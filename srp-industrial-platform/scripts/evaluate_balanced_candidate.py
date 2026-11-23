"""One held-out synthetic evaluation of a frozen candidate; no deployment."""
import hashlib,json,sys
from pathlib import Path
import joblib,numpy as np
from sklearn.metrics import classification_report,confusion_matrix,f1_score,log_loss
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/srp-apm')]
from fault_detection.remediation import live_inputs,CONFIDENCE,GATES

def main():
    artifact=ROOT/'data/training/balanced_experimental.joblib'
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    output=ROOT/'data/evaluation'/f'balanced_test_{digest[:16]}.json'
    if output.exists():
        print('Existing immutable evaluation:',output);return
    bundle=joblib.load(artifact);model=bundle['estimator'];meta=bundle['metadata']
    split=json.loads((ROOT/'data/evaluation/balanced_frozen_split.json').read_text())['partitions']
    records=[];seen={};duplicates=[]
    for path in sorted((ROOT/'data/generated/balanced_independent_strokes').glob('*.json')):
        row=json.loads(path.read_text())
        if row['split_group'] not in split['test']:continue
        if path.name in meta['source_hashes']:raise ValueError('Test record used for selection')
        label=meta['diagnostic_label_mapping'].get(row['mechanism'],row['mechanism'])
        fingerprint=hashlib.sha256(json.dumps(row['card']['surface_resampled'],sort_keys=True).encode()).hexdigest()
        if fingerprint in seen:
            if seen[fingerprint]!=label:raise ValueError('Identical test inputs have conflicting diagnostic labels')
            duplicates.append(path.name);continue
        seen[fingerprint]=label
        records.append((row,label,live_inputs(row['card'])[1]))
    if not records:raise ValueError('No test strokes')
    x=np.asarray([r[2] for r in records]);y=np.asarray([r[1] for r in records])
    p=model.predict_proba(x);pred=model.classes_[p.argmax(axis=1)];confidence=p.max(axis=1)
    accepted=confidence>=CONFIDENCE;correct=pred==y
    bins=[];ece=0.
    for lo in np.arange(0,1,.1):
        mask=(confidence>=lo)&(confidence<lo+.1 if lo<.9 else confidence<=1)
        if mask.any():
            accuracy=float(correct[mask].mean());mean_conf=float(confidence[mask].mean())
            ece+=mask.mean()*abs(accuracy-mean_conf)
            bins.append(dict(lower=float(lo),count=int(mask.sum()),accuracy=accuracy,confidence=mean_conf))
    report=dict(origin='HELD_OUT_SYNTHETIC_WELLS',artifact_sha256=digest,classes=model.classes_.tolist(),
        independent_virtual_wells=len({r[0]['split_group'] for r in records}),unique_test_strokes=len(records),
        excluded_duplicate_records=duplicates,macro_f1=float(f1_score(y,pred,average='macro')),
        per_class=classification_report(y,pred,output_dict=True,zero_division=0),
        confusion=confusion_matrix(y,pred,labels=model.classes_).tolist(),
        log_loss=float(log_loss(y,p,labels=model.classes_)),expected_calibration_error=float(ece),calibration_bins=bins,
        confidence_threshold=CONFIDENCE,coverage=float(accepted.mean()),
        accepted_accuracy=float(correct[accepted].mean()) if accepted.any() else None,
        real_test_wells=0,field_ready=False,deployment_gates=GATES,
        limitation='Uncalibrated candidate probabilities. No noise robustness or independently labeled field validation. Combined leakage output cannot identify the failed component.')
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['macro_f1','coverage','accepted_accuracy','expected_calibration_error','field_ready']},indent=2))
if __name__=='__main__':main()
