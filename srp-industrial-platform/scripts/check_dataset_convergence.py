"""Compare two integration time steps for one representative well per field."""
import json
import numpy as np
from context import ROOT
from shared.contracts import Well
from physics.engine import Engine

fleet=json.loads((ROOT/'config/fleet/dataset_120_calibrated.json').read_text())['wells']
reports=[]
for field in sorted({e['site_id'] for e in fleet}):
    config=next(e['well'] for e in fleet if e['site_id']==field)
    curves=[]
    for step in (.002,.001):
        e=Engine(Well.model_validate(dict(config,physics_step_s=step)))
        states=[e.advance(60/e.well.spm/100) for _ in range(100)]
        curves.append(np.array([[s['load_n'],s['pump_position_m'],s['pump_load_n']] for s in states]))
    diff=np.sqrt(np.mean((curves[0]-curves[1])**2,axis=0))
    scale=np.maximum(np.ptp(curves[1],axis=0),[1,1e-4,1])
    reports.append(dict(field=field,asset_id=config['asset_id'],range_normalized_rmse=dict(zip(['surface_load','pump_position','pump_load'],(diff/scale).tolist())),passed=bool(np.all(diff/scale<.05))))
    print(reports[-1],flush=True)
(ROOT/'reports/DATASET_120_CONVERGENCE.json').write_text(json.dumps(reports,indent=2))
