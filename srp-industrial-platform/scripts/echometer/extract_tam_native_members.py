"""Losslessly preserve non-JSON native members embedded in TAM_EXP archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for archive in sorted(args.state_root.glob("STATE-*/01_TAM/*.TAM_EXP")):
        state_id = archive.parents[1].name
        output_root = archive.parent / "EXTRACTED_NATIVE_MEMBERS"
        with ZipFile(archive) as package:
            for info in package.infolist():
                if info.is_dir() or info.filename in {"metadata.json", "TestResults.json"}:
                    continue
                relative = PurePosixPath(info.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Unsafe TAM archive member: {info.filename}")
                data = package.read(info.filename)
                member_hash = digest(data)
                flattened_name = "__".join(relative.parts)
                destination = output_root / flattened_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and file_digest(destination) != member_hash:
                    raise FileExistsError(f"Non-identical extracted member already exists: {destination}")
                if not destination.exists():
                    destination.write_bytes(data)
                category = (
                    "TEST" if "/Tests/" in f"/{info.filename}"
                    else "VERSION" if "/Versions/" in f"/{info.filename}"
                    else "HEADER" if info.filename.endswith(".{HEADER}")
                    else "OTHER"
                )
                rows.append({
                    "state_id": state_id,
                    "source_archive": str(archive.resolve()),
                    "source_archive_sha256": file_digest(archive),
                    "member_path": info.filename,
                    "member_category": category,
                    "member_bytes": len(data),
                    "member_sha256": member_hash,
                    "extracted_path": str(destination.resolve()),
                })

    args.report.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "state_id", "source_archive", "source_archive_sha256", "member_path",
        "member_category", "member_bytes", "member_sha256", "extracted_path",
    ]
    with args.report.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "states_with_archives": len({row["state_id"] for row in rows}),
        "members": len(rows),
        "categories": {
            category: sum(row["member_category"] == category for row in rows)
            for category in ("HEADER", "VERSION", "TEST", "OTHER")
        },
        "manifest": str(args.report.resolve()),
    }
    args.report.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
