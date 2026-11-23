"""Bounded physical parameter fitting, with a separate fifth-stroke evaluation."""
import csv
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from context import ROOT
from shared.contracts import Well,LBF
from physics.engine import Engine
from fault_injection.scenarios import Fault

MAPPING={'Normal Operation':'healthy','Blocked Intake':'restricted_inflow',
 'Gas Interference':'gas_interference','Severe Gas Lock':'gas_interference',
 'High Wellbore Friction':'rod_friction','High Fluid Damping':'rod_friction',
 'Tagging Down Hard':'rod_friction',
 'Standing Valve Leak':'standing_valve_leak','Traveling Valve Leak':'traveling_valve_leak',
 'Worn Pump Barrel':'pump_wear','Fluid Pound':'incomplete_fillage',
 'Unanchored Tubing Slip':'incomplete_fillage'}

def fit(entry):
    asset=entry['well']['asset_id'];field=entry['site_id']
    rows=list(csv.DictReader((ROOT.parent/'DIGITAL_TWIN_DATASET'/field/f'{asset}.csv').open(encoding='utf-8-sig')))
    last=rows[-1]['stroke_id'];train=np.array([r['stroke_id']!=last for r in rows])
    target=np.array([float(r['polished_rod_load_lbf']) for r in rows])
    phase=np.array([int(r['sample_index'])*math.tau/100 for r in rows])
    kind=MAPPING.get(entry['provenance']['fault'])
    severity=float(rows[0]['fault_severity'])
    candidates=[]
    for multiplier in (.6,1.,1.4):
        config=dict(entry['well']);config['damping_s']=min(5,max(.05,config['damping_s']*multiplier))
        e=Engine(Well.model_validate(config))
        e.fault=Fault(kind=kind or 'healthy',severity=severity,onset_s=e.time,duration_s=1e12,ramp_s=0)
        e.advance(60/config['spm']*2)
        states=[e.advance(60/config['spm']/100) for _ in range(100)]
        angles=np.array([s['crank_angle_deg']*math.pi/180 for s in states]);order=np.argsort(angles)
        loads=np.array([s['load_n']/LBF for s in states])
        # Compare periodic phase to source's fitted kinematic phase convention.
        prediction=np.interp((phase+entry['calibration_phase_rad'])%math.tau,angles[order],loads[order],period=math.tau)
        score=float(np.sqrt(np.mean((prediction[train]-target[train])**2)))
        candidates.append((score,config,prediction))
    score,config,prediction=min(candidates,key=lambda c:c[0]);entry['well']=config
    entry['initial_fault']=dict(kind=kind or 'healthy',severity=severity if kind else 0,duration_s=1e12,ramp_s=0)
    rmse=float(np.sqrt(np.mean((prediction[~train]-target[~train])**2)))
    span=float(np.ptp(target[~train]));nrmse=rmse/max(span,1)
    return entry,dict(asset_id=asset,source_condition=entry['provenance']['fault'],condition_supported=kind is not None,
        damping_s=config['damping_s'],train_rmse_lbf=score,holdout_rmse_lbf=rmse,holdout_range_normalized_rmse=nrmse,
        acceptance_threshold=.15,accepted=kind is not None and nrmse<=.15,field_validated=False)

def main():
    path=ROOT/'config/fleet/dataset_120_calibrated.json';fleet=json.loads(path.read_text())
    kine={r['asset_id']:r for r in json.loads((ROOT/'reports/DATASET_120_CALIBRATION.json').read_text())}
    for e in fleet['wells']:e['calibration_phase_rad']=kine[e['well']['asset_id']]['fitted_phase_rad']
    reports=[];entries=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fit,e) for e in fleet['wells']]):
            entry,report=future.result();entries.append(entry);reports.append(report)
            (ROOT/'reports/DATASET_120_LOAD_FIT.json').write_text(json.dumps(reports,indent=2))
            print(f'{len(entries)}/120 {report["asset_id"]}: holdout NRMSE {report["holdout_range_normalized_rmse"]:.3f}, accepted={report["accepted"]}',flush=True)
    fleet['wells']=sorted(entries,key=lambda e:e['well']['asset_id']);fleet['calibration']='bounded damping fit; acceptance in DATASET_120_LOAD_FIT.json'
    path.write_text(json.dumps(fleet,indent=2))

if __name__=='__main__':main()
