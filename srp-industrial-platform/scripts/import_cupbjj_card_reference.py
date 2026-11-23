"""Losslessly profile three public numerical card examples as reference-only data."""
import csv
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external_reference/cupbjj_dynamometer_card"
DATA = SOURCE / "datasets"
NORMALIZED = SOURCE / "normalized"
OUT = SOURCE / "PROVENANCE.json"
URL = "https://github.com/CUPBJJB/Dynamometer-card"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    NORMALIZED.mkdir(exist_ok=True)
    commit = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    source_files = sorted(DATA.glob("*.txt"))
    if len(source_files) != 3:
        raise RuntimeError(f"Expected exactly three card text files, found {len(source_files)}")
    cards = []
    for source in source_files:
        rows = []
        for line_no, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"Unexpected row shape: {source.name}:{line_no}")
            load, position = map(float, parts)
            rows.append((parts[0], parts[1], load, position))
        if len(rows) != 67:
            raise ValueError(f"Expected 67 pairs in {source.name}; got {len(rows)}")
        target = NORMALIZED / f"{source.stem}.csv"
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["sample_index", "load_source_text", "position_source_text"])
            for index, (load_text, position_text, _, _) in enumerate(rows):
                writer.writerow([index, load_text, position_text])
        loads = [r[2] for r in rows]
        positions = [r[3] for r in rows]
        cards.append({
            "card_id": source.stem,
            "source_path": str(source.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": sha256(source),
            "normalized_path": str(target.relative_to(ROOT)).replace("\\", "/"),
            "normalized_sha256": sha256(target),
            "ordered_numerical_pairs": len(rows),
            "load_column": {"source_name": "first column", "declared_unit": "kN (repository code axis label)",
                "unit_status": "UNIT_UNVERIFIED", "minimum": min(loads), "maximum": max(loads),
                "mean": sum(loads) / len(loads)},
            "position_column": {"source_name": "second column", "declared_unit": "m (repository code axis label)",
                "unit_status": "UNIT_UNVERIFIED", "minimum": min(positions), "maximum": max(positions),
                "mean": sum(positions) / len(positions), "range": max(positions) - min(positions)},
            "duplicate_rows": len(rows) - len(set((r[0], r[1]) for r in rows)),
            "measurement_origin": "UNKNOWN; repository does not state field-measured vs simulated",
            "fault_label": None,
        })
    license_file = SOURCE / "LICENSE"
    result = {
        "dataset_id": "cupbjj-dynamometer-card-three-examples",
        "source_url": URL,
        "commit": commit,
        "acquired_on": date.today().isoformat(),
        "repository_license_file_present": license_file.exists(),
        "repository_code_license": "NONE_FOUND_IN_CHECKOUT" if not license_file.exists() else "SEE_LICENSE_FILE",
        "data_license_and_training_permission": "PERMISSION_UNVERIFIED",
        "training_eligible": False,
        "intended_use": "Reference plotting and engineering importer evaluation only; no supervised training",
        "source_readme_declares_pairs": "load then displacement; code labels plotted axes kN and m",
        "source_readme_measurement_provenance": "Not stated",
        "record_summary": {"files": len(cards), "cards": len(cards),
            "ordered_numeric_pairs": sum(c["ordered_numerical_pairs"] for c in cards),
            "unique_well_count": None, "fault_labels": 0},
        "cards": cards,
        "limitations": [
            "Three files named DK3, DK6 and S22 are not independently authenticated unique wells.",
            "No fault labels, timestamps, electrical channels or verified downhole traces are included.",
            "The stated position unit is metres, but the observed 5.4-5.7 m spans are physically suspect for polished-rod stroke; no conversion is applied.",
            "No explicit dataset license was found; repository code license does not grant rights to the data.",
            "Do not use for supervised ML training or claim measured-field validation until provenance, units and permission are confirmed.",
        ],
    }
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"provenance": str(OUT), "commit": commit,
        "cards": len(cards), "pairs": result["record_summary"]["ordered_numeric_pairs"],
        "permission": result["data_license_and_training_permission"]}, indent=2))


if __name__ == "__main__":
    main()
