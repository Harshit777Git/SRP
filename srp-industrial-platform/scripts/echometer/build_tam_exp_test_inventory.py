"""Build cross-state inventories from losslessly extracted TAM result metadata."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = ROOT / "data" / "state93"
REPORT_ROOT = ROOT / "reports" / "STATE96"
VALIDATION = ROOT / "reports" / "STATE93" / "PHASE5_1" / "NUMERICAL_EXPORT_VALIDATION.csv"


def main() -> None:
    test_rows: list[dict[str, object]] = []
    stroke_rows: list[dict[str, object]] = []
    parameter_counts: Counter[tuple[str, str, str]] = Counter()
    verified: dict[tuple[str, str, int], dict[str, str]] = {}
    if VALIDATION.exists():
        with VALIDATION.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("status") == "NUMERICAL_VERIFIED":
                    stroke_match = re.match(r"\d+", row.get("stroke_id", ""))
                    if stroke_match:
                        verified[(row["state_id"], row["test_id"], int(stroke_match.group()))] = row

    for path in sorted(STATE_ROOT.glob("STATE-*/05_ENGINEERING_PARAMETERS/TAM/*_TAM_TEST_RESULTS.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        state_id = payload["provenance"]["state_id"]
        source = payload["provenance"]["source_archive"]
        source_hash = payload["provenance"]["source_sha256"]
        for well in payload.get("test_results", {}).get("Wells", []):
            for ordinal, test in enumerate(well.get("Tests", []), start=1):
                numeric = test.get("NumValues") or {}
                text = test.get("StrValues") or {}
                utc_text = test.get("DateTime", "")
                local_test_id = ""
                local_text = ""
                if utc_text:
                    utc_dt = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
                    local_dt = utc_dt.astimezone(ZoneInfo("Asia/Kolkata"))
                    local_test_id = local_dt.strftime("%Y-%m-%d_%H%M%S")
                    local_text = local_dt.isoformat()
                number_of_strokes = numeric.get("Number of Strokes")
                test_rows.append({
                    "state_id": state_id,
                    "well_name": well.get("Name", ""),
                    "well_id": well.get("ID", ""),
                    "test_ordinal": ordinal,
                    "test_type": test.get("Type", ""),
                    "test_datetime_utc": utc_text,
                    "test_datetime_local_ist": local_text,
                    "local_test_id": local_test_id,
                    "number_of_strokes": number_of_strokes,
                    "selected_stroke_number": numeric.get("Stroke Number"),
                    "last_modified_utc": test.get("LastModified", ""),
                    "numeric_parameter_count": len(numeric),
                    "text_parameter_count": len(text),
                    "source_archive": source,
                    "source_sha256": source_hash,
                })
                if test.get("Type") == "DYN" and number_of_strokes:
                    for stroke_number in range(1, int(number_of_strokes) + 1):
                        match = verified.get((state_id, local_test_id, stroke_number))
                        stroke_rows.append({
                            "state_id": state_id,
                            "well_name": well.get("Name", ""),
                            "test_datetime_utc": utc_text,
                            "test_datetime_local_ist": local_text,
                            "test_id": local_test_id,
                            "stroke_number": stroke_number,
                            "status": "NUMERICAL_VERIFIED" if match else "MISSING_DYN_AND_TXT",
                            "points": match.get("points", "") if match else "",
                            "dyn_path": match.get("dyn_path", "") if match else "",
                            "txt_path": match.get("txt_path", "") if match else "",
                            "source_archive": source,
                            "source_sha256": source_hash,
                        })
                for name in numeric:
                    parameter_counts[(test.get("Type", ""), "numeric", name)] += 1
                for name in text:
                    parameter_counts[(test.get("Type", ""), "text", name)] += 1

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    test_output = REPORT_ROOT / "TAM_EXP_TEST_INVENTORY.csv"
    test_fields = [
        "state_id", "well_name", "well_id", "test_ordinal", "test_type",
        "test_datetime_utc", "test_datetime_local_ist", "local_test_id",
        "number_of_strokes", "selected_stroke_number", "last_modified_utc",
        "numeric_parameter_count", "text_parameter_count", "source_archive", "source_sha256",
    ]
    with test_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=test_fields)
        writer.writeheader()
        writer.writerows(test_rows)

    parameter_output = REPORT_ROOT / "TAM_EXP_PARAMETER_INVENTORY.csv"
    with parameter_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["test_type", "value_kind", "parameter", "record_count"])
        writer.writeheader()
        for (test_type, value_kind, parameter), count in sorted(parameter_counts.items()):
            writer.writerow({"test_type": test_type, "value_kind": value_kind, "parameter": parameter, "record_count": count})

    stroke_output = REPORT_ROOT / "TAM_EXP_EXPECTED_STROKE_QUEUE.csv"
    stroke_fields = [
        "state_id", "well_name", "test_datetime_utc", "test_datetime_local_ist", "test_id",
        "stroke_number", "status", "points", "dyn_path", "txt_path", "source_archive", "source_sha256",
    ]
    with stroke_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=stroke_fields)
        writer.writeheader()
        writer.writerows(stroke_rows)

    summary = {
        "states": len({row["state_id"] for row in test_rows}),
        "tests": len(test_rows),
        "test_types": dict(sorted(Counter(str(row["test_type"]) for row in test_rows).items())),
        "unique_parameters": len(parameter_counts),
        "expected_strokes_from_vendor_counts": len(stroke_rows),
        "verified_expected_strokes": sum(row["status"] == "NUMERICAL_VERIFIED" for row in stroke_rows),
        "missing_expected_strokes": sum(row["status"] != "NUMERICAL_VERIFIED" for row in stroke_rows),
        "dyn_tests_without_stroke_count": sum(row["test_type"] == "DYN" and not row["number_of_strokes"] for row in test_rows),
        "outputs": [str(test_output), str(parameter_output), str(stroke_output)],
    }
    (REPORT_ROOT / "TAM_EXP_RESULT_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
