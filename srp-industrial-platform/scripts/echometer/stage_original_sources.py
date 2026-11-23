"""Copy only inventoried vendor originals into the 93-state library, with hashes.

The authoritative source directories come from the existing 93-state matrix.
Synthetic assumed CSVs are deliberately excluded. Existing files are never
overwritten; mismatching destinations cause an error.
"""
import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"
DEST = ROOT / "data" / "state93"
REPORT = ROOT / "reports" / "STATE93" / "PHASE5_1"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    matrix = list(csv.DictReader(MATRIX.open(encoding="utf-8-sig")))
    if len(matrix) != 93:
        raise ValueError("Expected 93 inventoried states")
    provenance = {"schema": "vendor-original-staging/1", "states": {}}
    for row in matrix:
        sid = row["State ID"]
        source = Path(row["Original Directory"])
        records = []
        for sub, destination in (("Original TAM", "01_TAM"), ("Original TWM", "02_TWM")):
            original_root = source / sub
            if not original_root.is_dir():
                continue
            for original in sorted(p for p in original_root.rglob("*") if p.is_file()):
                rel = original.relative_to(original_root)
                target = DEST / sid / destination / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                original_hash = sha(original)
                if target.exists():
                    if sha(target) != original_hash:
                        raise ValueError(f"Existing destination differs: {target}")
                else:
                    shutil.copy2(original, target)
                    if sha(target) != original_hash:
                        raise ValueError(f"Copy verification failed: {target}")
                records.append({"source": str(original.resolve()), "destination": str(target.resolve()),
                                "bytes": original.stat().st_size, "sha256": original_hash,
                                "source_class": sub})
        provenance["states"][sid] = {"state_name": row["Original State Name"], "original_files": records}
    REPORT.mkdir(parents=True, exist_ok=True)
    path = REPORT / "VENDOR_ORIGINAL_PROVENANCE.json"
    path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    counts = {"states": len(provenance["states"]),
              "tam_source_files": sum(r["source_class"] == "Original TAM" for s in provenance["states"].values() for r in s["original_files"]),
              "twm_source_files": sum(r["source_class"] == "Original TWM" for s in provenance["states"].values() for r in s["original_files"])}
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
