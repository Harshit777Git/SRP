"""Select synthetic candidates on validation wells; never deploy or read test cards."""
import json,sys,hashlib
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import f1_score,classification_report,confusion_matrix
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/srp-apm')]
from fault_detection.remediation import live_inputs,SCHEMA
DIAGNOSTIC_LABELS={'pump_wear':'traveling_valve_or_plunger_leakage',
                   'traveling_valve_leak':'traveling_valve_or_plunger_leakage'}

def main():
    split=json.loads((ROOT/'data/evaluation/balanced_frozen_split.json').read_text())['partitions']
    data=ROOT/'data/generated/balanced_independent_strokes'
    paths=sorted(data.glob('*.json'))
    if len(paths)!=2970:raise RuntimeError(f'Expected complete 2970-stroke experiment; found {len(paths)}. Training deferred.')
    x=[];y=[];part=[];hashes={};seen={};duplicates=[];coverage=defaultdict(set)
    mechanisms=[];severities=[]
    for path in paths:
        row=json.loads(path.read_text())
        asset=row['split_group']
        if asset in split['test']:continue
        partition='train' if asset in split['train'] else 'validation'
        assert asset in split[partition]
        coverage[(asset,row['mechanism'])].add(row['severity'])
        label=DIAGNOSTIC_LABELS.get(row['mechanism'],row['mechanism'])
        fingerprint=hashlib.sha256(json.dumps(row['card']['surface_resampled'],sort_keys=True).encode()).hexdigest()
        if fingerprint in seen:
            previous=seen[fingerprint]
            if previous['partition']!=partition:
                raise ValueError('Identical surface signal crosses training/validation partitions')
            if previous['label']!=label:
                raise ValueError('Identical surface signal has conflicting mechanism labels')
            duplicates.append(path.name)
            continue
        seen[fingerprint]=dict(partition=partition,label=label)
        x.append(live_inputs(row['card'])[1]);y.append(label);part.append(partition)
        mechanisms.append(row['mechanism']);severities.append(row['severity'])
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    x=np.asarray(x);y=np.asarray(y);train=np.asarray(part)=='train';validation=~train
    mechanisms=np.asarray(mechanisms);severities=np.asarray(severities)
    assert np.isfinite(x).all()
    classes={mechanism for asset,mechanism in coverage}
    expected={.001,.01,.05,.1,.2,.4,.6,.8,1.}
    for asset in split['train']+split['validation']:
        for label in classes:
            if coverage[(asset,label)]!=({0.} if label=='healthy' else expected):
                raise ValueError(f'Incomplete severity coverage: {asset}/{label}')
    candidates={
        'logistic':make_pipeline(RobustScaler(),LogisticRegression(max_iter=4000,C=1,class_weight='balanced')),
        'extra_trees':ExtraTreesClassifier(n_estimators=400,min_samples_leaf=2,n_jobs=2,random_state=73129,class_weight='balanced'),
        'hist_gradient':HistGradientBoostingClassifier(max_iter=250,max_leaf_nodes=15,l2_regularization=1,random_state=73129)}
    metrics={}
    for name,model in candidates.items():
        if name=='hist_gradient':
            counts=Counter(y[train]);weights=np.asarray([len(y[train])/(len(counts)*counts[label]) for label in y[train]])
            model.fit(x[train],y[train],sample_weight=weights)
        else:model.fit(x[train],y[train])
        pred=model.predict(x[validation])
        metrics[name]=dict(macro_f1=float(f1_score(y[validation],pred,average='macro')),
            classes=model.classes_.tolist(),confusion=confusion_matrix(y[validation],pred,labels=model.classes_).tolist(),
            per_class=classification_report(y[validation],pred,output_dict=True,zero_division=0))
        metrics[name]['by_severity']={str(level):dict(
            samples=int(np.sum(severities[validation]==level)),
            accuracy=float(np.mean(pred[severities[validation]==level]==y[validation][severities[validation]==level])))
            for level in sorted(set(severities[validation]))}
        metrics[name]['original_mechanism_predictions']={str(mechanism):dict(Counter(
            pred[mechanisms[validation]==mechanism])) for mechanism in sorted(set(mechanisms[validation]))}
        metrics[name]['component_resolution_limit']='Combined leakage output does not resolve pump wear versus traveling valve failure.'
        print(name,metrics[name]['macro_f1'],flush=True)
    selected=max(metrics,key=lambda k:metrics[k]['macro_f1'])
    metadata=dict(origin='SYNTHETIC_ONLY',deployed=False,feature_schema=SCHEMA,selected=selected,
                  validation=metrics,test_evaluated=False,field_test_wells=0,source_hashes=hashes,
                  excluded_exact_duplicates=duplicates,unique_class_counts=dict(Counter(y)),
                  diagnostic_label_mapping=DIAGNOSTIC_LABELS,
                  unresolved_distinction='Pump wear and traveling valve leakage share the simulated leakage conductance; component identification requires independent evidence.')
    joblib.dump(dict(estimator=candidates[selected],metadata=metadata),ROOT/'data/training/balanced_experimental.joblib')
    (ROOT/'data/evaluation/balanced_candidate_selection.json').write_text(json.dumps(metadata,indent=2))
if __name__=='__main__':main()
