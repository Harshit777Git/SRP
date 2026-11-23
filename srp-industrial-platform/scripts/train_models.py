import argparse
import hashlib
import json
import time

from context import ROOT
import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from configurations.presets import presets
from evaluate_wave import cycle
from fault_detection.models import cnn, inputs
from fault_injection.scenarios import Fault

CLASSES = ["gas_interference","healthy","traveling_valve_leak"]


def create_dataset(count):
    sequences, features, labels, groups, runs, contexts, quality = [],[],[],[],[],[],[]
    for group, preset in enumerate(presets()):
        for index in range(count):
            for label in CLASSES:
                w = preset.model_copy(update=dict(spm=preset.spm+(-.4+.8*index/max(1,count-1)),
                                                  noise_load_n=25*index,
                                                  noise_position_m=.001*index,seed=32+index))
                run_id = f"{preset.asset_id}-{label}-{index}"
                card, _, _ = cycle(w,Fault(kind=label,severity=.5+.4*index/max(1,count-1)),run_id)
                assert card["downhole"]["status"]=="SOLVED", run_id
                series, vector = inputs(card)
                sequences.append(series)
                features.append(vector)
                labels.append(label)
                groups.append(group)
                runs.append(run_id)
                contexts.append(w.model_dump_json())
                quality.append(card["quality"])
    path = ROOT/"data/training/simulated_cards.npz"
    np.savez_compressed(path,series=sequences,features=features,labels=labels,
                        groups=groups,runs=runs,contexts=contexts,quality=quality,origin="SIMULATED",
                        channel_scales=[3,30000,3,30000])
    return path


def metrics(y, probabilities, latency):
    predictions = np.asarray(CLASSES)[probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    correct = predictions==y
    bins = []
    for low in np.arange(0,1,.2):
        mask = (confidence>=low)&(confidence<low+.2 if low<.79 else confidence<=1)
        if mask.any():
            bins.append(dict(n=int(mask.sum()),mean_confidence=float(confidence[mask].mean()),
                             accuracy=float(correct[mask].mean())))
    n = len(y)
    return dict(samples=n,accuracy=accuracy_score(y,predictions),
                macro_f1=f1_score(y,predictions,average="macro"),
                by_class=classification_report(y,predictions,labels=CLASSES,output_dict=True,zero_division=0),
                confusion_matrix=confusion_matrix(y,predictions,labels=CLASSES).tolist(),
                calibration_bins=bins, expected_calibration_error=sum(
                    b["n"]*abs(b["mean_confidence"]-b["accuracy"]) for b in bins)/n,
                abstention_fraction=float(np.mean(confidence<.7)),mean_batch_inference_ms=latency*1000/n,
                labels=CLASSES,predictions=predictions.tolist())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--runs-per-class",type=int,default=4)
    parser.add_argument("--reuse",action="store_true")
    parser.add_argument("--cnn",action="store_true")
    args=parser.parse_args()
    path = ROOT/"data/training/simulated_cards.npz" if args.reuse else create_dataset(args.runs_per_class)
    data = np.load(path)
    train,cal,test = [data["groups"]==i for i in range(3)]
    train_ids,cal_ids,test_ids = [set(data["runs"][s]) for s in (train,cal,test)]
    assert not (train_ids&cal_ids or train_ids&test_ids or cal_ids&test_ids)
    x,y = data["features"],data["labels"]
    estimator = RandomForestClassifier(n_estimators=120,min_samples_leaf=2,random_state=42).fit(x[train],y[train])
    calibrated = CalibratedClassifierCV(FrozenEstimator(estimator),method="sigmoid",cv=2).fit(x[cal],y[cal])
    started = time.perf_counter()
    proba = calibrated.predict_proba(x[test])
    report = dict(origin="SIMULATED",split=dict(train="SRP_001",calibration="SRP_002",test="SRP_003"),
                  dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  tabular=metrics(y[test],proba,time.perf_counter()-started))
    version = "rf/"+report["dataset_sha256"][:12]
    metadata = dict(model_version=version, status="TRAINED_ON_SYNTHETIC",origin="SIMULATED",
                    classes=CLASSES,dataset=path.name,dataset_sha256=report["dataset_sha256"],
                    comparison="data/evaluation/ml.json")
    domain = [float(x[train,0].min()),float(x[train,0].max())]
    report["domain_aware_test_abstention_fraction"] = float(np.mean(
        (x[test,0]<domain[0]-.03)|(x[test,0]>domain[1]+.03)|(proba.max(axis=1)<.7)))
    report["longitudinal_metrics"] = dict(false_alarms_per_day=None,detection_latency=None,
        reason="isolated steady-state strokes have no monitored day or onset trajectory")
    joblib.dump(dict(estimator=calibrated,metadata=metadata,domain=domain),ROOT/"data/training/model.joblib")
    if args.cnn:
        import torch
        torch.manual_seed(42)
        torch.set_num_threads(2)
        model=cnn()
        optimizer=torch.optim.Adam(model.parameters(),lr=.004)
        series=torch.tensor(data["series"],dtype=torch.float32)
        target=torch.tensor(np.searchsorted(CLASSES,y),dtype=torch.long)
        for _ in range(80):
            optimizer.zero_grad()
            loss=torch.nn.functional.cross_entropy(model(series[train]),target[train])
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            cal_logits=model(series[cal])
            temperatures=torch.logspace(-1,1,41)
            scores=[torch.nn.functional.cross_entropy(cal_logits/t,target[cal]).item() for t in temperatures]
            temperature=float(temperatures[np.argmin(scores)])
            started=time.perf_counter()
            probs=torch.softmax(model(series[test])/temperature,dim=1).numpy()
        report["cnn"]=dict(temperature=temperature,**metrics(y[test],probs,time.perf_counter()-started))
        torch.save(dict(weights=model.state_dict(),temperature=temperature,domain=domain,
                        metadata=metadata|{"model_version":"cnn/"+version[3:]}),
                   ROOT/"data/training/cnn.pt")
    (ROOT/"data/evaluation/ml.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({name:(values["accuracy"],values["macro_f1"]) for name,values in report.items()
                      if name in ("cnn","tabular")}))


if __name__=="__main__":
    main()
