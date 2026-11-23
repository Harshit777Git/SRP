"""Audit completed checkpoints without treating telemetry rows as strokes."""
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    groups=defaultdict(list)
    fingerprints=defaultdict(list)
    for path in sorted((ROOT/'data/generated/balanced_independent_strokes').glob('*.json')):
        row=json.loads(path.read_text())
        assert row['origin']=='SYNTHETIC_SIMULATOR'
        assert row['card']['run_id']==row['run_id']
        assert row['card']['identity_consistent']
        assert row['card']['quality']=='GOOD'
        assert row['card']['downhole']['status']=='SOLVED'
        # Retain only inventory metadata; raw telemetry/truth can be large.
        groups[row['mechanism']].append(dict(run_id=row['run_id'],split_group=row['split_group'],
                                            severity=row['severity'],raw_samples=len(row['telemetry'])))
        signal=json.dumps(row['card']['surface_resampled'],sort_keys=True)
        fingerprints[hashlib.sha256(signal.encode()).hexdigest()].append(row['run_id'])
    result=dict(origin='SYNTHETIC_ONLY',complete_strokes=sum(map(len,groups.values())),
        classes={key:dict(strokes=len(rows),runs=len({r['run_id'] for r in rows}),
                         wells=len({r['split_group'] for r in rows}),
                         severity_counts=dict(Counter(str(r['severity']) for r in rows)),
                         raw_samples=sum(r['raw_samples'] for r in rows)) for key,rows in groups.items()},
        identical_surface_signal_groups=[ids for ids in fingerprints.values() if len(ids)>1],
        field_validation=False)
    out=ROOT/'reports/PHASE3_2/BALANCED_CAPTURE_AUDIT.json'
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
