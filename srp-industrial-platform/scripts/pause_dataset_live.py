import json,time
from context import ROOT
from verify_live_dataset_fleet import api
path=ROOT/'reports/DATASET_120_LIVE_VERIFICATION.json'
if path.exists():
    report=json.loads(path.read_text());report['delivery_latency_passed']=report['publisher']['ack_lag_s']<5 and report['publisher']['dropped']==0
    report['passed']=report['passed'] and report['delivery_latency_passed']
    (ROOT/'reports/DATASET_120_LIVE_BASELINE.json').write_text(json.dumps(report,indent=2))
print(api(8001,'fleet/pause',{}),flush=True)
deadline=time.monotonic()+120
while time.monotonic()<deadline:
    health=api(8001,'health');print('Durable messages awaiting broker ACK:',health['queued'],flush=True)
    if health['queued']==0:break
    time.sleep(5)
