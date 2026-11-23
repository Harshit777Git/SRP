"""Freeze geometry-grouped partitions before candidate selection."""
import hashlib,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    source=ROOT/'config/fleet/us_srp_30_wells.json'
    ignored={'asset_id','seed','noise_position_m','noise_load_n','position_bias_m','load_bias_n',
             'sensor_latency_s','missing_probability','physics_step_s','dynamometer_hz','electrical_hz','pressure_hz'}
    groups={}
    for entry in json.loads(source.read_text())['wells']:
        well=entry['well']
        signature={k:v for k,v in well.items() if k not in ignored}
        key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
        groups.setdefault(key,[]).append(well['asset_id'])
    keys=sorted(groups);random.Random(73129).shuffle(keys)
    train_end=int(len(keys)*.6);cal_end=int(len(keys)*.8)
    split={name:[asset for key in subset for asset in groups[key]] for name,subset in
           [('train',keys[:train_end]),('validation',keys[train_end:cal_end]),('test',keys[cal_end:])]}
    assert all(split.values())
    assert not(set(split['train'])&set(split['test']) or set(split['validation'])&set(split['test']))
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                origin='SYNTHETIC',seed=73129,partitions=split,physical_configuration_groups=groups,
                policy='All strokes and severity variants from a configuration stay together. Test partition must not guide model selection.',
                limitation='Fleet configurations have previously informed simulator development; this is not an independent field evaluation.')
    path=ROOT/'data/evaluation/balanced_frozen_split.json'
    if path.exists():
        assert json.loads(path.read_text())==report,'Refusing to change frozen split'
    else:path.write_text(json.dumps(report,indent=2))
    print({k:len(v) for k,v in split.items()},'physical groups',len(groups))
if __name__=='__main__':main()
