"""Research-only provider-fillage baseline; no verified fault labels or production artifact."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/external_reference/nk_well_monitoring/wells_dataset.csv'
OUT=ROOT/'reports/SRP_NK_FILLAGE_BASELINE.json'
FEATURES=['SPM','min_rod_weight','max_rod_weight','dynamometer_area']

def main():
    d=pd.read_csv(SOURCE)
    d=d[d.well_type.eq('sucker_rod_pump')]
    wide=d.pivot(index=['well_id','timestamp'],columns='parameter',values='value').reset_index()
    complete=wide.dropna(subset=FEATURES+['pump_fillage']).copy()
    quality=complete['SPM'].gt(0)&complete['dynamometer_area'].ge(0)&complete['pump_fillage'].between(0,100)
    filtered=complete[quality]
    wells=sorted(filtered.well_id.unique())
    runs=[]
    for test_well in wells:
        train=filtered[filtered.well_id.ne(test_well)]
        test=filtered[filtered.well_id.eq(test_well)]
        if len(train)<50 or len(test)<20:continue
        xtr=train[FEATURES].to_numpy(dtype=float);xte=test[FEATURES].to_numpy(dtype=float)
        ytr=train.pump_fillage.to_numpy(dtype=float);yte=test.pump_fillage.to_numpy(dtype=float)
        mean=xtr.mean(axis=0);std=xtr.std(axis=0);std[std==0]=1
        a=np.column_stack((np.ones(len(xtr)),(xtr-mean)/std))
        b=np.column_stack((np.ones(len(xte)),(xte-mean)/std))
        penalty=np.diag([0,1,1,1,1])
        coefficients=np.linalg.solve(a.T@a+penalty,a.T@ytr)
        pred=np.clip(b@coefficients,0,100)
        baseline=np.full_like(yte,ytr.mean())
        mae=float(np.mean(np.abs(pred-yte)))
        base_mae=float(np.mean(np.abs(baseline-yte)))
        variance=float(np.sum((yte-yte.mean())**2))
        r2=float(1-np.sum((yte-pred)**2)/variance) if variance>0 else None
        runs.append(dict(held_out_well=test_well,train_rows=len(train),test_rows=len(test),
                         target_mean=float(yte.mean()),ridge_mae_percentage_points=mae,
                         train_mean_mae_percentage_points=base_mae,ridge_r2=r2))
    result=dict(task='provider-reported hourly pump fillage estimation',validation='leave-one-whole-well-out',
        target_status='provider estimate; not independent measured fillage or fault truth',
        features=FEATURES,complete_rows=len(complete),quality_filtered_rows=len(filtered),
        excluded_rows=len(complete)-len(filtered),wells=wells,per_well=runs,
        unweighted_mean_mae=float(np.mean([r['ridge_mae_percentage_points'] for r in runs])) if runs else None,
        unweighted_mean_baseline_mae=float(np.mean([r['train_mean_mae_percentage_points'] for r in runs])) if runs else None,
        model='ridge linear regression, penalty 1 on standardized features; fit on training wells only',
        deployment='NOT_READY',production_fault_model_changed=False)
    OUT.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
