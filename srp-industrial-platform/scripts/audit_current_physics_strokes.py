"""Verify complete-stroke v2 capture provenance, card integrity and class counts."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/generated/balanced_independent_strokes_v2"
VERSION = "srp-forward-2.0-plunger-clearance"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    files = sorted(DATA.glob("balanced-v2-*.json"))
    counts, severity, wells = Counter(), defaultdict(set), defaultdict(set)
    raw_samples, cards_by_run, duplicates, bad = 0, set(), defaultdict(list), []
    file_hashes = {}
    for path in files:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            assert row["origin"] == "SYNTHETIC_SIMULATOR"
            assert row["field_validated"] is False
            assert row["physics_model_version"] == VERSION
            assert row["run_id"] == row["card"]["run_id"]
            assert row["card"]["quality"] == "GOOD"
            assert row["card"]["identity_consistent"] is True
            assert row["card"]["downhole"]["status"] == "SOLVED"
            assert row["split_group"] == row["well"]["asset_id"]
            assert row["telemetry"]
            assert all(sample["physics_model_version"] == VERSION for sample in row["telemetry"])
            mechanism = row["mechanism"]
            counts[mechanism] += 1
            severity[mechanism].add(row["severity"])
            wells[mechanism].add(row["split_group"])
            raw_samples += len(row["telemetry"])
            assert row["run_id"] not in cards_by_run
            cards_by_run.add(row["run_id"])
            fingerprint = hashlib.sha256(json.dumps(
                row["card"]["surface_resampled"], sort_keys=True).encode()).hexdigest()
            duplicates[fingerprint].append(dict(path=path.name, well=row["split_group"], label=mechanism))
            file_hashes[path.name] = sha256(path)
        except Exception as error:
            bad.append({"file": path.name, "error": repr(error)})

    duplicate_groups = [rows for rows in duplicates.values() if len(rows) > 1]
    expected = {"healthy", "incomplete_fillage", "gas_interference", "traveling_valve_leak",
                "standing_valve_leak", "rod_friction", "pump_wear", "restricted_inflow",
                "load_cell_drift", "position_sensor_fault", "abnormal_speed"}
    report = {
        "dataset_id": "balanced-current-physics-100-cards-per-mechanism-v2",
        "origin": "SYNTHETIC_ONLY",
        "physics_model_version": VERSION,
        "records": len(files),
        "complete_surface_downhole_pairs": sum(counts.values()) - len(bad),
        "raw_telemetry_rows": raw_samples,
        "distinct_virtual_wells": len({w for group in wells.values() for w in group}),
        "cards_per_mechanism": dict(sorted(counts.items())),
        "virtual_wells_per_mechanism": {k: len(v) for k, v in sorted(wells.items())},
        "severity_values_per_mechanism": {k: sorted(v) for k, v in sorted(severity.items())},
        "exact_duplicate_surface_card_groups": len(duplicate_groups),
        "duplicate_groups": duplicate_groups,
        "invalid_records": bad,
        "expected_mechanisms_present": set(counts) == expected,
        "all_records_current_physics": not bad,
        "file_sha256": file_hashes,
        "training_use": "Experimental synthetic-only; injected scenario labels are not field diagnoses.",
        "sensor_noise_calibrated_to_field": False,
        "field_validation": False,
    }
    output = ROOT / "reports/PHASE3_2/CURRENT_PHYSICS_STROKE_AUDIT.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "records", "raw_telemetry_rows", "distinct_virtual_wells", "cards_per_mechanism",
        "exact_duplicate_surface_card_groups", "invalid_records", "all_records_current_physics")}, indent=2))
    if bad or set(counts) != expected or any(value != 100 for value in counts.values()):
        raise SystemExit("Current physics stroke audit failed acceptance checks")


if __name__ == "__main__":
    main()
