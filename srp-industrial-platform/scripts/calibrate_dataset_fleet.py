"""Fit kinematics on four strokes; evaluate the fifth and forward physics independently."""
import csv
import json
import math
import sys
import numpy as np
from scipy.optimize import least_squares
from context import ROOT
from shared.contracts import Well, INCH, LBF
from physics.engine import Engine, Mechanism

path=ROOT/'config/fleet/dataset_120_wells.json'
fleet=json.loads(path.read_text())
results=[]
for index,entry in enumerate(fleet['wells']):
    config=entry['well']; asset=config['asset_id']
    field=asset.split('-')[0].title()
    rows=list(csv.DictReader((ROOT.parent/'DIGITAL_TWIN_DATASET'/field/f'{asset}.csv').open(encoding='utf-8-sig')))
    # Per-well files can include configuration columns; telemetry names are authoritative.
    positions=np.array([float(r['polished_rod_position_in'])*INCH for r in rows])
    indices=np.array([int(r['sample_index']) for r in rows])
    strokes=list(dict.fromkeys(r['stroke_id'] for r in rows))
    train=np.array([r['stroke_id']!=strokes[-1] for r in rows])
    phase=indices*math.tau/(indices.max()+1)
    w=Well.model_validate(config); motion=Mechanism(w)
    def predict(p):
        return np.array([motion.position(float(a+p[0]))/w.stroke_m*p[1]+p[2] for a in phase])
    candidates=[least_squares(lambda p:(predict(p)-positions)[train], [a,w.stroke_m,0],
        bounds=([-math.tau,.5,-.1],[math.tau,4,.1]),max_nfev=50) for a in (-math.pi,0,math.pi)]
    fit=min(candidates,key=lambda r:np.sum(r.fun**2)); prediction=predict(fit.x)
    config['stroke_m']=float(fit.x[1]);config['position_bias_m']=float(fit.x[2])
    # Phase alignment is an evaluation parameter, never a hidden load correction.
    engine=Engine(Well.model_validate(config));states=[]
    for _ in range(100): states.append(engine.advance(60/config['spm']/100))
    finite=all(math.isfinite(v) for s in states for v in s.values() if isinstance(v,(int,float)))
    pf=[s['power_w']/(math.sqrt(3)*s['voltage_v']*s['current_a']) for s in states]
    result=dict(asset_id=asset,train_strokes=len(strokes)-1,test_strokes=1,
        kinematic_train_rmse_m=float(np.sqrt(np.mean((prediction[train]-positions[train])**2))),
        kinematic_test_rmse_m=float(np.sqrt(np.mean((prediction[~train]-positions[~train])**2))),
        fitted_phase_rad=float(fit.x[0]),fitted_stroke_m=config['stroke_m'],
        finite_forward_physics=finite,power_factor_range=[min(pf),max(pf)],
        forward_load_range_lbf=[min(s['load_n']/LBF for s in states),max(s['load_n']/LBF for s in states)],
        source_load_range_lbf=[min(float(r['polished_rod_load_lbf']) for r in rows),max(float(r['polished_rod_load_lbf']) for r in rows)],
        status='KINEMATICS_FITTED_PHYSICS_CHECKED',field_validated=False)
    results.append(result)
    print(f'{index+1}/120 {asset}: holdout position RMSE {result["kinematic_test_rmse_m"]:.6f} m',flush=True)
    (ROOT/'reports/DATASET_120_CALIBRATION.json').write_text(json.dumps(results,indent=2))
fleet['calibration']='four-stroke kinematics fit, fifth-stroke holdout; synthetic source'
(ROOT/'config/fleet/dataset_120_calibrated.json').write_text(json.dumps(fleet,indent=2))
