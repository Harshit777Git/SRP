"""Paired synthetic signal differences; not a detection-accuracy estimate."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/generated/balanced_independent_strokes'

def main():
    rows=[json.loads(p.read_text()) for p in sorted(DATA.glob('*.json'))]
    healthy={r['run_id'].rsplit('-',1)[1]:r for r in rows if r['mechanism']=='healthy'}
    output=[]
    for row in rows:
        if row['mechanism']=='healthy':continue
        reference=healthy.get(row['run_id'].rsplit('-',1)[1])
        if reference is None:continue
        assert row['well']==reference['well'], 'unmatched equipment or noise seed'
        a=row['card']['surface_resampled'];b=reference['card']['surface_resampled']
        dx=np.asarray(a['position_m'])-np.asarray(b['position_m'])
        df=np.asarray(a['load_n'])-np.asarray(b['load_n'])
        load_noise=row['well']['noise_load_n'];position_noise=row['well']['noise_position_m']
        load_rms=float(np.sqrt(np.mean(df**2)));position_rms=float(np.sqrt(np.mean(dx**2)))
        output.append(dict(run_id=row['run_id'],mechanism=row['mechanism'],severity=row['severity'],
            asset_id=row['well']['asset_id'],load_difference_rms_n=load_rms,
            position_difference_rms_m=position_rms,
            configured_load_noise_std_n=load_noise,configured_position_noise_std_m=position_noise,
            load_difference_over_noise=load_rms/load_noise if load_noise>0 else None,
            position_difference_over_noise=position_rms/position_noise if position_noise>0 else None))
    report=dict(origin='PAIRED_SYNTHETIC_DIFFERENCES',pairs=len(output),
        limitations=['Same seed pairs suppress some random variability; ratios are descriptive, not statistical detection power.',
                     'SPM changes alter sample counts and noise alignment.',
                     'One run per severity in the pilot cannot establish recall or false alarm rates.'],results=output)
    (ROOT/'reports/PHASE3_2/FAULT_OBSERVABILITY_PILOT.json').write_text(json.dumps(report,indent=2))
    for r in output:
        if r['severity']==.001:print(r['mechanism'], 'load RMS N',round(r['load_difference_rms_n'],4),
                                     'position RMS m',round(r['position_difference_rms_m'],7))

if __name__=='__main__':main()
