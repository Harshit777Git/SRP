"""Audit the requested 96-state Echometer acquisition library.

The authoritative inventory currently identifies 93 named states.  The final
three rows remain explicit unresolved slots until their source names and paths
are supplied or discovered.  No placeholder is counted as collected data.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "state93"
REPORT = ROOT / "reports" / "STATE96"
MATRIX = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_for(folder: Path, suffix: str) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == suffix)


def pdf_kind(paths: list[Path], words: tuple[str, ...]) -> list[Path]:
    return [p for p in paths if any(word in p.stem.casefold() for word in words)]


def joined(paths: list[Path]) -> str:
    return " | ".join(str(p.resolve()) for p in paths)


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    with MATRIX.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))

    rows: list[dict[str, object]] = []
    file_manifest: list[dict[str, object]] = []
    for source in source_rows:
        state_id = source["State ID"]
        folder = DATA / state_id
        tam = files_for(folder / "01_TAM", ".tam_exp")
        dyn = files_for(folder, ".dyn")
        pdfs = files_for(folder, ".pdf")
        summary = pdf_kind(pdfs, ("summary", "field summary"))
        history = pdf_kind(pdfs, ("test history", "test_history", "history report"))
        rows.append(
            {
                "State ID": state_id,
                "State Name": source["Original State Name"],
                "Identity Status": "IDENTIFIED",
                "State Directory": str(folder.resolve()),
                "TAM_EXP Count": len(tam),
                "TAM_EXP Status": "COLLECTED" if tam else "MISSING",
                "DYN File Count": len(dyn),
                "All Strokes DYN Status": "PARTIAL" if dyn else "MISSING",
                "Field Summary Count": len(summary),
                "Field Summary Status": "COLLECTED" if summary else "MISSING",
                "Test History Count": len(history),
                "Test History Status": "COLLECTED" if history else "MISSING",
                "TAM_EXP Paths": joined(tam),
                "DYN Paths": joined(dyn),
                "Field Summary Paths": joined(summary),
                "Test History Paths": joined(history),
            }
        )
        for kind, paths in (("TAM_EXP", tam), ("DYN", dyn), ("FIELD_SUMMARY", summary), ("TEST_HISTORY", history)):
            for path in paths:
                file_manifest.append(
                    {
                        "State ID": state_id,
                        "State Name": source["Original State Name"],
                        "Asset Type": kind,
                        "Path": str(path.resolve()),
                        "Bytes": path.stat().st_size,
                        "SHA256": sha256(path),
                    }
                )

    for number in range(94, 97):
        rows.append(
            {
                "State ID": f"STATE-{number:03d}",
                "State Name": "",
                "Identity Status": "SOURCE_STATE_NOT_IDENTIFIED",
                "State Directory": "",
                "TAM_EXP Count": 0,
                "TAM_EXP Status": "BLOCKED_MISSING_STATE_IDENTITY",
                "DYN File Count": 0,
                "All Strokes DYN Status": "BLOCKED_MISSING_STATE_IDENTITY",
                "Field Summary Count": 0,
                "Field Summary Status": "BLOCKED_MISSING_STATE_IDENTITY",
                "Test History Count": 0,
                "Test History Status": "BLOCKED_MISSING_STATE_IDENTITY",
                "TAM_EXP Paths": "",
                "DYN Paths": "",
                "Field Summary Paths": "",
                "Test History Paths": "",
            }
        )

    matrix_path = REPORT / "96_STATE_ACQUISITION_MATRIX.csv"
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest_path = REPORT / "COLLECTED_ASSET_MANIFEST.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["State ID", "State Name", "Asset Type", "Path", "Bytes", "SHA256"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(file_manifest)

    summary = {
        "requested_states": 96,
        "identified_states": len(source_rows),
        "unidentified_states": 96 - len(source_rows),
        "states_with_tam_exp": sum(int(row["TAM_EXP Count"] > 0) for row in rows),
        "tam_exp_files": sum(int(row["TAM_EXP Count"]) for row in rows),
        "states_with_dyn": sum(int(row["DYN File Count"] > 0) for row in rows),
        "dyn_files": sum(int(row["DYN File Count"]) for row in rows),
        "states_with_field_summary": sum(int(row["Field Summary Count"] > 0) for row in rows),
        "field_summary_files": sum(int(row["Field Summary Count"]) for row in rows),
        "states_with_test_history": sum(int(row["Test History Count"] > 0) for row in rows),
        "test_history_files": sum(int(row["Test History Count"]) for row in rows),
        "matrix": str(matrix_path.resolve()),
        "asset_manifest": str(manifest_path.resolve()),
    }
    (REPORT / "COLLECTION_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
