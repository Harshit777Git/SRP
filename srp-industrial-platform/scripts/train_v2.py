import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import time

from context import ROOT
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from configurations.presets import presets
from evaluate_wave import cycle
from fault_detection.models import baseline, cnn, inputs
from fault_injection.scenarios import Fault
from shared.contracts import Rod, Well


CLASSES=sorted(("healthy","incomplete_fillage","gas_interference","traveling_valve_leak",
                "standing_valve_leak","rod_friction","pump_wear","restricted_inflow"))
HERE=ROOT/"data"
SCHEMA="srp-v2-grouped/1.0"


def geometry(index):
    rng=np.random.default_rng(7313+index)
    base=presets()[index%3]
    rods=[Rod(length_m=r.length_m*rng.uniform(.82,1.17),diameter_m=r.diameter_m*rng.uniform(.92,1.08))
          for r in base.rods]
    return Well.model_validate(base.model_dump()|dict(asset_id=f"ML_{index:03}",rods=rods,
        plunger_m=rng.uniform(.036,.061),stroke_m=rng.uniform(1.4,2.6),
        spm=rng.uniform(5,9),fluid_kg_m3=rng.uniform(810,1020),
        chamber_gas_fraction=rng.uniform(.009,.035),
        viscosity_pa_s=rng.uniform(.009,.028),intake_head_m=rng.uniform(55,130),
        damping_s=rng.uniform(.36,.84),physics_step_s=.003,noise_load_n=rng.uniform(0,80),
        noise_position_m=rng.uniform(0,.002),seed=7313+index))


def features(card):
    channels, basics=inputs(card)
    well=card["asset_configuration"]
    rods=well["rods"]
    depth=sum(r["length_m"] for r in rods)
    hydro=max(1., (well["tubing_pa"]-well["casing_pa"]+well["fluid_kg_m3"]*9.80665*
                (depth-well["intake_head_m"]))*np.pi*well["plunger_m"]**2/4)
    signal=[]
    for x,f in channels.reshape(2,2,-1):
        signal.extend((np.abs(np.fft.rfft(f-f.mean())[1:13])/len(f)*30000/hydro).tolist())
        signal.extend((np.abs(np.fft.rfft(x-x.mean())[1:5])/len(x)).tolist())
    return channels,np.r_[basics,depth,hydro,well["plunger_m"],well["viscosity_pa_s"],
                           well["fluid_kg_m3"],well["stroke_m"],len(rods),signal]


def simulate(task):
    index,label=task
    well=geometry(index)
    seed=1917+index*len(CLASSES)+CLASSES.index(label)
    well=well.model_copy(update={"seed":seed})
    severity=float(np.random.default_rng(seed).uniform(.28,.96))
    run=f"{well.asset_id}/{label}/{seed}"
    fault=Fault(kind=label,severity=severity)
    try:
        card,_,_=cycle(well,fault,run)
        series,feature=features(card)
    except (RuntimeError,ValueError,KeyError) as e:
        return dict(run=run,error=str(e),label=label,group=index,seed=seed,well=well.model_dump(),severity=severity)
    return dict(run=run,label=label,group=index,seed=seed,well=well.model_dump(),severity=severity,
                series=series,feature=feature,rule=baseline(card)["label"])


