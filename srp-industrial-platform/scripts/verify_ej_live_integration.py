"""Validate actual MQTT-acquired cards, engineering units and blind-model wiring."""
import json,math,time
from collections import Counter
from urllib.request import urlopen
from urllib.parse import urlencode
import numpy as np
from context import ROOT
from shared.contracts import Well,LBF,INCH,Sample,GRAVITY
from shared.telemetry_privacy import assert_label_blind

def get(port,route):
    with urlopen(f'http://127.0.0.1:{port}/{route}',timeout=30) as response:return json.load(response)

deadline=time.monotonic()+900
while True:
    try:
        if get(8001,'health').get('connected') and get(8002,'health').get('ready'):break
    except Exception:pass
    if time.monotonic()>deadline:raise TimeoutError('runtime not ready')
    time.sleep(2)
fleet=get(8001,'fleet');results=[]
for entry in fleet['wells']:
    asset=entry['asset_id'];deadline=time.monotonic()+90;card=None
    while time.monotonic()<deadline:
        snapshot=get(8002,'snapshot?'+urlencode({'asset':asset}));card=snapshot.get('card')
        if card and card['downhole']['status']=='SOLVED':break
        time.sleep(.5)
    assert card and card['downhole']['status']=='SOLVED',asset
    s=card['surface'];d=card['downhole'];features=d['features'];well=Well.model_validate(card['asset_configuration'])
    assert d['solver_version']=='EJ-spatial-FD/3.0' and d['verification_version']=='Gibbs-harmonic/2.0'
    for sample in snapshot['live']:
        assert_label_blind(sample);Sample.model_validate(sample)
    x=np.asarray(s['position_m']);load=np.asarray(s['load_n'])
    area=abs(np.sum((np.roll(x,-1)-x)*(np.roll(load,-1)+load)/2))
    assert abs(s['area_lbf_in']-area/(LBF*INCH))<1e-5
    assert abs(s['pprl_lbf']-load.max()/LBF)<1e-5
    assert abs(s['mprl_lbf']-load.min()/LBF)<1e-5
    dx=np.asarray(d['position_m']);df=np.asarray(d['load_n'])
    assert len(dx)==len(df)==200 and np.isfinite(dx).all() and np.isfinite(df).all()
    assert abs(features['mpt_m']-np.ptp(dx))<1e-8
    expected_fo=(well.tubing_pa-well.casing_pa+well.fluid_kg_m3*GRAVITY*(well.depth-well.intake_head_m))*math.pi*well.plunger_m**2/4
    assert abs(features['fluid_load_fo_n']-expected_fo)<1e-5
    if features['ept_m'] is not None:
        assert 0<=features['ept_m']<=features['mpt_m']
        expected_bpd=math.pi*well.plunger_m**2/4*features['ept_m']*card['spm']*1440/.158987294928
        assert abs(features['displacement_bpd']-expected_bpd)<1e-6
    diagnosis=card['diagnosis']
    result=dict(asset_id=asset,stroke_id=card['stroke_id'],source=card['source'],quality=card['quality'],
        primary=d['solver_version'],verification=d['verification_version'],solver_quality=d['solver_quality']['status'],
        model_version=diagnosis['model_version'],predicted=diagnosis['label'],confidence=diagnosis.get('confidence'),
        displacement_rmse_in=d['displacement_rmse_in'],load_rmse_lbf=d['load_rmse_lbf'],
        transfer_identifiable=features['ept_m'] is not None,configured_limits=s['limits'])
    results.append(result);print(f'{len(results)}/120 {asset}: {result["solver_quality"]} · {result["predicted"]}',flush=True)
    report=dict(wells=len(results),results=results,model_versions=dict(Counter(r['model_version'] for r in results)),
        solver_quality=dict(Counter(r['solver_quality'] for r in results)),passed=len(results)==120,
        checks=['actual MQTT acquisition','paired sample geometry','imperial area/load conversions','fluid-load pressure equation','EPT bounds','BPD dimensional equation','no fault identifiers in input samples'])
    (ROOT/'reports/EJ_GIBBS_LIVE_INTEGRATION.json').write_text(json.dumps(report,indent=2))
assert report['passed']
print('PASS: 120 live surface/downhole cards and engineering measurements')
