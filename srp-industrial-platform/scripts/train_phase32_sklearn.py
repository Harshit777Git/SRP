"""Grouped synthetic-only candidate selection; never deploys a model."""
import hashlib,json,time,sys
from pathlib import Path
import joblib,numpy as np
from sklearn.ensemble import ExtraTreesClassifier,RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score,confusion_matrix,f1_score,classification_report,log_loss
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.linear_model import LogisticRegression

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/srp-apm'),str(ROOT/'apps/srp-simulator')]
from fault_detection.remediation import physical_inputs,SCHEMA
DATA=ROOT/'data/training/v2_full_runs.npz';OUT=ROOT/'data/evaluation/phase32_sklearn_grouped.json'
def main():
 old=json.loads((ROOT/'data/evaluation/v2_full_ml.json').read_text())
 conditions={r['run']:r for r in json.loads(DATA.with_suffix('.json').read_text())}
 with np.load(DATA) as d:
  x=np.asarray([physical_inputs(card,conditions[run]['well'],spm)[1] for card,run,spm in zip(d['series'],d['run'],d['feature'][:,0],strict=True)],dtype=np.float32)
  y=np.asarray(d['label']);g=np.asarray(d['group'])
 tr,ca,te=(np.isin(g,old['groups'][k]) for k in ('train','calibration','test'))
 assert tr.sum() and ca.sum() and te.sum() and not ((tr&ca)|(tr&te)|(ca&te)).any()
 classes=np.unique(y);models={};candidates=[
  ('extra_trees_leaf1',ExtraTreesClassifier(n_estimators=300,min_samples_leaf=1,n_jobs=2,random_state=43)),
  ('extra_trees_leaf3',ExtraTreesClassifier(n_estimators=300,min_samples_leaf=3,n_jobs=2,random_state=43)),
  ('random_forest_leaf2',RandomForestClassifier(n_estimators=300,min_samples_leaf=2,n_jobs=2,random_state=43)),
  ('hist_gradient_100',HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,l2_regularization=1.5,random_state=43)),
  ('hist_gradient_250',HistGradientBoostingClassifier(max_iter=250,max_leaf_nodes=15,l2_regularization=1.5,random_state=43)),
  ('logistic_c01',make_pipeline(RobustScaler(),LogisticRegression(C=.1,max_iter=3000))),
  ('logistic_c1',make_pipeline(RobustScaler(),LogisticRegression(C=1,max_iter=3000))),
  ('logistic_c10',make_pipeline(RobustScaler(),LogisticRegression(C=10,max_iter=3000)))]
 for name,model in candidates:
  start=time.perf_counter();model.fit(x[tr],y[tr]);pred=model.predict(x[ca]);proba=model.predict_proba(x[ca]);
  models[name]=dict(calibration_macro_f1=float(f1_score(y[ca],pred,average='macro')),calibration_log_loss=float(log_loss(y[ca],proba,labels=model.classes_)),fit_seconds=time.perf_counter()-start)
 selected=max(models,key=lambda n:(models[n]['calibration_macro_f1'],-models[n]['calibration_log_loss']))
 model=dict(candidates)[selected];pred=model.predict(x[te]);proba=model.predict_proba(x[te]);
 result=dict(origin='SYNTHETIC_ONLY',dataset_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),classes=classes.tolist(),
  counts=dict(train=int(tr.sum()),calibration=int(ca.sum()),test=int(te.sum())),groups=old['groups'],selection_metric='calibration_macro_f1_then_log_loss',
  candidates=models,selected=selected,test=dict(macro_f1=float(f1_score(y[te],pred,average='macro')),accuracy=float(accuracy_score(y[te],pred)),
   log_loss=float(log_loss(y[te],proba,labels=model.classes_)),per_class=classification_report(y[te],pred,labels=classes,output_dict=True,zero_division=0),
   confusion=confusion_matrix(y[te],pred,labels=classes).tolist()),field_test_wells=0,deployed=False,
  limitation='Previous grouped holdout reused; 57 new cards are too sparse per class and include classes absent from this 8-class model.')
 OUT.write_text(json.dumps(result,indent=2));joblib.dump(dict(estimator=model,metadata=dict(origin='SYNTHETIC',deployed=False,classes=classes.tolist(),feature_schema=SCHEMA)),
  ROOT/'data/training/phase32_sklearn_experimental.joblib');print(json.dumps({k:result[k] for k in ('counts','selected','test','field_test_wells')},indent=2))
if __name__=='__main__':main()
