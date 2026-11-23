"""Read-only inventory of the specifically supplied OneDrive archive."""
import collections
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\HARSHIT\Downloads\OneDrive_2026-11-16 (2).zip")
OUTPUT = ROOT / "data/evaluation/onedrive_zip_inventory.json"
DEST = ROOT / "data/external_reference/onedrive_2026-11-16_2"
KEEP = {".001",".002",".003",".004",".005",".006",".007",".008",".010",".011",".012",".013",".014",".016",".017",".018",".019",".023",".029",".072",".073",".076",".080",".081",".088",".089",".106",".qrd",".xls",".txt",".pdf",".jpg"}

def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    digest = hashlib.file_digest(SOURCE.open("rb"), "sha256").hexdigest()
    entries = []
    names = collections.Counter()
    total = 0
    with zipfile.ZipFile(SOURCE) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename.replace("\\", "/"))
            unsafe = parts.is_absolute() or ".." in parts.parts or "" in parts.parts
            mode = info.external_attr >> 16
            symlink = stat.S_ISLNK(mode)
            encrypted = bool(info.flag_bits & 1)
            names[info.filename.lower()] += 1
            total += info.file_size
            entries.append(dict(path=info.filename,compressed_bytes=info.compress_size,
                                bytes=info.file_size,extension=Path(info.filename).suffix.lower(),
                                nested_archive=Path(info.filename).suffix.lower() in (".zip",".7z",".rar",".tar"),
                                encrypted=encrypted,symlink=symlink,unsafe_path=unsafe,
                                compression_ratio=round(info.file_size/max(1,info.compress_size),2),
                                crc=info.CRC))
        inner=[]
        for outer in archive.infolist():
            if Path(outer.filename).suffix.lower() != ".zip" or outer.file_size > 300_000_000:
                continue
            raw=archive.read(outer)
            with zipfile.ZipFile(BytesIO(raw)) as nested:
                corrupt=nested.testzip()
                for member in nested.infolist():
                    path=PurePosixPath(member.filename.replace("\\","/"))
                    inner.append(dict(container=outer.filename,path=member.filename,bytes=member.file_size,
                                      compressed_bytes=member.compress_size,extension=Path(member.filename).suffix.lower(),
                                      encrypted=bool(member.flag_bits&1),unsafe_path=path.is_absolute() or ".." in path.parts,
                                      crc=member.CRC))
                    if member.is_dir() or member.flag_bits&1:
                        continue
                    content=nested.read(member)
                    inner[-1]["sha256"]=hashlib.sha256(content).hexdigest()
                    if member.is_dir() or Path(member.filename).suffix.lower() not in KEEP:
                        continue
                    if path.is_absolute() or ".." in path.parts or member.file_size>25_000_000 or member.flag_bits&1:
                        continue
                    target=DEST.joinpath(*path.parts)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():
                        target.write_bytes(content)
                    elif target.read_bytes()!=content:
                        raise ValueError(f"Conflicting existing acquisition file: {target}")
                    inner[-1]["retained_path"]=target.relative_to(ROOT).as_posix()
                    inner[-1]["first_bytes_hex"]=content[:16].hex()
        inner_corrupt=corrupt if inner else None
    result=dict(source=str(SOURCE),bytes=SOURCE.stat().st_size,sha256=digest,entry_count=len(entries),
                uncompressed_bytes=total,extensions=dict(collections.Counter(e["extension"] for e in entries)),
                nested_archives=[e["path"] for e in entries if e["nested_archive"]],
                duplicate_names=[n for n,c in names.items() if c>1],
                unsafe_paths=[e["path"] for e in entries if e["unsafe_path"]],
                encrypted=[e["path"] for e in entries if e["encrypted"]],
                symlinks=[e["path"] for e in entries if e["symlink"]],
                very_large=[e["path"] for e in entries if e["bytes"]>2_000_000_000 or e["compression_ratio"]>1000],
                entries=entries,inner_entry_count=len(inner),inner_extensions=dict(collections.Counter(e["extension"] for e in inner)),
                inner_unsafe_paths=[e["path"] for e in inner if e["unsafe_path"]],
                inner_encrypted=[e["path"] for e in inner if e["encrypted"]],
                inner_corrupt=inner_corrupt,
                inner_duplicate_content_groups=[g for g in
                    ([(e["path"],e["bytes"],e["sha256"]) for e in inner if e.get("sha256")==key]
                     for key,count in collections.Counter(e.get("sha256") for e in inner if e.get("sha256")).items() if count>1)
                    if len(g)>1],inner_entries=inner)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("entries","inner_entries")},indent=2))
    print("FIRST_INNER_PATHS",json.dumps([e["path"] for e in inner[:60]]))

if __name__ == "__main__":
    main()
