import hashlib
import json
import time

import joblib
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

from context import ROOT
from fault_detection.models import cnn
from fault_detection.remediation import CONFIDENCE, GATES, SCHEMA, physical_inputs


def report(y,p,classes,in_domain):
    predicted=classes[p.argmax(axis=1)]
    confidence=p.max(axis=1)
    keep=(confidence>=CONFIDENCE)&in_domain
    ece=0.
    for group in range(10):
        mask=np.minimum((confidence*10).astype(int),9)==group
        if mask.any():
            ece+=mask.mean()*abs(confidence[mask].mean()-(predicted[mask]==y[mask]).mean())
    return dict(macro_f1=f1_score(y,predicted,average="macro"),coverage=float(keep.mean()),
                accuracy=float((predicted==y).mean()),ece=float(ece),
                selective_accuracy=float((predicted[keep]==y[keep]).mean()) if keep.any() else None,
                per_class=classification_report(y,predicted,labels=classes,output_dict=True,zero_division=0),
                confusion=confusion_matrix(y,predicted,labels=classes).tolist(),
                selective_macro_f1=f1_score(y,np.where(keep,predicted,"FAULT_TYPE_UNDETERMINED"),
                                           labels=classes,average="macro",zero_division=0))


def main():
    path=ROOT/"data/training/v2_full_runs.npz"
    conditions={r["run"]:r for r in json.loads(path.with_suffix(".json").read_text())}
    with np.load(path) as src:
        original=src["series"]
        y,g=src["label"],src["group"]
        features=[physical_inputs(c,conditions[r]["well"],spm) for c,r,spm in
                  zip(original,src["run"],src["feature"][:,0],strict=True)]
    channels=np.asarray([s for s,f in features],dtype=np.float32)
    x=np.asarray([f for s,f in features])
    old=json.loads((ROOT/"data/evaluation/v2_full_ml.json").read_text())
    tr,ca,te=[np.isin(g,old["groups"][key]) for key in ("train","calibration","test")]
    assert not ((tr&ca)|(ca&te)|(tr&te)).any()
    classes=np.unique(y)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(schema=SCHEMA,classes=classes.tolist(),dataset_sha256=sha,
                partitions=old["groups"],counts=[int(k.sum()) for k in (tr,ca,te)],
                validation="synthetic development benchmark; historical holdout reused",
                real_labeled_test_wells=0,gates=GATES,models={})
    bounds=[float(np.min(x[tr,-7])),float(np.max(x[tr,-7]))]
    domain=(x[:,-7]>=bounds[0]-.03)&(x[:,-7]<=bounds[1]+.03)
    metadata=dict(classes=classes.tolist(),schema=SCHEMA,dataset=path.name,origin="SIMULATED",
                  approved_for_deployment=False,status="EXPERIMENTAL_SYNTHETIC")
    for name,est in [
        ("physics_features",make_pipeline(RobustScaler(),LogisticRegression(C=.8,max_iter=2500))),
        ("lightgbm",LGBMClassifier(n_estimators=220,min_child_samples=8,num_leaves=15,
                                   verbosity=-1,n_jobs=2,random_state=43,reg_lambda=1.5)),
        ("extra_trees",ExtraTreesClassifier(n_estimators=350,min_samples_leaf=2,n_jobs=2,random_state=43))
    ]:
        est.fit(x[tr],y[tr])
        cal=LogisticRegression(C=.4,max_iter=1500).fit(np.log(est.predict_proba(x[ca]).clip(1e-6)),y[ca])
        prob=lambda rows:cal.predict_proba(np.log(est.predict_proba(rows).clip(1e-6)))
        start=time.perf_counter()
        p=prob(x[te])
        result["models"][name]=report(y[te],p,classes,domain[te])|{"calibration":report(y[ca],prob(x[ca]),classes,domain[ca]),
            "inference_ms_per_card":(time.perf_counter()-start)*1000/len(p)}
        joblib.dump(dict(estimator=est,calibrator=cal,domain=bounds,
                         metadata=metadata|{"model_version":f"remediation/{name}/{sha[:12]}"}),
                    ROOT/"data/training"/f"remediation_{name}.joblib")
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(43)
    data=torch.tensor(channels)
    target=torch.tensor(np.searchsorted(classes,y),dtype=torch.long)
    net=cnn(len(classes))
    optimizer=torch.optim.AdamW(net.parameters(),lr=.003)
    for _ in range(55):
        indices=torch.randperm(int(tr.sum()))
        for mini in indices.split(64):
            optimizer.zero_grad()
            loss=torch.nn.functional.cross_entropy(net(data[tr][mini]),target[tr][mini])
            loss.backward()
            optimizer.step()
    net.eval()
    with torch.inference_mode():
        logits=net(data[ca])
        temp=min(np.geomspace(.4,5,40),key=lambda t:float(torch.nn.functional.cross_entropy(logits/float(t),target[ca])))
        val=torch.softmax(logits/float(temp),dim=1).numpy()
        start=time.perf_counter()
        p=torch.softmax(net(data[te])/float(temp),dim=1).numpy()
        latency=(time.perf_counter()-start)*1000/len(p)
    result["models"]["cnn"]=report(y[te],p,classes,domain[te])|{"calibration":report(y[ca],val,classes,domain[ca]),"inference_ms_per_card":latency}
    torch.save(dict(weights=net.state_dict(),temperature=float(temp),domain=bounds,
                    metadata=metadata|{"model_version":f"remediation/cnn/{sha[:12]}"}),ROOT/"data/training/remediation_cnn.pt")
    result["deployed_model"]=None
    (ROOT/"data/evaluation/remediation_metrics.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print({name:(round(m["macro_f1"],3),round(m["coverage"],3)) for name,m in result["models"].items()},flush=True)


if __name__=="__main__":
    main()
