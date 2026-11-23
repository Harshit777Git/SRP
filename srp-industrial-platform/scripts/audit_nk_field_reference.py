"""Profile the downloaded NK field-claimed summary telemetry without training on it."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/external_reference/nk_well_monitoring/wells_dataset.csv"
OUT = ROOT / "data/evaluation/nk_field_reference_profile.json"
EXPECTED = {"well_id", "well_type", "timestamp", "parameter", "value", "unit"}


def quantile(values, probability):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * probability
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def main():
    rows, values, units = 0, defaultdict(list), defaultdict(Counter)
    wells_by_type = defaultdict(set)
    timestamps = defaultdict(list)
    duplicate_keys = Counter()
    with CSV.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != EXPECTED:
            raise ValueError(f"Unexpected columns: {reader.fieldnames}")
        for row in reader:
            rows += 1
            well, kind, parameter = row["well_id"], row["well_type"], row["parameter"]
            try:
                value = float(row["value"])
                timestamp = datetime.fromisoformat(row["timestamp"])
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid value/timestamp on line {reader.line_num}") from error
            key = (well, parameter)
            wells_by_type[kind].add(well)
            values[key].append(value)
            units[(parameter, row["unit"])]["count"] += 1
            timestamps[key].append(timestamp)
            duplicate_keys[(well, parameter, timestamp)] += 1
    per_series = {}
    for (well, parameter), observed in sorted(values.items()):
        times = sorted(timestamps[(well, parameter)])
        gaps = [(later - earlier).total_seconds() / 3600 for earlier, later in zip(times, times[1:])]
        duplicate_count = sum(n - 1 for (w, p, _), n in duplicate_keys.items()
                              if w == well and p == parameter and n > 1)
        per_series[f"{well}|{parameter}"] = {
            "rows": len(observed), "unit": next(unit for (param, unit), c in units.items()
                if param == parameter and c["count"] and unit),
            "start": times[0].isoformat(), "end": times[-1].isoformat(),
            "duplicates": duplicate_count, "interval_hours_median": median(gaps) if gaps else None,
            "interval_hours_max": max(gaps) if gaps else None,
            "gaps_over_1_5h": sum(gap > 1.5 for gap in gaps),
            "minimum": min(observed), "p05": quantile(observed, .05),
            "median": median(observed), "mean": mean(observed),
            "p95": quantile(observed, .95), "maximum": max(observed),
            "std_population": pstdev(observed),
            "negative_values": sum(v < 0 for v in observed),
        }
    by_parameter = {}
    for parameter in sorted({p for _, p in values}):
        combined = [v for (well, p), items in values.items() if p == parameter for v in items]
        by_parameter[parameter] = {"rows": len(combined),
            "wells": sorted(well for well, p in values if p == parameter),
            "units": {unit: count["count"] for (param, unit), count in units.items() if param == parameter},
            "minimum": min(combined), "p05": quantile(combined, .05),
            "median": median(combined), "mean": mean(combined),
            "p95": quantile(combined, .95), "maximum": max(combined),
            "negative_values": sum(v < 0 for v in combined)}
    out = {
        "dataset_id": "nk-hourly-2026",
        "source": "https://huggingface.co/datasets/Arailym-tleubayeva/NK-Oil-Well-Sensor-Monitoring",
        "origin": "SOURCE_CLAIMED_FIELD_MEASUREMENTS_NOT_INDEPENDENTLY_VERIFIED",
        "rows": rows, "columns": list(EXPECTED), "well_counts_by_type":
            {kind: len(wells) for kind, wells in wells_by_type.items()},
        "parameter_totals": by_parameter, "well_parameter_series": per_series,
        "global_duplicate_well_parameter_timestamps": sum(n - 1 for n in duplicate_keys.values() if n > 1),
        "fault_labels": 0, "surface_or_downhole_point_arrays": 0,
        "training_status": "NOT_USED_FOR_SUPERVISED_FAULT_TRAINING",
        "allowed_local_use": "Aggregate engineering-envelope audit only, subject to dataset Apache-2.0 license and source-owner confidentiality/contractual obligations.",
        "limitations": ["Hourly summary telemetry only; no raw load-displacement sequences.",
            "No independently adjudicated fault labels or asset configuration.",
            "Dataset README states year 2026 was inferred from monthly files and needs source verification.",
            "Do not convert kg or unitless dynamometer_area to force or physical card area without source definition."],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"rows": rows, "well_counts_by_type": out["well_counts_by_type"],
        "parameters": by_parameter, "duplicate_timestamps": out["global_duplicate_well_parameter_timestamps"],
        "report": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
