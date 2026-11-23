"""Prove source-bus privacy and model invariance to state/identity metadata."""
import csv,importlib.util,io,json,os,re,tempfile
from pathlib import Path
import joblib,numpy as np
from context import ROOT,SIM
from shared.contracts import Well,Rod,Sample
from shared.telemetry_privacy import assert_label_blind
from fault_injection.scenarios import Fault
from fault_detection.contour import predict

spec=importlib.util.spec_from_file_location('twin_server',SIM/'backend/server.py')
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
class Capture:
    def __init__(self):self.messages=[]
    def append(self,messages,delay_s=0):self.messages.extend(messages)
with tempfile.TemporaryDirectory(prefix='srp-blind-test-') as folder:
    run=server.Run(Well(asset_id='BLIND',rods=[Rod(length_m=450,diameter_m=.0222)]),1,Path(folder),'Prairie')
    run.engine.fault=Fault(kind='traveling_valve_leak',severity=.7,onset_s=run.engine.time,ramp_s=0)
    os.environ['PUBLISH_TRUTH']='1'
    capture=Capture();truth=io.StringIO();run.sample(capture,truth)
    assert 'traveling_valve_leak' in truth.getvalue()
    for topic,payload,_ in capture.messages:
        assert 'ground_truth' not in topic
        assert_label_blind(payload)
        assert 'traveling_valve_leak' not in json.dumps(payload)
        assert re.fullmatch('[0-9a-f]{32}',payload['run_id'])
        if topic.endswith('telemetry/dynamometer'):Sample.model_validate(payload)
    assert capture.messages
for payload in ({'state_id':'STATE-1'},{'nested':{'fault_name':'GAS'}},{'scenario':'anything'}):
    try:assert_label_blind(payload)
    except ValueError:pass
    else:raise AssertionError('fault metadata was permitted')
source=ROOT.parent/'DH_IMG_PREDICTION_ML_DATASET'
row=next(csv.DictReader((source/'DOWNHOLE_CARD_COORDINATES.csv').open()))
def values(key,scale):return [float(v)*scale for v in row[key].split(';')]
card=dict(quality='GOOD',source='SIMULATOR',
    surface_resampled=dict(position_m=values('raw_surface_pos_in_100',.0254),load_n=values('raw_surface_load_lbf_100',4.4482216152605)),
    downhole=dict(status='SOLVED',solver_quality={'status':'VALID'},position_m=values('raw_downhole_pos_in_100',.0254),load_n=values('raw_downhole_load_lbf_100',4.4482216152605)))
artifact=joblib.load(ROOT/'data/training/downhole_contour.joblib')
first=predict(artifact,card)
changed=dict(card,asset_id='OTHER',well_id='SECRET',state_id='STATE-999',fault_class_name='INVENTED',fault_severity=1,run_id='state-name')
changed['downhole']=dict(card['downhole'],features={'fault_name':'FORBIDDEN_IF_PUBLISHED'})
second=predict(artifact,changed)
assert first['candidate_scores']==second['candidate_scores']
result=dict(source_messages_checked=len(capture.messages),ground_truth_confined_to_local_output=True,
    opaque_run_ids=True,forbidden_metadata_rejected=True,model_metadata_invariance=True,
    feature_contract=artifact['metadata']['feature_contract'],passed=True)
(ROOT/'reports/BLIND_TELEMETRY_ML_CHECKS.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
