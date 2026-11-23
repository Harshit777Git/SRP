from concurrent.futures import ProcessPoolExecutor
import json

import joblib
import numpy as np
import torch

from context import ROOT
from configurations.presets import presets
from evaluate_wave import cycle
from fault_detection.models import cnn
from fault_detection.remediation import physical_inputs
from fault_injection.scenarios import Fault
from train_v2 import CLASSES, simulate
from train_remediation import report


def main():
    tasks=[(g,label) for g in range(100,112) for label in CLASSES]
    with ProcessPoolExecutor(max_workers=6) as pool:
        runs=list(pool.map(simulate,tasks))
    valid=[item for item in runs if "error" not in item]
    meta=[{key:value for key,value in r.items() if key not in ("series","feature")} for r in runs]
    target=np.array([r["label"] for r in valid])
    yclasses=np.asarray(CLASSES)
    data=[physical_inputs(r["series"],r["well"],r["feature"][0]) for r in valid]
    channels=np.array([item[0] for item in data],dtype=np.float32)
    features=np.array([item[1] for item in data])
    results={}
    for name in ("physics_features","lightgbm","extra_trees","cnn"):
        folder=ROOT/"data/training"
        if name=="cnn":
            torch.set_num_threads(2)
            artifact=torch.load(folder/"remediation_cnn.pt",map_location="cpu",weights_only=True)
            net=cnn(len(CLASSES))
            net.load_state_dict(artifact["weights"])
            net.eval()
            with torch.inference_mode():
                p=torch.softmax(net(torch.tensor(channels))/artifact["temperature"],dim=1).numpy()
        else:
            artifact=joblib.load(folder/f"remediation_{name}.joblib")
            p=artifact["calibrator"].predict_proba(np.log(artifact["estimator"].predict_proba(features).clip(1e-6)))
        low,high=artifact["domain"]
        domain=(features[:,-7]>=low-.03)&(features[:,-7]<=high+.03)
        results[name]=report(target,p,yclasses,domain)
    w=presets()[0]
    leak,*_=cycle(w,Fault(kind="traveling_valve_leak",severity=.75))
    wear,*_=cycle(w,Fault(kind="pump_wear",severity=.50))
    counterexample={name:float(np.max(abs(np.asarray(leak[name]["load_n"])-wear[name]["load_n"])))
                    for name in ("surface_resampled","downhole")}
    evidence=dict(validation="fresh synthetic, changed simulator physics",classes=CLASSES,
        test_configs=list(range(100,112)),accepted_runs=len(valid),rejected_runs=len(runs)-len(valid),
        models=results,runs=meta,matched_leak_wear_max_load_difference_N=counterexample)
    (ROOT/"data/evaluation/remediation_fresh.json").write_text(json.dumps(evidence,indent=2,allow_nan=False))
    print(len(valid),{k:round(v["macro_f1"],4) for k,v in results.items()},counterexample,flush=True)


if __name__=="__main__":
    main()
