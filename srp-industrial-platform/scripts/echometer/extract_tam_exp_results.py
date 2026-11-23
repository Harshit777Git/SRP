"""Extract vendor result metadata from a TAM_EXP without altering the archive.

The native archive remains authoritative.  This utility copies its metadata and
TestResults JSON into the state library and creates a long-form CSV for dataset
inventory and engineering review.  It does not synthesize measurements.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    archive = args.archive.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)

    with ZipFile(archive) as package:
        names = set(package.namelist())
        required = {"metadata.json", "TestResults.json"}
        missing = required - names
        if missing:
            raise ValueError(f"Missing required TAM result members: {sorted(missing)}")
        metadata = json.loads(package.read("metadata.json"))
        test_results = json.loads(package.read("TestResults.json"))

    generated = str(metadata.get("DateExported") or datetime.fromtimestamp(archive.stat().st_mtime, timezone.utc).isoformat())
    provenance = {
        "state_id": args.state,
        "source_archive": str(archive),
        "source_sha256": sha256(archive),
        "source_bytes": archive.stat().st_size,
        "extracted_utc": generated,
        "method": "lossless extraction of vendor metadata.json and TestResults.json",
        "synthetic_data": False,
    }

    engineering_dir = args.output_root / "05_ENGINEERING_PARAMETERS" / "TAM"
    normalized_dir = args.output_root / "NORMALIZED_DATA"
    engineering_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    exact_output = engineering_dir / f"{args.state}_TAM_TEST_RESULTS.json"
    exact_output.write_text(
        json.dumps(
            {"provenance": provenance, "archive_metadata": metadata, "test_results": test_results},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    measurement_outputs: list[Path] = []
    all_tests = [
        test
        for well in test_results.get("Wells", [])
        for test in well.get("Tests", [])
    ]
    acoustic_tests = [test for test in all_tests if test.get("Type") == "ACU"]
    if acoustic_tests:
        acoustic_dir = args.output_root / "07_MEASUREMENTS" / "ACOUSTIC_TESTS"
        acoustic_dir.mkdir(parents=True, exist_ok=True)
        acoustic_output = acoustic_dir / f"{args.state}_TAM_ACU_RESULTS.json"
        acoustic_output.write_text(
            json.dumps({"provenance": provenance, "tests": acoustic_tests}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        measurement_outputs.append(acoustic_output)

    mechanical_terms = ("torque", "power", "counterbalance", "cyclic load", "beam loading", "rated current")
    mechanical_tests = []
    for test in all_tests:
        if test.get("Type") != "DYN":
            continue
        values = {
            name: value
            for name, value in (test.get("NumValues") or {}).items()
            if any(term in name.casefold() for term in mechanical_terms)
        }
        text_values = {
            name: value
            for name, value in (test.get("StrValues") or {}).items()
            if any(term in name.casefold() for term in ("balance", "weight"))
        }
        if values or text_values:
            mechanical_tests.append({
                "DateTime": test.get("DateTime", ""),
                "LastModified": test.get("LastModified", ""),
                "Type": test.get("Type", ""),
                "NumValues": values,
                "StrValues": text_values,
            })
    if mechanical_tests:
        mechanical_dir = args.output_root / "07_MEASUREMENTS" / "POWER_TORQUE"
        mechanical_dir.mkdir(parents=True, exist_ok=True)
        mechanical_output = mechanical_dir / f"{args.state}_TAM_DYN_MECHANICAL_ELECTRICAL_RESULTS.json"
        mechanical_output.write_text(
            json.dumps(
                {
                    "provenance": provenance,
                    "tests": mechanical_tests,
                    "note": "Exact vendor result values only; invalid/sentinel values are preserved and no units are inferred.",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        measurement_outputs.append(mechanical_output)

    rows: list[dict[str, object]] = []
    for well in test_results.get("Wells", []):
        well_name = well.get("Name", "")
        well_id = well.get("ID", "")
        for ordinal, test in enumerate(well.get("Tests", []), start=1):
            base = {
                "state_id": args.state,
                "well_name": well_name,
                "well_id": well_id,
                "test_ordinal": ordinal,
                "test_type": test.get("Type", ""),
                "test_datetime_utc": test.get("DateTime", ""),
                "last_modified_utc": test.get("LastModified", ""),
            }
            for kind, values in (("numeric", test.get("NumValues") or {}), ("text", test.get("StrValues") or {})):
                for parameter, value in values.items():
                    rows.append({**base, "value_kind": kind, "parameter": parameter, "value": value})

    csv_output = normalized_dir / f"{args.state}_TAM_TEST_RESULTS_LONG.csv"
    columns = [
        "state_id", "well_name", "well_id", "test_ordinal", "test_type",
        "test_datetime_utc", "last_modified_utc", "value_kind", "parameter", "value",
    ]
    with csv_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        **provenance,
        "well_count": len(test_results.get("Wells", [])),
        "test_count": sum(len(well.get("Tests", [])) for well in test_results.get("Wells", [])),
        "normalized_parameter_rows": len(rows),
        "outputs": [str(exact_output), str(csv_output), *map(str, measurement_outputs)],
    }
    manifest_output = normalized_dir / f"{args.state}_TAM_TEST_RESULTS_MANIFEST.json"
    manifest_output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
