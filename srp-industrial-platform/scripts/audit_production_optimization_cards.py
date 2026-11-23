"""Verify public SCADA-export card CSV contents without assigning labels."""
import csv
import hashlib
import json
import math
import csv
from statistics import mean, median, pstdev
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external_reference/production_optimization"
OUTPUT = ROOT / "data/evaluation/production_optimization_card_audit.json"
PROVENANCE = SOURCE / "PROVENANCE.json"
NORMALIZED = SOURCE / "normalized"
POINTS_CSV = NORMALIZED / "LA-0024_surface_points.csv"
CARDS_CSV = NORMALIZED / "LA-0024_card_metadata.csv"
RAW_BASE = "https://raw.githubusercontent.com/mulzahrian/production_optimization/main/csv_file/"
FILES = [
    "ExportedDynaCards_2020-9-28.csv",
    "ExportedDynaCards_2020-10-2.csv",
]
REQUIRED = {
    "Well Name", "Card Time", "Card Type", "Stroke Period", "SPM",
    "Stroke Length", "Surface Max Load", "Surface Min Load",
    "PositionLimit", "Surface Positions", "Surface Loads",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_points(value, name, row_number):
    if value is None or not value.strip():
        return []
    try:
        points = [float(item) for item in value.split(",")]
    except ValueError as exc:
        raise ValueError(f"Invalid {name} array on row {row_number}") from exc
    return points


def audit_file(filename, points_writer, cards_writer):
    path = SOURCE / filename
    result = {
        "file": str(path.relative_to(ROOT)),
        "source_url": RAW_BASE + filename,
        "sha256": sha256(path),
    }
    rows, types, wells, timestamps = [], Counter(), Counter(), Counter()
    surface_counts, downhole_counts = [], Counter()
    equal_dh_pos_load = 0
    scalar_values = defaultdict(lambda: {"values": [], "missing": 0})
    fingerprints = Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="|")
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fields)
        if missing:
            raise ValueError(f"{filename} missing columns: {missing}")
        for row in reader:
            number = reader.line_num
            time = datetime.fromisoformat(row["Card Time"].replace("Z", "+00:00"))
            surface_pos = parse_points(row.get("Surface Positions"), "Surface Positions", number)
            surface_load = parse_points(row.get("Surface Loads"), "Surface Loads", number)
            down_pos = parse_points(row.get("Downhole Positions"), "Downhole Positions", number)
            down_load = parse_points(row.get("Downhole Loads"), "Downhole Loads", number)
            if len(surface_pos) != len(surface_load):
                raise ValueError(f"Surface point-count mismatch on row {number}")
            if len(down_pos) != len(down_load) and down_load:
                raise ValueError(f"Downhole point-count mismatch on row {number}")
            if down_load and down_pos == down_load:
                equal_dh_pos_load += 1
            fingerprint = hashlib.sha256(
                (row.get("Surface Positions", "") + "|" + row.get("Surface Loads", "")).encode("utf-8")
            ).hexdigest()
            fingerprints[fingerprint] += 1
            for name in ("Stroke Period", "SPM", "Stroke Length", "Surface Max Load",
                         "Surface Min Load", "PositionLimit", "Hours Since Gauge Off"):
                try:
                    value = float(row[name])
                    if math.isfinite(value):
                        scalar_values[name]["values"].append(value)
                except (KeyError, ValueError, TypeError):
                    scalar_values[name]["missing"] += 1
            for sample_index, (position, load) in enumerate(zip(surface_pos, surface_load)):
                points_writer.writerow({
                    "source_file": filename, "source_sha256": result["sha256"],
                    "well_id": row["Well Name"], "stroke_timestamp": time.isoformat(),
                    "acquisition_card_type": row["Card Type"], "surface_trace_fingerprint": fingerprint,
                    "sample_index": sample_index, "surface_position_original": format(position, ".17g"),
                    "surface_load_original": format(load, ".17g"),
                    "position_unit_status": "UNIT_UNVERIFIED", "load_unit_status": "UNIT_UNVERIFIED",
                })
            cards_writer.writerow({
                "source_file": filename, "source_sha256": result["sha256"],
                "well_id": row["Well Name"], "stroke_timestamp": time.isoformat(),
                "acquisition_card_type": row["Card Type"], "surface_trace_fingerprint": fingerprint,
                "surface_point_count": len(surface_pos),
                "surface_max_load_source_field": row["Surface Max Load"],
                "surface_min_load_source_field": row["Surface Min Load"],
                "spm_source_field": row["SPM"], "stroke_length_source_field": row["Stroke Length"],
                "units": "UNIT_UNVERIFIED",
            })
            rows.append({
                "well": row["Well Name"], "time": time.isoformat(),
                "card_type": row["Card Type"],
                "surface_fingerprint": fingerprint,
                "surface_points": len(surface_pos),
                "downhole_position_points": len(down_pos),
                "downhole_load_points": len(down_load),
                "surface_min": min(surface_load) if surface_load else None,
                "surface_max": max(surface_load) if surface_load else None,
                "position_min": min(surface_pos) if surface_pos else None,
                "position_max": max(surface_pos) if surface_pos else None,
            })
            types[row["Card Type"]] += 1
            wells[row["Well Name"]] += 1
            timestamps[time.isoformat()] += 1
            surface_counts.append(len(surface_pos))
            downhole_counts["position_points"] += len(down_pos)
            downhole_counts["load_points"] += len(down_load)
    result.update({
        "rows": len(rows),
        "columns": sorted(fields),
        "card_type_counts": dict(types),
        "well_counts": dict(wells),
        "duplicate_timestamps_within_file": sum(n - 1 for n in timestamps.values() if n > 1),
        "surface_point_count_min": min(surface_counts, default=0),
        "surface_point_count_max": max(surface_counts, default=0),
        "surface_point_count_values": sorted(set(surface_counts)),
        "downhole_position_point_total": downhole_counts["position_points"],
        "downhole_load_point_total": downhole_counts["load_points"],
        "downhole_load_equals_position_rows": equal_dh_pos_load,
        "surface_point_pair_total": sum(surface_counts),
        "timestamp_min": min((row["time"] for row in rows), default=None),
        "timestamp_max": max((row["time"] for row in rows), default=None),
        "unique_surface_trace_fingerprints": len(fingerprints),
        "duplicate_surface_trace_copies": sum(n - 1 for n in fingerprints.values() if n > 1),
        "scalar_profiles": {
            name: {
                "count": len(stats["values"]), "missing": stats["missing"],
                "minimum": min(stats["values"]) if stats["values"] else None,
                "median": median(stats["values"]) if stats["values"] else None,
                "mean": mean(stats["values"]) if stats["values"] else None,
                "maximum": max(stats["values"]) if stats["values"] else None,
                "standard_deviation_population": pstdev(stats["values"]) if stats["values"] else None,
            }
            for name, stats in scalar_values.items()
        },
        "rows_detail": rows,
    })
    return result


