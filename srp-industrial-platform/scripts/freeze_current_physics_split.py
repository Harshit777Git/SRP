"""Freeze a whole-well split for corrected-physics synthetic candidate work."""
import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Mapping
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/generated/balanced_independent_strokes_v2"
AUDIT = ROOT / "reports/PHASE3_2/CURRENT_PHYSICS_STROKE_AUDIT.json"
OUTPUT = ROOT / "data/evaluation/current_physics_v2_split.json"
SEED = 20261117


def main():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit["invalid_records"] or not audit["expected_mechanisms_present"]:
        raise RuntimeError("Refusing to split an unaudited capture")
    rows = []
    physical_groups = defaultdict(set)
    ignored = {"asset_id", "seed", "noise_position_m", "noise_load_n", "position_bias_m",
               "load_bias_n", "sensor_latency_s", "missing_probability", "physics_step_s",
               "dynamometer_hz", "electrical_hz", "pressure_hz"}
    for path in sorted(DATA.glob("balanced-v2-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        rows.append((path.name, row["split_group"], row["mechanism"]))
        config = {key: value for key, value in row["well"].items() if key not in ignored}
        signature = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        physical_groups[signature].add(row["split_group"])
    wells = sorted({row[1] for row in rows})
    if len(wells) != 30 or len(physical_groups) < 20:
        raise RuntimeError(f"Expected 30 wells and adequate unique physical groups; got {len(wells)} wells, {len(physical_groups)} groups")
    keys = sorted(physical_groups)
    random.Random(SEED).shuffle(keys)
    train_end = int(len(keys)*.6)
    calibration_end = int(len(keys)*.8)
    keys_by_partition = {"train": keys[:train_end], "calibration": keys[train_end:calibration_end],
                         "test": keys[calibration_end:]}
    groups = {name: sorted({well for key in selected for well in physical_groups[key]})
              for name, selected in keys_by_partition.items()}
    membership = {well: name for name, members in groups.items() for well in members}
    per_split = {name: Counter(row[2] for row in rows if membership[row[1]] == name)
                 for name in groups}
    classes = sorted({row[2] for row in rows})
    if any(set(counts) != set(classes) for counts in per_split.values()):
        raise RuntimeError("At least one mechanism is absent from a frozen partition")
    report = {
        "origin": "SYNTHETIC_ONLY",
        "physics_model_version": audit["physics_model_version"],
        "seed": SEED,
        "groups_by_virtual_well": groups,
        "physical_configuration_groups": {key: sorted(value) for key, value in physical_groups.items()},
        "partition_card_counts": {name: dict(sorted(counts.items())) for name, counts in per_split.items()},
        "whole_well_isolation": True,
        "test_used_for_model_selection": False,
        "source_capture_sha256": hashlib.sha256(json.dumps(
            audit["file_sha256"], sort_keys=True).encode()).hexdigest(),
        "policy": "Fit candidate on train wells, choose model on calibration wells, evaluate once on test wells.",
        "limitation": "Virtual wells share a simulator and hand-authored parameter envelope; this does not estimate field generalization.",
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"split_file": str(OUTPUT), "wells": {k: len(v) for k, v in groups.items()},
                      "cards": {k: sum(v.values()) for k, v in per_split.items()}}, indent=2))


if __name__ == "__main__":
    main()
