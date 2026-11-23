"""Collect fixed-volume, explicitly synthetic simulator data per fault mechanism."""
import copy,hashlib,json,math,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/srp-simulator'),str(ROOT/'apps/srp-apm')]
from physics.engine import Engine, PHYSICS_MODEL_VERSION
from fault_injection.scenarios import Fault
from shared.contracts import Well
from virtual_sensors.sampling import Sensors
from stroke_processing.cards import build

FAULTS=['healthy','incomplete_fillage','gas_interference','traveling_valve_leak','standing_valve_leak','rod_friction','pump_wear','restricted_inflow','load_cell_drift','position_sensor_fault','abnormal_speed']
SEVERITIES=(.1,.2,.4,.6,.8,1.)
N=3129  # telemetry samples per mechanism; not strokes or independent runs
OUT=ROOT/'data/generated/fault_training_candidate_3129_each_v4'

def main():
 fleet=json.loads((ROOT/'config/fleet/us_srp_30_wells.json').read_text())['wells']; OUT.mkdir(parents=True,exist_ok=True)
 # Warm each physical configuration once, then clone that healthy equilibrium
 # for independent fault/severity runs. This preserves warm-up physics without
 # repeating five expensive cycles for every case.
 baseline_engines={}
 for entry in fleet:
  well=Well.model_validate(entry['well'])
  baseline_engines[well.asset_id]=Engine(well)
  print('warmed baseline',well.asset_id,flush=True)
 telemetry=[];aux=[];truth=[];cards=[];runs=[];card_errors=[]
 for fi,kind in enumerate(FAULTS):
  remaining=N;case=0
  while remaining > 0:
   entry=fleet[(fi*len(SEVERITIES)+case)%len(fleet)]; well=Well.model_validate(entry['well'])
   severity=0. if kind=='healthy' else SEVERITIES[case%len(SEVERITIES)]
   effective_spm=well.spm*(1+.35*severity if kind=='abnormal_speed' else 1.)
   minimum_card_samples=math.ceil(well.dynamometer_hz*60/effective_spm)+2
   count=max(min(remaining,math.ceil(N/len(SEVERITIES))),minimum_card_samples)
   run=f'phase32-fault-v4-{kind}-case{case:02d}-{well.asset_id}'
   # Engine.__init__ already performs five healthy warm-up cycles.
   engine=copy.deepcopy(baseline_engines[well.asset_id])
   engine.fault=Fault(kind=kind,severity=severity,ramp_s=0,onset_s=engine.time,duration_s=1e6)
   sensors=Sensors(engine,run,datetime(2026,11,17,tzinfo=timezone.utc)+timedelta(seconds=fi*10000+case*100))
   sensors.site_id=entry['site_id'];previous=[]
   emitted=0
   while emitted<count:
    state=engine.advance(1/well.dynamometer_hz);sample,boundary=sensors.read(state)
    if sample:
     row=sample.model_dump(mode='json');telemetry.append(row)
     emitted+=1
     truth.append(dict(asset_id=well.asset_id,site_id=entry['site_id'],run_id=run,sequence=sample.sequence,stroke_id=sample.stroke_id,timestamp=sample.timestamp.isoformat(),
       fault_mechanism=kind,severity=severity,physics_model_version=PHYSICS_MODEL_VERSION,
       true_pump_position_m=state['pump_position_m'],true_pump_load_n=state['pump_load_n'],
       pump_clearance_m=state['pump_clearance_m'],plunger_slippage_m3_s=state['plunger_slippage_m3_s'],
       chamber_pa=state['chamber_pa'],intake_pa=state['intake_pa'],motor_current_a=state['current_a'],delivered_m3=state['net_delivered_m3']))
     aux.append(dict(asset_id=well.asset_id,run_id=run,sequence=sample.sequence,timestamp=sample.timestamp.isoformat(),
       motor_rpm=state['motor_rpm'],voltage_v=state['voltage_v'],current_a=state['current_a'],power_w=state['power_w'],
       gearbox_torque_nm=state['gearbox_torque_nm'],tubing_pa=state['tubing_pa'],casing_pa=state['casing_pa'],
       intake_pa=state['intake_pa'],net_delivered_m3=state['net_delivered_m3']))
     previous.append(sample)
    if boundary and previous and sample:
     try:
      if previous[0].sample_index==0:
       card=build(previous[:-1],sample,well)
       if card: cards.append(dict(card,synthetic_fault_mechanism=kind,synthetic_severity=severity,
                                 physics_model_version=PHYSICS_MODEL_VERSION,case_id=run))
     except Exception as e: card_errors.append(dict(run_id=run,error=repr(e)))
     previous=[sample]
   runs.append(dict(run_id=run,asset_id=well.asset_id,site_id=entry['site_id'],mechanism=kind,severity=severity,samples=count))
   remaining-=count;case+=1
   print(kind,'case_complete',case,'telemetry_rows',count,'cards_so_far',len(cards),flush=True)
  print(kind,'telemetry_rows',sum(x['samples'] for x in runs if x['mechanism']==kind),
       'independent_runs',sum(x['mechanism']==kind for x in runs),flush=True)
 def write(name,rows):
  p=OUT/name;p.write_text(''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows),encoding='utf8');return p
 ps=[write('ml_inputs_telemetry.jsonl',telemetry),write('ml_inputs_auxiliary.jsonl',aux),write('simulation_truth_labels.jsonl',truth),write('surface_downhole_cards.jsonl',cards)]
 manifest=dict(dataset_id='phase32-fault-training-candidate-3129-each-v4',origin='SYNTHETIC_SIMULATOR',training_use='SYNTHETIC_EXPERIMENTS_ONLY',field_validated=False,
   physics_model_version=PHYSICS_MODEL_VERSION,
   mechanisms=FAULTS,target_telemetry_samples_per_mechanism=N,target_is_minimum=True,
   actual_telemetry_samples_per_mechanism={k:sum(t['fault_mechanism']==k for t in truth) for k in FAULTS},
   target_independent_strokes_per_mechanism=None,
   independent_runs_per_mechanism={k:sum(r['mechanism']==k for r in runs) for k in FAULTS},
   completed_cards_per_mechanism={k:sum(c.get('synthetic_fault_mechanism')==k for c in cards) for k in FAULTS},
   # Backward-compatible field names remain, explicitly mirrored from telemetry row counts.
   target_samples_per_mechanism=N,actual_samples_per_mechanism={k:sum(t['fault_mechanism']==k for t in truth) for k in FAULTS},
   total_samples=len(telemetry),wells=sorted({t['asset_id'] for t in telemetry}),runs=runs,cards=len(cards),
   card_build_errors=card_errors,
   solved_downhole_cards=sum(c.get('downhole',{}).get('status')=='SOLVED' for c in cards),
   configured_severity_values=list(SEVERITIES),
   severity_values=sorted({r['severity'] for r in runs}),
   severity_values_by_mechanism={k:sorted({r['severity'] for r in runs if r['mechanism']==k}) for k in FAULTS},
   provenance='Generated by Engine + virtual Sensors; labels from injected simulation Fault, not field diagnosis. Counts are telemetry rows; cards and independent runs are reported separately.',
   files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ps})
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in manifest.items() if k!='runs'},indent=2))
if __name__=='__main__':main()
