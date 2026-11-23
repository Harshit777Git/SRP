"""Resumable synthetic complete-stroke collection, never field ground truth."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'apps/srp-simulator'),str(ROOT/'apps/srp-apm')]
from shared.contracts import Well
from evaluate_wave import cycle, compare
from fault_injection.scenarios import Fault
from generate_fault_training_capture import FAULTS
from physics.engine import PHYSICS_MODEL_VERSION

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runs-per-class',type=int,default=3129,
                        help='complete simulated strokes per mechanism (not telemetry rows)')
    parser.add_argument('--limit-new',type=int)
    parser.add_argument('--output-dir',default='balanced_independent_strokes',
                        help='directory name under data/generated')
    parser.add_argument('--run-version',default='v1')
    args=parser.parse_args()
    if args.runs_per_class<1:parser.error('runs-per-class must be positive')
    if not args.output_dir or Path(args.output_dir).name!=args.output_dir:
        parser.error('output-dir must be one directory name')
    if not args.run_version.replace('_','').replace('-','').isalnum():
        parser.error('run-version must contain only letters, numbers, hyphens or underscores')
    source=ROOT/'config/fleet/us_srp_30_wells.json'
    fleet=json.loads(source.read_text())['wells']
    output=ROOT/'data/generated'/args.output_dir
    output.mkdir(parents=True,exist_ok=True)
    # One JSON file per independent simulation allows recovery without appending
    # partially written rows. Existing records are never overwritten.
    created=0
    for i in range(args.runs_per_class):
        entry=fleet[i%len(fleet)]
        for kind in FAULTS:
            run=f'balanced-{args.run_version}-{kind}-{i:05d}'
            path=output/(run+'.json')
            if path.exists():
                saved=json.loads(path.read_text())
                if saved['run_id']!=run:raise ValueError('existing run identity mismatch')
                continue
            # Rotate after each fleet pass so every geometry eventually sees all
            # severities (30 wells and 9 levels otherwise share a factor of 3).
            severity=0. if kind=='healthy' else (.1,.2,.3,.4,.5,.6,.7,.8,.9,1.)[(i+i//len(fleet))%10]
            well=Well.model_validate(entry['well']).model_copy(update={'seed':104729+i})
            fault=Fault(kind=kind,severity=severity,ramp_s=0,duration_s=1e6)
            card,samples,truth=cycle(well,fault,run_id=run)
            if card['quality']!='GOOD' or card['downhole']['status']!='SOLVED':
                raise RuntimeError(f'{run}: incomplete reconstruction')
            record=dict(run_id=run,origin='SYNTHETIC_SIMULATOR',field_validated=False,
                        physics_model_version=PHYSICS_MODEL_VERSION,
                        mechanism=kind,severity=severity,well=well.model_dump(mode='json'),
                        configuration_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        card=card,telemetry=[s.model_dump(mode='json') for s in samples],
                        simulation_truth=truth,reconstruction_comparison=compare(card,truth),
                        split_group=well.asset_id,
                        limitation='Repeated well configurations and related simulation runs must remain grouped; not independent field wells.')
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(record,allow_nan=False),encoding='utf8')
            temp.replace(path)
            created+=1
            print(run,'samples',len(samples),'severity',severity,flush=True)
            if args.limit_new is not None and created>=args.limit_new:return

if __name__=='__main__':main()
