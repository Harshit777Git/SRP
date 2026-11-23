"""Verify running fleet APIs, MQTT receipt and fleet pause/resume behavior."""
import json
import math
import time
from collections import defaultdict
from urllib.request import Request,urlopen
from context import ROOT
from shared.mqtt import client
from shared.contracts import Sample

def api(port,path,body=None):
    req=Request(f'http://127.0.0.1:{port}/{path}',data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=30) as response:return json.load(response)

def main():
    entries=json.loads((ROOT/'config/fleet/dataset_120_calibrated.json').read_text())['wells']
    expected={e['well']['asset_id'] for e in entries}
    deadline=time.monotonic()+900
    while True:
        try:
            if api(8001,'health').get('connected') and len(api(8001,'fleet')['wells'])==120:break
        except Exception:pass
        if time.monotonic()>deadline:raise TimeoutError('Live fleet startup did not finish')
        time.sleep(2)
    counts=defaultdict(lambda:defaultdict(int));errors=[];sequences=defaultdict(list)
    c=client('dataset-live-audit')
    def received(conn,u,m):
        try:
            parts=m.topic.split('/');asset=parts[2];stream='/'.join(parts[3:]);payload=json.loads(m.payload)
            if asset not in expected:return
            counts[asset][stream]+=1
            if stream=='telemetry/dynamometer':
                s=Sample.model_validate(payload);sequences[asset].append(s.sequence)
            for value in payload.values():
                if isinstance(value,(int,float)) and not math.isfinite(value):raise ValueError('nonfinite value')
        except Exception as error:errors.append(str(error))
    c.on_message=received;c.connect('127.0.0.1',18883);c.loop_start()
    c.subscribe('srp/v1/#',qos=1)
    try:
        fleet=api(8001,'fleet');running={w['asset_id'] for w in fleet['wells'] if w['mode']=='running'}
        deadline=time.monotonic()+180
        required={'telemetry/dynamometer','telemetry/electrical','telemetry/pressure','events/stroke'}
        while time.monotonic()<deadline and not all(required<=set(counts[a]) for a in expected):time.sleep(1)
        pause=api(8001,'fleet/pause',{})
        paused=all(w['mode']=='paused' for w in api(8001,'fleet')['wells'])
        stop_start=[]
        for field in sorted({w['site_id'] for w in fleet['wells']}):
            asset=next(e['well']['asset_id'] for e in entries if e['site_id']==field and e['provenance']['fault']=='Normal Operation')
            stopped=api(8001,f'assets/{asset}/stop',{})
            started=api(8001,f'assets/{asset}/start',{})
            stop_start.append(dict(field=field,asset_id=asset,stopped=stopped['mode']=='stopped',restarted=started['mode']=='running'))
        resume=api(8001,'fleet/resume',{})
        resumed=all(w['mode']=='running' for w in api(8001,'fleet')['wells'])
        delivery=[]
        for _ in range(6):
            time.sleep(5)
            h=api(8001,'health')
            delivery.append({k:v for k,v in h.items() if k!='topics'})
        apm=api(8002,'fleet');apm_seen={w['asset_id'] for w in apm['wells'] if w['last_sample']}
        final_fleet={w['asset_id']:w for w in api(8001,'fleet')['wells']}
        sequence_lag={w['asset_id']:(max(0,final_fleet[w['asset_id']]['latest_sequence']-w['latest_sequence'])
            if w.get('run_id')==final_fleet[w['asset_id']]['run_id'] and w['latest_sequence'] is not None else None)
            for w in apm['wells'] if w['asset_id'] in expected}
        result=dict(expected_wells=len(expected),default_running=len(running),all_default_running=running==expected,
            wells_with_required_mqtt_streams=sum(required<=set(counts[a]) for a in expected),
            mqtt_counts={a:dict(counts[a]) for a in sorted(expected)},pause_verified=paused,resume_verified=resumed,stop_restart_checks=stop_start,
            apm_wells_receiving=len(expected&apm_seen),subscriber_sequence_lag=sequence_lag,publisher=api(8001,'health'),subscriber=api(8002,'health'),delivery_observations=delivery,errors=errors)
        result['passed']=result['all_default_running'] and result['wells_with_required_mqtt_streams']==120 and paused and resumed and all(r['stopped'] and r['restarted'] for r in stop_start) and len(expected&apm_seen)==120 and not errors
        result['delivery_latency_passed']=all(h['ack_lag_s']<5 and h['dropped']==0 for h in delivery)
        limits={e['well']['asset_id']:5*e['well'].get('dynamometer_hz',50) for e in entries}
        result['subscriber_latency_passed']=len(sequence_lag)==120 and all(v is not None and v<=limits[a] for a,v in sequence_lag.items())
        result['passed']=result['passed'] and result['delivery_latency_passed'] and result['subscriber_latency_passed']
        (ROOT/'reports/DATASET_120_LIVE_VERIFICATION.json').write_text(json.dumps(result,indent=2))
        summary={k:v for k,v in result.items() if k not in ('mqtt_counts','publisher')}
        summary['publisher']={k:v for k,v in result['publisher'].items() if k!='topics'}
        print(json.dumps(summary,indent=2))
    finally:c.disconnect();c.loop_stop()

if __name__=='__main__':main()
