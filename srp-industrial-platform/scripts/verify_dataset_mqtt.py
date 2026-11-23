"""Exercise each well and supported fault through real loopback MQTT QoS 1."""
import copy
import json
import math
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import get_args
from context import ROOT
from shared.contracts import Well, Sample
from shared.mqtt import client
from physics.engine import Engine
from fault_injection.scenarios import Fault, FaultName
from virtual_sensors.sampling import Sensors

def simulate(entry):
    well=Well.model_validate(entry['well']); base=Engine(well); cases=[]
    for kind in get_args(FaultName):
        e=copy.deepcopy(base)
        e.fault=Fault(kind=kind,severity=0 if kind=='healthy' else .7,onset_s=e.time,duration_s=1000,ramp_s=0)
        sensors=Sensors(e,f'verify-{well.asset_id}-{kind}'); sensors.site_id=entry['site_id']
        samples=[]; powers=[]
        for _ in range(100):
            state=e.advance(60/well.spm/100)
            assert all(math.isfinite(v) for v in state.values() if isinstance(v,(int,float)))
            assert state['power_w']<=math.sqrt(3)*state['voltage_v']*state['current_a']+1e-6
            sample,_=sensors.read(state); Sample.model_validate(sample.model_dump())
            samples.append(sample.model_dump(mode='json'));powers.append(state['power_w'])
        cases.append(dict(kind=kind,samples=samples,power_w_range=[min(powers),max(powers)]))
    return dict(asset_id=well.asset_id,cases=cases)

def main():
    fleet=json.loads((ROOT/'config/fleet/dataset_120_calibrated.json').read_text())['wells']
    port=18984; env=dict(os.environ,MQTT_PORT=str(port))
    log=(ROOT/'state/dataset_verification_broker.log').open('w')
    broker=subprocess.Popen(['C:/Program Files/nodejs/node.exe','scripts/test_broker.mjs'],cwd=ROOT,env=env,stdout=log,stderr=log)
    received={}; errors=[]
    subscriber=client('dataset-verification-sub'); publisher=client('dataset-verification-pub')
    def message(c,u,m):
        try:
            value=json.loads(m.payload); s=Sample.model_validate(value)
            received.setdefault(s.run_id,set()).add(s.sequence)
        except Exception as error: errors.append(str(error))
    subscriber.on_message=message
    try:
        time.sleep(1)
        subscriber.connect('127.0.0.1',port);subscriber.loop_start()
        subscriber.subscribe('srp/v1/+/telemetry/dynamometer',qos=1)
        publisher.connect('127.0.0.1',port);publisher.loop_start();time.sleep(.5)
        results=[]
        with ProcessPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(simulate,e) for e in fleet]):
                result=future.result()
                for case in result['cases']:
                    for s in case.pop('samples'):
                        receipt=publisher.publish(f'srp/v1/{s["asset_id"]}/telemetry/dynamometer',json.dumps(s),qos=1)
                        receipt.wait_for_publish(timeout=10)
                        if not receipt.is_published(): raise TimeoutError('MQTT publish acknowledgement missing')
                    run=f'verify-{result["asset_id"]}-{case["kind"]}'
                    deadline=time.monotonic()+10
                    while len(received.get(run,set()))<100 and time.monotonic()<deadline: time.sleep(.01)
                    case['received_unique_samples']=len(received.get(run,set()))
                    case['pass']=case['received_unique_samples']==100
                results.append(result)
                report=dict(wells=len(results),supported_conditions=list(get_args(FaultName)),results=results,errors=errors,
                    passed=not errors and all(c['pass'] for r in results for c in r['cases']))
                (ROOT/'reports/DATASET_120_MQTT_VERIFICATION.json').write_text(json.dumps(report,indent=2))
                print(f'{len(results)}/120 wells: {result["asset_id"]} 11 conditions received',flush=True)
        assert report['passed'] and len(results)==120
    finally:
        publisher.disconnect();subscriber.disconnect();publisher.loop_stop();subscriber.loop_stop();broker.terminate();broker.wait();log.close()

if __name__=='__main__':main()