def evaluate(y,p,domain):
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    labels=np.array(CLASSES)
    score=p.max(axis=1)
    pred=labels[p.argmax(axis=1)]
    use=(score>=.7)&domain
    bins=[]
    for low in np.arange(0,1,.1):
        take=(score>=low)&(score<(low+.1) if low<.89 else score<=1)
        if take.any():
            bins.append(float(take.mean()*abs(score[take].mean()-(pred[take]==y[take]).mean())))
    return dict(accuracy=accuracy_score(y,pred),macro_f1=f1_score(y,pred,average="macro"),
        per_class=classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0),
        confusion_matrix=confusion_matrix(y,pred,labels=CLASSES).tolist(),expected_calibration_error=sum(bins),
        unknown_fraction=float((~use).mean()),
        selective_accuracy=float((pred[use]==y[use]).mean()) if use.any() else None,
        healthy_false_positive_fraction=float(((pred[y=="healthy"]!="healthy")&use[y=="healthy"]).mean()))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--runs-per-class",type=int,default=100)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--reuse",action="store_true")
    parser.add_argument("--tag",choices=("v2","v2_full"),default="v2")
    args=parser.parse_args()
    if args.runs_per_class<6:
        parser.error("At least six configurations are required")
    dataset=HERE/"training"/f"{args.tag}_runs.npz"
    manifest=HERE/"training"/f"{args.tag}_runs.json"
    artifacts=HERE/"evaluation"
    if not args.reuse:
        tasks=[(i,label) for i in range(args.runs_per_class) for label in CLASSES]
        with ProcessPoolExecutor(max_workers=args.workers) as workers:
            rows=[]
            for index,row in enumerate(workers.map(simulate,tasks),1):
                rows.append(row)
                if index%50==0 or index==len(tasks):
                    print(f"Generated {index}/{len(tasks)} independent runs",flush=True)
        manifest.write_text(json.dumps([dict((k,v) for k,v in row.items() if k not in ("series","feature"))
                                        for row in rows],indent=2))
        valid=[r for r in rows if "error" not in r]
        if not valid:
            raise RuntimeError("No complete reconstruction")
        np.savez_compressed(dataset,**{k:np.array([row[k] for row in valid]) for k in
             ("series","feature","label","group","seed","rule","run")})
    with np.load(dataset) as data:
        x,y,g,w=[data[name] for name in ("feature","label","group","series")]
        groups=sorted(int(group) for group in set(g)); n=len(groups)
        holdout=max(2,n//5)
        splits=(groups[:-2*holdout],groups[-2*holdout:-holdout],groups[-holdout:])
        tr,ca,te=[np.isin(g,selected) for selected in splits]
        assert len(set(g[tr])&set(g[te]))==0
        if any(set(y[mask])!=set(CLASSES) for mask in (tr,ca,te)):
            raise RuntimeError("A split lacks class coverage")
        results=dict(validation="SYNTHETIC VALIDATION ONLY",schema=SCHEMA,classes=CLASSES,
            groups=dict(zip(("train","calibration","test"),splits)),
            dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
            counts={label:int(np.sum(y==label)) for label in CLASSES},accepted_runs=len(y),
            rejected_runs=sum("error" in row for row in json.loads(manifest.read_text())),
            rules=dict(unknown_fraction=float(np.mean(np.isin(data["rule"][te],["UNKNOWN","FAULT_TYPE_UNDETERMINED"])))),seeds=[],
            false_alarms_per_well_day=None,detection_latency_s=None)
        domain=(x[te,0]>=x[tr,0].min())&(x[te,0]<=x[tr,0].max())
        import torch
        torch.set_num_threads(2)
        series=torch.tensor(w,dtype=torch.float32)
        target=torch.tensor(np.searchsorted(CLASSES,y),dtype=torch.long)
        import joblib
        try:
            from lightgbm import LGBMClassifier
        except ImportError:
            LGBMClassifier=None
        results["tabular_model"]="LightGBM" if LGBMClassifier else "HistGradientBoosting"
        for seed in (13,29,71):
            torch.manual_seed(seed)
            tab=(LGBMClassifier(random_state=seed,n_estimators=120,min_child_samples=4,num_leaves=12,
                                reg_lambda=1.,n_jobs=1,verbosity=-1) if LGBMClassifier else
                 HistGradientBoostingClassifier(random_state=seed,max_iter=120,min_samples_leaf=4,
                                                l2_regularization=1.)).fit(x[tr],y[tr])
            cal=LogisticRegression(C=.3,max_iter=1000).fit(np.log(tab.predict_proba(x[ca]).clip(1e-6)),y[ca])
            t0=time.perf_counter()
            pt=cal.predict_proba(np.log(tab.predict_proba(x[te]).clip(1e-6)))
            tab_ms=(time.perf_counter()-t0)*1000/sum(te)
            net=cnn(len(CLASSES))
            opt=torch.optim.AdamW(net.parameters(),lr=.004)
            for _ in range(45):
                net.train();opt.zero_grad()
                loss=torch.nn.functional.cross_entropy(net(series[tr]),target[tr])
                loss.backward();opt.step()
            net.eval()
            with torch.inference_mode():
                logits=net(series[ca])
                temperatures=np.geomspace(.3,8,35)
                temp=min(temperatures,key=lambda v:float(torch.nn.functional.cross_entropy(logits/float(v),target[ca])))
                t0=time.perf_counter()
                pn=torch.softmax(net(series[te])/float(temp),dim=1).numpy()
                cnn_ms=(time.perf_counter()-t0)*1000/sum(te)
            version=results["dataset_sha256"][:12]+f"-{seed}"
            metadata=dict(classes=CLASSES, origin="SIMULATED", deployed=False, status="TRAINED_ON_SYNTHETIC",
                          model_version="cnn-v2/"+version, dataset=dataset.name, dataset_sha256=results["dataset_sha256"])
            domain_bounds=[float(x[tr,0].min()),float(x[tr,0].max())]
            torch.save(dict(weights=net.state_dict(),temperature=float(temp),domain=domain_bounds,metadata=metadata),
                       HERE/"training"/f"v2_cnn_{version}.pt")
            joblib.dump(dict(estimator=tab,calibrator=cal,metadata=metadata|{"model_version":"tabular-v2/"+version}),
                        HERE/"training"/f"v2_tabular_{version}.joblib")
            results["seeds"].append(dict(seed=seed,tabular=evaluate(y[te],pt,domain)|{"inference_ms":tab_ms},
                cnn=evaluate(y[te],pn,domain)|{"temperature":float(temp),"inference_ms":cnn_ms},
                ensemble=evaluate(y[te],(pt+pn)/2,domain)))
        results["macro_f1_across_seeds"]={k:dict(mean=float(np.mean(values)),spread=float(np.std(values)))
            for k in ("tabular","cnn","ensemble") if (values:=[r[k]["macro_f1"] for r in results["seeds"]])}
        (artifacts/f"{args.tag}_ml.json").write_text(json.dumps(results,indent=2,allow_nan=False))
        print(json.dumps(dict(runs=len(y),metrics=results["macro_f1_across_seeds"]),indent=2))


if __name__=="__main__":
    main()