def main():
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    point_fields = ["source_file", "source_sha256", "well_id", "stroke_timestamp",
                    "acquisition_card_type", "surface_trace_fingerprint", "sample_index",
                    "surface_position_original", "surface_load_original",
                    "position_unit_status", "load_unit_status"]
    card_fields = ["source_file", "source_sha256", "well_id", "stroke_timestamp",
                   "acquisition_card_type", "surface_trace_fingerprint", "surface_point_count",
                   "surface_max_load_source_field", "surface_min_load_source_field",
                   "spm_source_field", "stroke_length_source_field", "units"]
    with POINTS_CSV.open("w", encoding="utf-8", newline="") as point_stream, \
            CARDS_CSV.open("w", encoding="utf-8", newline="") as card_stream:
        points_writer = csv.DictWriter(point_stream, fieldnames=point_fields)
        cards_writer = csv.DictWriter(card_stream, fieldnames=card_fields)
        points_writer.writeheader()
        cards_writer.writeheader()
        files = [audit_file(name, points_writer, cards_writer) for name in FILES]
    all_rows = [row for file in files for row in file["rows_detail"]]
    result = {
        "source_url": "https://github.com/mulzahrian/production_optimization",
        "access_status": "DOWNLOADED_FOR_RESTRICTED_LOCAL_AUDIT",
        "permission": "RESTRICTED_NO_DATA_LICENSE_FOUND",
        "training_eligible": False,
        "fault_labels": 0,
        "measurement_origin": "SCADA-export claim in public source audit; not independently authenticated",
        "files": files,
        "total_cards": len(all_rows),
        "unique_wells_in_files": sorted({row["well"] for row in all_rows}),
        "all_surface_point_counts": sorted({row["surface_points"] for row in all_rows}),
        "unit_status": "UNIT_UNVERIFIED_IN_FILE_HEADERS",
        "usage": "Local restricted plotting/import-format evaluation only. No redistribution or supervised training.",
        "limitations": [
            "No data license was found; keep out of public artifacts and distribution.",
            "Card Type is acquisition type, not a fault label.",
            "A public source-maintainer audit reports one file's Downhole Loads equals Downhole Positions and the other file has no downhole data; this script independently checks the local file values.",
            "Any downhole reference values are provider calculations, not measured pump-end ground truth.",
            "File headers do not establish measurement units or full equipment configuration.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    provenance = {
        "dataset_id": "production-optimization-la0024-public-controller-export",
        "repository_url": result["source_url"],
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_method": "HTTPS raw GitHub file download",
        "license_status": "NO_DATA_LICENSE_FOUND; source maintainer says all rights reserved",
        "permission": "RESTRICTED",
        "measurement_origin": result["measurement_origin"],
        "training_eligible": False,
        "fault_labels": 0,
        "local_use": "Restricted local surface-card plotting/import-format inspection only; no redistribution or supervised training.",
        "files": [
            {key: value for key, value in file.items() if key != "rows_detail"}
            for file in files
        ],
        "normalized_point_file": str(POINTS_CSV.relative_to(ROOT)),
        "normalized_point_file_sha256": sha256(POINTS_CSV),
        "normalized_card_metadata_file": str(CARDS_CSV.relative_to(ROOT)),
        "normalized_card_metadata_file_sha256": sha256(CARDS_CSV),
        "normalized_point_rows": sum(file["surface_point_pair_total"] for file in files),
        "source_license_and_content_audit_url": "https://github.com/vamseeachanta/digitalmodel/issues/1873",
    }
    PROVENANCE.write_text(json.dumps(provenance, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, indent=2))
    for file in files:
        print(json.dumps({key: value for key, value in file.items() if key != "rows_detail"}, indent=2))


if __name__ == "__main__":
    main()
