"""Create lossless, provenance-linked CSV copies of the PLOS card sheets.

The original XLSX files are preserved. This does not assign card units, field
labels, well IDs, or training eligibility.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external_reference/plos_0326973_s001"
OUT = SOURCE / "normalized_csv"
EXPECTED_HEADERS = (
    "suspension point displacement",
    "suspension point load",
)
EXPECTED_POINTS = 144
SOURCE_URL = "https://doi.org/10.1371/journal.pone.0326973.s001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_one(path: Path) -> dict:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = workbook["Sheet1"]
        rows = sheet.iter_rows(values_only=False)
        header_cells = next(rows)
        headers = tuple(cell.value for cell in header_cells)
        if headers != EXPECTED_HEADERS:
            raise ValueError(f"{path.name}: unexpected columns {headers!r}")

        points = []
        numeric_cells = 0
        for row_number, cells in enumerate(rows, start=2):
            values = tuple(cell.value for cell in cells)
            if len(values) != 2 or any(not isinstance(v, (str, int, float)) for v in values):
                raise ValueError(f"{path.name}:{row_number}: expected two numeric values")
            try:
                numeric_values = tuple(float(v) for v in values)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path.name}:{row_number}: non-numeric point") from error
            if any(not math.isfinite(v) for v in numeric_values):
                raise ValueError(f"{path.name}:{row_number}: non-finite point")
            numeric_cells += sum(not isinstance(v, str) for v in values)
            # Keep source text cells verbatim; express numeric XLSX cells using
            # their shortest Python decimal representation (e.g. numeric 0 -> "0").
            points.append(tuple(v if isinstance(v, str) else str(v) for v in values))
        if len(points) != EXPECTED_POINTS:
            raise ValueError(f"{path.name}: expected {EXPECTED_POINTS} pairs, got {len(points)}")
    finally:
        workbook.close()

    output = OUT / f"{path.stem}.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(points)

    # Read back and compare exact source text values, not approximate floats.
    with output.open(newline="", encoding="utf-8-sig") as stream:
        csv_rows = list(csv.reader(stream))
    if tuple(csv_rows[0]) != EXPECTED_HEADERS or csv_rows[1:] != [list(p) for p in points]:
        raise ValueError(f"{output.name}: round-trip value mismatch")

    return {
        "source_file": path.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(path),
        "normalized_file": output.relative_to(ROOT).as_posix(),
        "normalized_sha256": sha256(output),
        "sheet": "Sheet1",
        "point_pairs": len(points),
        "numeric_cells_as_decimal_text": numeric_cells,
        "columns_original_order": list(headers),
        "values_round_trip_exact": True,
        "units": "UNIT_UNVERIFIED",
        "origin": "MEASURED_CLAIM_UNVERIFIED",
        "fault_label": None,
        "training_eligible": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = [normalize_one(SOURCE / f"DC{index}.xlsx") for index in range(1, 5)]
    manifest = {
        "source_url": SOURCE_URL,
        "derivation": "CSV values copied in original row/column order; original XLSX files unchanged",
        "dataset_kind": "unlabeled numerical surface-card references",
        "total_cards": len(records),
        "total_ordered_point_pairs": sum(row["point_pairs"] for row in records),
        "training_eligible": False,
        "exclusion": "Units, well IDs, independent fault labels, and data-specific training permission are unverified.",
        "cards": records,
    }
    manifest_path = OUT / "PROVENANCE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), **{k: manifest[k] for k in (
        "total_cards", "total_ordered_point_pairs", "training_eligible")}}, indent=2))


if __name__ == "__main__":
    main()
