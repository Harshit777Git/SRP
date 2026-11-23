import hashlib
import json
from collections import Counter
from context import ROOT

path=ROOT/'config/fleet/dataset_120_calibrated.json'
fleet=json.loads(path.read_text());fits=json.loads((ROOT/'reports/DATASET_120_LOAD_FIT.json').read_text())
assert len(fits)==120
by_id={r['asset_id']:r for r in fits}
for entry in fleet['wells']:
    entry['calibration_result']=by_id[entry['well']['asset_id']]
    entry['well'].update(dynamometer_hz=20,electrical_hz=5,pressure_hz=1)
fleet['sampling_policy']='20 Hz dynamometer; 5 Hz electrical; 1 Hz pressure; unchanged 2 ms physics ceiling'
fleet['source_sha256']=hashlib.sha256((ROOT.parent/'DIGITAL_TWIN_DATASET/MASTER_120_WELLS_CONFIGURATION.csv').read_bytes()).hexdigest()
fleet['accepted_wells']=sum(r['accepted'] for r in fits)
fleet['unmodeled_source_conditions']=dict(Counter(r['source_condition'] for r in fits if not r['condition_supported']))
path.write_text(json.dumps(fleet,indent=2))
print(json.dumps({k:v for k,v in fleet.items() if k!='wells'},indent=2))
