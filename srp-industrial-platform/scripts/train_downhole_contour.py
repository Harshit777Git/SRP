"""Train on supplied contour images encoded from their clean coordinate pairs.
Well-group holdout, duplicate embargo, no identities/labels in model features.
"""
import csv,hashlib,json,re
from pathlib import Path
from collections import Counter
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from context import ROOT
from fault_detection.contour import encode,SCHEMA

source=ROOT.parent/'DH_IMG_PREDICTION_ML_DATASET'
index=list(csv.DictReader((source/'DOWNHOLE_CARD_DATASET_INDEX.csv').open(encoding='utf-8-sig')))
coordinates={r['image_id']:r for r in csv.DictReader((source/'DOWNHOLE_CARD_COORDINATES.csv').open(encoding='utf-8-sig'))}
vectors=[];labels=[];groups=[];ids=[];image_missing=[]
for row in index:
    if not (source/row['image_path']).is_file():image_missing.append(row['image_id'])
    c=coordinates[row['image_id']]
    x=[float(v)*.0254 for v in c['raw_downhole_pos_in_100'].split(';')]
    f=[float(v)*4.4482216152605 for v in c['raw_downhole_load_lbf_100'].split(';')]
    sx=[float(v)*.0254 for v in c['raw_surface_pos_in_100'].split(';')]
    sf=[float(v)*4.4482216152605 for v in c['raw_surface_load_lbf_100'].split(';')]
    vectors.append(np.r_[encode(sx,sf),encode(x,f)]);labels.append(row['fault_class_name']);ids.append(row['image_id'])
    # All augmentation variants from one crossfield equipment family stay together.
    groups.append('catalog_benchmark' if row['source']=='96_state_catalog_benchmark' else
        'crossfield_'+row['field'].lower() if Path(row['image_path']).name.startswith('crossfield') else row['well_id'])
X=np.asarray(vectors);y=np.asarray(labels);groups=np.asarray(groups);classes=sorted(set(y))
for seed in range(1000):
    trainval,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(X,y,groups))
    a,b=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed+1000).split(X[trainval],y[trainval],groups[trainval]))
    train,val=trainval[a],trainval[b]
    if all(set(y[fold])==set(classes) for fold in (train,val,test)):break
else:raise ValueError('Insufficient independent groups for all classes in three folds')
fingerprints=[hashlib.sha256(np.round(v*255).astype('uint8').tobytes()).hexdigest() for v in X]
seen=set();purged={}
def embargo(fold,name):
    kept=[]
    for i in fold:
        if fingerprints[i] not in seen:kept.append(i)
    purged[name]=len(fold)-len(kept);seen.update(fingerprints[i] for i in fold)
    return np.asarray(kept,dtype=int)
train=embargo(train,'train');val=embargo(val,'validation');test=embargo(test,'test')
if not len(val) or not len(test):raise ValueError('No independent contours after duplicate embargo')
models=[]
for features in (.4,1.):
    model=ExtraTreesClassifier(n_estimators=300,max_features=features,class_weight='balanced',random_state=42,n_jobs=2)
    model.fit(X[train],y[train]);score=f1_score(y[val],model.predict(X[val]),labels=classes,average='macro',zero_division=0)
    models.append((score,model));print('Validation macro F1',score,'max_features',features,flush=True)
for c in (1,10,100):
    model=make_pipeline(StandardScaler(),SVC(C=c,probability=True,class_weight='balanced',random_state=42))
    model.fit(X[train],y[train]);score=f1_score(y[val],model.predict(X[val]),labels=classes,average='macro',zero_division=0)
    models.append((score,model));print('Validation macro F1',score,'SVC C',c,flush=True)
_,model=max(models,key=lambda pair:pair[0]);vp=model.predict_proba(X[val]);confidence=vp.max(axis=1);correct=model.classes_[vp.argmax(axis=1)]==y[val]
eligible=[t for t in np.arange(.5,.96,.05) if (confidence>=t).sum()>=10 and correct[confidence>=t].mean()>=.85]
threshold=float(min(eligible)) if eligible else .9
distance=np.array([np.sqrt(np.mean((X[train]-v)**2,axis=1)).min() for v in X[val]])
distance_limit=float(max(.035,np.quantile(distance,.99)*1.25))
prediction=model.predict(X[test]);prob=model.predict_proba(X[test]);selected=prob.max(axis=1)>=threshold
test_distance=np.array([np.sqrt(np.mean((X[train]-v)**2,axis=1)).min() for v in X[test]])
selected&=test_distance<=distance_limit
report=dict(schema=SCHEMA,origin='SIMULATED',field_validated=False,rows=len(X),classes=classes,
    group_split_seed=seed,group_overlap=0,duplicate_embargo=purged,missing_images=image_missing,
    train_rows=len(train),validation_rows=len(val),test_rows=len(test),
    train_groups=len(set(groups[train])),validation_groups=len(set(groups[val])),test_groups=len(set(groups[test])),
    accuracy=float(accuracy_score(y[test],prediction)),macro_f1=float(f1_score(y[test],prediction,labels=classes,average='macro',zero_division=0)),
    classification_report=classification_report(y[test],prediction,labels=classes,output_dict=True,zero_division=0),
    confusion_matrix=confusion_matrix(y[test],prediction,labels=classes).tolist(),
    abstention_threshold=threshold,accepted_coverage=float(selected.mean()),accepted_accuracy=float((prediction[selected]==y[test][selected]).mean()) if selected.any() else None,
    feature_contract=['surface_resampled.position_m','surface_resampled.load_n','downhole.position_m','downhole.load_n'],
    forbidden_features=['well_id','asset_id','state_id','fault_class_name','fault_class_id','fault_severity','image_path','image_id','field','stroke_id'],
    split_members={name:[ids[i] for i in fold] for name,fold in [('train',train),('validation',val),('test',test)]},
    limitations=['synthetic source only','holdout contours are not independent field validation','solver-to-dataset domain shift is gated with abstention'])
metadata=dict(model_version='paired-contour/3.0',schema=SCHEMA,classes=classes,origin='SIMULATED',
    status='HELD_OUT_SYNTHETIC_EVALUATION',dataset='DH_IMG_PREDICTION_ML_DATASET',approved_for_deployment=False,
    field_validated=False,feature_contract=report['feature_contract'],evaluation={k:report[k] for k in ['accuracy','macro_f1','accepted_coverage','accepted_accuracy']})
artifact=dict(metadata=metadata,estimator=model,threshold=threshold,distance_limit=distance_limit,reference_vectors=X[train])
joblib.dump(artifact,ROOT/'data/training/downhole_contour.joblib')
(ROOT/'reports/DOWNHOLE_CONTOUR_TRAINING.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ['split_members','classification_report','confusion_matrix']},indent=2))
