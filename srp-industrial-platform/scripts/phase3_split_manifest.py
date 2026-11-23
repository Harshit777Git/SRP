"""Reserve complete fictional well configurations; no model training."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "config/fleet/us_srp_30_wells.json"
fleet = json.loads(source.read_text())["wells"]
splits = {"future_train": [], "future_calibration": [], "held_out_well": []}
for site in sorted({x["site_id"] for x in fleet}):
    wells = sorted(x["well"]["asset_id"] for x in fleet if x["site_id"] == site)
    assert len(wells) == 5
    splits["future_train"].extend(wells[:3])
    splits["future_calibration"].append(wells[3])
    splits["held_out_well"].append(wells[4])
sets = [set(x) for x in splits.values()]
assert len(set.union(*sets)) == 30 and all(not (a & b) for i,a in enumerate(sets) for b in sets[i+1:])
manifest = dict(schema_version="phase3.1", status="PREPARED_NOT_TRAINED",
                configuration_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                split_unit="complete_virtual_well_configuration", splits=splits,
                scenario_coverage="ONLY_ONE_HEALTHY_STROKE_PER_WELL_GENERATED",
                ood_fault_scenarios="NOT_GENERATED", adjacent_stroke_leakage="NOT_APPLICABLE_SINGLE_STROKE")
path = ROOT / "data/evaluation/phase3/future_split_manifest.json"
path.write_text(json.dumps(manifest, indent=2) + "\n")
print(path)
