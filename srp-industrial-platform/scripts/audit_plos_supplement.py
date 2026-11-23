"""Audit and losslessly export the public PLOS SRP supporting workbook.

The source workbook is preserved unchanged. CSV files retain the original
column names, row order, and numeric values; this script does not invent times,
units, well IDs, card/electrical pairings, or fault labels.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external_reference/plos_0326973_s001"
NORMALIZED = SOURCE / "normalized_csv"
EVALUATION = ROOT / "data/evaluation/plos_0326973_s001_profile.json"
REPORT = ROOT / "reports/PHASE3_2/PLOS_SUPPLEMENT_AUDIT.md"
SOURCE_URL = "https://doi.org/10.1371/journal.pone.0326973.s001"
ARTICLE_URL = "https://doi.org/10.1371/journal.pone.0326973"
CC_BY = "CC BY 4.0; attribution required"

TRANSLATIONS = {
    "suspension point displacement": ("polished_rod_displacement", "UNIT_UNVERIFIED"),
    "suspension point load": ("polished_rod_load", "UNIT_UNVERIFIED"),
    "A相电压": ("phase_a_voltage", "UNIT_UNVERIFIED"),
    "A相电流": ("phase_a_current", "UNIT_UNVERIFIED"),
    "B相电压": ("phase_b_voltage", "UNIT_UNVERIFIED"),
    "B相电流": ("phase_b_current", "UNIT_UNVERIFIED"),
    "C相电压": ("phase_c_voltage", "UNIT_UNVERIFIED"),
    "C相电流": ("phase_c_current", "UNIT_UNVERIFIED"),
    "功率": ("power", "UNIT_UNVERIFIED"),
    "功率因数": ("power_factor", "UNIT_UNVERIFIED"),
    "备注": ("remarks_code", "CATEGORY_UNVERIFIED"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    return str(value)


def profile_column(name, values, dataset_id, source_file):
    missing = [v is None or (isinstance(v, str) and not v.strip()) for v in values]
    observed = [v for v, is_missing in zip(values, missing) if not is_missing]
    numeric = []
    for value in observed:
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            numeric = []
            break
        if not math.isfinite(number):
            numeric = []
            break
        numeric.append(number)
    normalized_name, unit = TRANSLATIONS.get(name, ("UNMAPPED", "UNIT_UNVERIFIED"))
    result = {
        "dataset_id": dataset_id,
        "source_file": source_file,
        "original_column": name,
        "normalized_name": normalized_name,
        "engineering_meaning": {
            "polished_rod_displacement": "Surface suspension-point displacement; paper describes dynamometer displacement.",
            "polished_rod_load": "Surface suspension-point load; paper describes dynamometer load.",
            "phase_a_voltage": "Three-phase motor electrical channel A voltage.",
            "phase_a_current": "Three-phase motor electrical channel A current.",
            "phase_b_voltage": "Three-phase motor electrical channel B voltage.",
            "phase_b_current": "Three-phase motor electrical channel B current.",
            "phase_c_voltage": "Three-phase motor electrical channel C voltage.",
            "phase_c_current": "Three-phase motor electrical channel C current.",
            "power": "Motor power channel; physical scale/unit not confirmed from workbook.",
            "power_factor": "Power-factor channel; precise convention not stated in workbook.",
            "remarks_code": "Source remarks field; code meanings not documented.",
        }.get(normalized_name, "Source field meaning not verified."),
        "unit": unit,
        "data_type": "numeric" if numeric else (type(observed[0]).__name__ if observed else "unknown"),
        "sample_count": len(values),
        "missing_count": sum(missing),
        "missing_percent": 100 * sum(missing) / len(values) if values else None,
        "unique_values": len(set(map(str, observed))),
        "source_type": "sensor_or_calculated_source_field; workbook-level origin unresolved",
        "quality": "REVIEW_REQUIRED" if normalized_name == "remarks_code" else "PROFILED",
        "suitable_for_ml": "conditional_unlabeled_only" if numeric else "no",
        "suitable_for_simulation": "conditional_reference_only" if normalized_name != "remarks_code" else "no",
        "leakage_risk": "unknown; do not use as target or label",
    }
    if numeric:
        result.update(
            minimum=min(numeric), maximum=max(numeric),
            mean=statistics.fmean(numeric),
            standard_deviation=statistics.stdev(numeric) if len(numeric) > 1 else 0.0,
            finite_count=len(numeric),
            sampling_interval="UNAVAILABLE: no timestamp/sample-time column",
        )
    else:
        result["value_counts"] = {str(k): v for k, v in Counter(map(str, observed)).most_common()}
    if normalized_name == "remarks_code":
        result["value_counts"] = {str(k): v for k, v in Counter(map(str, observed)).most_common()}
    return result


def inspect_workbook(path: Path, dataset_id: str):
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet_names = list(workbook.sheetnames)
        sheet = workbook.worksheets[0]
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    if not rows or not rows[0]:
        raise ValueError(f"No tabular values: {path}")
    headers = [str(value) if value is not None else "" for value in rows[0]]
    values = [tuple(row) for row in rows[1:] if any(value is not None for value in row)]
    if any(len(row) != len(headers) for row in values):
        raise ValueError(f"Inconsistent row width: {path}")
    canonical_rows = [tuple(csv_value(value) for value in row) for row in values]
    duplicate_row_count = len(canonical_rows) - len(set(canonical_rows))
    adjacent_duplicate_count = sum(a == b for a, b in zip(canonical_rows, canonical_rows[1:]))

    normalized_path = NORMALIZED / f"{path.stem}.csv"
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    with normalized_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows([[csv_value(value) for value in row] for row in values])

    # Confirm row/column values survive CSV serialization without numeric conversion.
    with normalized_path.open(newline="", encoding="utf-8-sig") as stream:
        copied = list(csv.reader(stream))
    expected = [[csv_value(value) for value in row] for row in values]
    if copied[0] != headers or copied[1:] != expected:
        raise ValueError(f"CSV round-trip mismatch: {normalized_path}")

    columns = []
    for index, header in enumerate(headers):
        columns.append(profile_column(header, [row[index] for row in values], dataset_id,
                                      path.relative_to(ROOT).as_posix()))
    note_counts = None
    if "备注" in headers:
        note_counts = dict(Counter(str(row[headers.index("备注")]) for row in values))
    info = {
        "source_file": path.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(path),
        "source_bytes": path.stat().st_size,
        "sheet": sheet.title,
        "sheet_names": sheet_names,
        "data_bearing_sheet": sheet.title,
        "data_rows": len(values),
        "column_count": len(headers),
        "original_columns": headers,
        "normalized_file": normalized_path.relative_to(ROOT).as_posix(),
        "normalized_sha256": sha256(normalized_path),
        "csv_round_trip_exact": True,
        "remarks_value_counts": note_counts,
        "exact_duplicate_rows": duplicate_row_count,
        "adjacent_duplicate_rows": adjacent_duplicate_count,
        "columns": columns,
    }
    return info


def main():
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    inputs = [SOURCE / f"DC{i}.xlsx" for i in range(1, 5)] + [SOURCE / f"ED{i}.xlsx" for i in range(1, 5)]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing expected supporting files: " + ", ".join(missing))

    items = []
    for path in inputs:
        kind = "surface_card" if path.stem.startswith("DC") else "electrical_timeseries_unresolved_origin"
        items.append(inspect_workbook(path, f"plos-0326973-{kind}"))

    cards = [item for item in items if item["source_file"].split("/")[-1].startswith("DC")]
    electrical = [item for item in items if item["source_file"].split("/")[-1].startswith("ED")]
    summary = {
        "dataset_id": "plos-0326973-s001",
        "source_url": SOURCE_URL,
        "article_url": ARTICLE_URL,
        "accessed_date": date.today().isoformat(),
        "attribution": "Li X, Liu Z, Yuan C, Liao Z. Electric parameter prediction of rod pumping units based on N-HiTS model. PLOS ONE. 2025;20(7):e0326973. https://doi.org/10.1371/journal.pone.0326973",
        "license": CC_BY,
        "dataset_permission": "VERIFIED_CC_BY_4_0_WITH_ATTRIBUTION",
        "source_origin": "Paper states DC and electrical parameters are included; paper also describes mixing actual electrical observations with generated electrical sequences. Workbook-level provenance/category mapping is not provided, so ED1-ED4 remain MEASURED_OR_GENERATED_UNRESOLVED.",
        "publication_engineering_context": {
            "source": ARTICLE_URL,
            "pumping_unit_model_reported": "CJY10-3-53HB",
            "balance_type_reported": "crank-balanced beam unit",
            "motor_nameplate_table": {"rated_power_W": 4000, "rated_voltage_V": 400, "rated_speed_rpm": 1430, "rated_torque_Nm": 26.6331},
            "electrical_generation_experiment_settings": {"supply_frequency_Hz": 50, "phase_angle_deg": 120, "initial_motor_speed_rpm": 1480},
            "not_supplied_for_record_level_match": ["card-to-condition mapping", "well/stroke identifiers", "rod-string taper and depth", "pump depth/diameter", "fluid properties", "individual card units and collection times", "ED workbook origin and timestamps"],
            "usage_note": "Paper-level context only; do not assign every supplementary row/card to these settings without a source crosswalk. Rated 1430 rpm and model-experiment 1480 rpm are distinct stated values.",
        },
        "training_eligible_for_fault_classification": False,
        "training_exclusion": "No independently verified card fault labels, no well IDs/timestamps, no card-to-electrical crosswalk, and ED workbook origin and units are not assigned per file.",
        "normalization_policy": "Original XLSX files retained. CSV copies keep source headers, row order and source cell values; no unit conversion, time synthesis, fault labels, or joins were made.",
        "inventory": {
            "surface_cards": len(cards),
            "ordered_card_pairs": sum(item["data_rows"] for item in cards),
            "electrical_workbooks": len(electrical),
            "electrical_rows": sum(item["data_rows"] for item in electrical),
            "timestamped_electrical_rows": 0,
            "known_fault_labeled_records": 0,
            "unique_wells": None,
        },
        "files": items,
    }
    manifest_path = SOURCE / "PROVENANCE.json"
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    legacy_card_manifest = NORMALIZED / "PROVENANCE.json"
    legacy_cards = json.loads(legacy_card_manifest.read_text(encoding="utf-8")) if legacy_card_manifest.exists() else {}
    legacy_cards.update({
        "scope": "DC1-DC4 card CSV derivatives only; ED1-ED4 are cataloged in the canonical root manifest.",
        "canonical_provenance_path": "data/external_reference/plos_0326973_s001/PROVENANCE.json",
        "permission": "VERIFIED_CC_BY_4_0_WITH_ATTRIBUTION",
        "training_eligible": False,
        "exclusion": "No independent fault labels, well IDs, timestamps, explicit card units, or card-to-electrical crosswalk.",
    })
    legacy_card_manifest.write_text(json.dumps(legacy_cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EVALUATION.parent.mkdir(parents=True, exist_ok=True)
    EVALUATION.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    attribution_path = SOURCE / "ATTRIBUTION.md"
    attribution_path.write_text(
        "# PLOS supporting information attribution\n\n"
        "Source: Li X, Liu Z, Yuan C, Liao Z. *Electric parameter prediction of rod pumping units based on N-HiTS model*. PLOS ONE. 2025;20(7):e0326973. https://doi.org/10.1371/journal.pone.0326973.\n\n"
        "Supporting Information: S1 Data, https://doi.org/10.1371/journal.pone.0326973.s001. Reuse under CC BY 4.0 with attribution.\n\n"
        "The XLSX files are preserved unchanged. CSV copies retain original headers and row order. No unit conversion, row-label assignment, timestamps, well identities, or card/electrical joins were added. The source paper describes both measured electrical parameters and generated electrical data, but does not map those origins to each ED workbook.\n",
        encoding="utf-8",
    )

    registry_path = ROOT / "data/dataset_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for row in registry:
        if row.get("dataset_id") == "plos-0326973-s001":
            row.update(
                records=41699, raw_samples=41699, surface_cards=4, downhole_cards=0,
                labeled_records=0, unlabeled_records=41699, files=8,
                path="data/external_reference/plos_0326973_s001/",
                sha256=sha256(SOURCE.parent / "plos_0326973_s001.zip") if (SOURCE.parent / "plos_0326973_s001.zip").exists() else None,
                source_origin=summary["source_origin"],
                engineering_units="Card and all ED physical units UNVERIFIED from these sheets",
                quality_findings="4 cards x 144 ordered pairs; 4 ED workbooks x 41,699 rows total. ED files have 9 columns and no timestamp. Workbook-level measured/generated origin, fault labels, wells and DC/ED crosswalk are unavailable. See PROVENANCE.json.",
                provenance_path="data/external_reference/plos_0326973_s001/PROVENANCE.json",
                profile_path="data/evaluation/plos_0326973_s001_profile.json",
                intended_use="Attribution-required reference and unlabeled engineering analysis; not supervised fault training",
            )
        elif row.get("dataset_id") == "plos-0326973-dynamometer-cards":
            row.update(raw_samples=576, records=4, strokes=None, wells=None,
                       sha256_manifest="data/external_reference/plos_0326973_s001/PROVENANCE.json",
                       provenance_path="data/external_reference/plos_0326973_s001/PROVENANCE.json",
                       quality_findings="4 cards x 144 ordered pairs; units, well IDs, timestamps and fault labels unavailable; CC BY 4.0 attribution required.")
        elif row.get("dataset_id") == "plos-0326973-electrical-rows":
            row.update(records=41699, raw_samples=41699, files=4,
                       sha256_manifest="data/external_reference/plos_0326973_s001/PROVENANCE.json",
                       provenance_path="data/external_reference/plos_0326973_s001/PROVENANCE.json",
                       quality_findings="41,699 rows with 9 source columns, no timestamps, no per-workbook origin mapping and no card crosswalk; units and note-code semantics unverified.")
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_file = ROOT / "data/dataset_manifest.json"
    dataset_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    for entry in dataset_manifest.get("datasets", []):
        if entry.get("dataset_id", "").startswith("plos-0326973-"):
            entry["superseded_by_audit"] = "data/external_reference/plos_0326973_s001/PROVENANCE.json"
    zip_path = SOURCE.parent / "plos_0326973_s001.zip"
    zip_hash = sha256(zip_path) if zip_path.exists() else None
    new_entries = [
        {
            "dataset_id": "plos-0326973-s001-package", "title": "PLOS ONE S1 Data: SRP dynamometer and electrical parameters",
            "source_url": SOURCE_URL, "article_url": ARTICLE_URL, "license_status": CC_BY,
            "path": "data/external_reference/plos_0326973_s001/", "archive_path": "data/external_reference/plos_0326973_s001.zip",
            "sha256": zip_hash, "download_timestamp": "2026-11-17", "workbooks": 8,
            "surface_cards": 4, "surface_point_pairs": 576, "electrical_rows": 41699,
            "fault_labeled_records": 0, "wells": None, "status": "ATTRIBUTION_REQUIRED_REFERENCE",
            "origin": summary["source_origin"], "training_eligible": False,
            "provenance_path": "data/external_reference/plos_0326973_s001/PROVENANCE.json",
        },
        {
            "dataset_id": "plos-0326973-dc1-dc4", "title": "PLOS S1 Data: four surface dynamometer cards",
            "source_url": SOURCE_URL, "license_status": CC_BY, "files": [item["source_file"] for item in cards],
            "normalized_files": [item["normalized_file"] for item in cards],
            "sha256": {item["source_file"]: item["source_sha256"] for item in cards},
            "surface_cards": 4, "ordered_point_pairs": 576, "labels": [], "well_ids": None,
            "units": "UNIT_UNVERIFIED", "origin": "PAPER_CLAIMS_MEASURED; record-level origin unverified",
            "training_eligible": False, "provenance_path": "data/external_reference/plos_0326973_s001/PROVENANCE.json",
        },
        {
            "dataset_id": "plos-0326973-ed1-ed4", "title": "PLOS S1 Data: four electrical-parameter workbooks",
            "source_url": SOURCE_URL, "license_status": CC_BY, "files": [item["source_file"] for item in electrical],
            "normalized_files": [item["normalized_file"] for item in electrical],
            "sha256": {item["source_file"]: item["source_sha256"] for item in electrical},
            "rows": sum(item["data_rows"] for item in electrical), "columns_per_workbook": 9,
            "fault_labels": [], "timestamps": False, "well_ids": None,
            "units": "UNIT_UNVERIFIED", "origin": "MEASURED_OR_GENERATED_UNRESOLVED_PER_WORKBOOK",
            "training_eligible": False, "provenance_path": "data/external_reference/plos_0326973_s001/PROVENANCE.json",
        },
    ]
    for entry in new_entries:
        if not any(item.get("dataset_id") == entry["dataset_id"] for item in dataset_manifest["datasets"]):
            dataset_manifest["datasets"].append(entry)
        else:
            index = next(i for i, item in enumerate(dataset_manifest["datasets"])
                         if item.get("dataset_id") == entry["dataset_id"])
            dataset_manifest["datasets"][index] = entry
    manifest_file.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# PLOS S1 Supporting Data Audit",
        "",
        f"Source: [PLOS article]({ARTICLE_URL}) and [S1 Data archive]({SOURCE_URL}). The article states that S1 Data contains dynamometer and electrical-parameter data. Reuse is under CC BY 4.0 with attribution.",
        "",
        f"Audit command: `python scripts/audit_plos_supplement.py` (Python dependencies: openpyxl). Canonical file inventory: `data/external_reference/plos_0326973_s001/PROVENANCE.json`; complete column profile: `data/evaluation/plos_0326973_s001_profile.json`.",
        "",
        "## Inventory",
        "",
        "| Files | Records | Details |",
        "|---|---:|---|",
        "| DC1–DC4 | 4 cards / 576 pairs | 144 ordered surface displacement/load rows per card; Sheet1 contains data. |",
        "| ED1–ED4 | 41,699 rows | Four electrical-parameter sheets with 9 columns each; no timestamp column. |",
        "| Fault-labeled records | 0 | No verified row/card-to-fault labels or DC/ED crosswalk. |",
        "",
        "The article describes actual electrical measurements and generated electrical values from cards, but does not identify which ED workbook belongs to which origin. Treat ED1–ED4 as `MEASURED_OR_GENERATED_UNRESOLVED`, not as verified measured or simulated subsets. The card workbooks are described as surface dynamometer measurements, but card-level well identity, fault label, units and collection times are absent. DC2–DC4 each end with one adjacent repeated point pair; these raw rows are preserved and not interpreted as errors or removed.",
        "",
        "## Publication-reported engineering context (not a complete matched configuration)",
        "",
        "The PLOS article names a crank-balanced `CJY10-3-53HB` beam unit. Its motor table gives rated power 4,000 W, voltage 400 V, rated speed 1,430 rpm and rated torque 26.6331 N·m. The paper's electrical-generation experiment separately sets 50 Hz, 120° phase separation and 1,480 rpm initial speed. These values describe the publication's setup and model, not a verified row-level join to DC1–DC4 or ED1–ED4. Rod-string geometry, pump depth/diameter, fluid properties, exact per-card operating rate, units, and sample timestamps remain unavailable here.",
        "",
        "A related 2025 [Scientific Reports study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12215541/) by the same research group also names `CJY10-3-53HB`, describes a 6-condition card set (normal, rod parting, insufficient supply, underbalance, pump leakage, gas influence), and states the data are available from corresponding author Xiangyu Li (`xyli@sylu.edu.cn`) on reasonable request. That study lists a 37 kW motor, unlike the PLOS paper's 4 kW nameplate; these contexts are not merged. The same fault-class list does not establish which DC1–DC4 card belongs to which condition. See the access request draft in `docs/REAL_DATA_AUTHOR_REQUEST_DRAFT.md`.",
        "",
        "## Electrical columns",
        "",
        "| Original field | Common name | Physical meaning | Units / sampling |",
        "|---|---|---|---|",
    ]
    for original, (common, unit) in TRANSLATIONS.items():
        if common.startswith("phase_") or common in ("power", "power_factor", "remarks_code"):
            meaning = next((col["engineering_meaning"] for item in electrical for col in item["columns"]
                            if col["original_column"] == original), "Source field meaning not verified.")
            report_lines.append(f"| `{original}` | `{common}` | {meaning} | `{unit}`; sample interval unknown |")
    report_lines.extend([
        "",
        "All nine columns contain 41,699 total values across the four workbooks with zero missing cells. Each workbook has 5,621–17,222 rows. The remark field takes values `0`, `111`, and `222`; no code definitions are supplied, so these values are not treated as labels. Per-workbook ranges, means, standard deviations, unique counts, hashes and row-level duplicate counts are in the JSON profile.",
        "",
        "## Use and limitations",
        "",
        "- Keep the original XLSX files unchanged; UTF-8 CSV derivatives preserve source header text, row order and cell values exactly. No timestamps, unit conversions, labels or joins were invented.",
        "- The DC cards can be plotted as engineering references. Do not compare load/displacement errors until units, phase conventions and equipment association are verified.",
        "- The electrical workbooks support source-format and unlabeled signal-profile analysis. They are not a validated supervised fault dataset, and their exact measured-versus-generated provenance is unresolved per file.",
        "- Use the published model details as research context only; do not assume one workbook is a normal/fault class based on its filename, numerical signature or remarks code.",
        "- No records from this supplement were added to `data/training/real_labeled/`.",
        "",
    ])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    print(json.dumps({"manifest": manifest_path.as_posix(), "profile": EVALUATION.as_posix(),
                      "surface_cards": summary["inventory"]["surface_cards"],
                      "ordered_card_pairs": summary["inventory"]["ordered_card_pairs"],
                      "electrical_rows": summary["inventory"]["electrical_rows"],
                      "fault_labeled_records": 0,
                      "training_eligible_for_fault_classification": False}, indent=2))


if __name__ == "__main__":
    main()
