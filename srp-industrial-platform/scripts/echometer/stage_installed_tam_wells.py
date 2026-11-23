"""Stage installed TAM example records into the state library without altering TAM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    with MATRIX.open(encoding="utf-8-sig", newline="") as stream:
        by_name = {row["Original State Name"].casefold(): row["State ID"] for row in csv.DictReader(stream)}

    known_hashes: dict[str, str] = {}
    for path in args.state_root.glob("STATE-*/01_TAM/EXTRACTED_NATIVE_MEMBERS/*"):
        if path.is_file():
            known_hashes.setdefault(sha256(path), str(path.resolve()))

    rows: list[dict[str, object]] = []
    unmatched: list[str] = []
    for well_dir in sorted(path for path in args.installed_root.iterdir() if path.is_dir()):
        well_name = well_dir.name.rsplit("_{", 1)[0]
        state_id = by_name.get(well_name.casefold())
        if not state_id:
            unmatched.append(str(well_dir))
            continue
        destination_root = args.state_root / state_id / "01_TAM" / "INSTALLED_TAM_NATIVE"
        for source in sorted(path for path in well_dir.rglob("*") if path.is_file()):
            relative = source.relative_to(well_dir)
            destination = destination_root / relative
            source_hash = sha256(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and sha256(destination) != source_hash:
                raise FileExistsError(f"Refusing to overwrite non-identical file: {destination}")
            if not destination.exists():
                shutil.copy2(source, destination)
            name_upper = source.name.upper()
            category = (
                "DYN" if ".DYN." in name_upper
                else "ACU" if ".ACU." in name_upper
                else "CBE" if ".CBE." in name_upper
                else "PLIFT" if ".PLIFT." in name_upper
                else "HEADER" if source.name.endswith(".{HEADER}")
                else "CONFIGURATION"
            )
            rows.append({
                "state_id": state_id,
                "well_name": well_name,
                "category": category,
                "source_path": str(source.resolve()),
                "relative_path": str(relative),
                "bytes": source.stat().st_size,
                "sha256": source_hash,
                "duplicate_of_tam_exp_member": known_hashes.get(source_hash, ""),
                "staged_path": str(destination.resolve()),
            })

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "state_id", "well_name", "category", "source_path", "relative_path", "bytes",
        "sha256", "duplicate_of_tam_exp_member", "staged_path",
    ]
    with args.manifest.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "matched_states": len({row["state_id"] for row in rows}),
        "files": len(rows),
        "categories": {
            category: sum(row["category"] == category for row in rows)
            for category in ("DYN", "ACU", "CBE", "PLIFT", "HEADER", "CONFIGURATION")
        },
        "duplicate_members": sum(bool(row["duplicate_of_tam_exp_member"]) for row in rows),
        "unmatched_directories": unmatched,
        "manifest": str(args.manifest.resolve()),
    }
    args.manifest.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
