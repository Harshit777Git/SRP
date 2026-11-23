"""Safely inventory the exact user-specified OneDrive archive without extracting it."""
import collections
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

SOURCE = Path(r"C:\Users\HARSHIT\Downloads\OneDrive_2026-11-16 (2).zip")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/PHASE3_2/ONEDRIVE_ARCHIVE_AUDIT.json"
MAX_ENTRIES = 100_000
MAX_TOTAL_UNCOMPRESSED = 2_000_000_000
MAX_MEMBER_UNCOMPRESSED = 500_000_000
HASH_CHUNK = 1024 * 1024
DATA_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx", ".json", ".parquet", ".txt",
                   ".mat", ".npz", ".npy", ".h5", ".hdf5", ".sqlite", ".db", ".dyn",
                   ".pdf", ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz"}


def sha256_stream(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(HASH_CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def safe_member_name(name):
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not (path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", normalized))


def inspect_nested(parent, info, depth=1):
    label = info.filename
    if depth > 3:
        return {"name": label, "depth": depth, "inspection": "DEPTH_LIMIT"}
    if info.file_size > MAX_MEMBER_UNCOMPRESSED:
        return {"name": label, "depth": depth, "inspection": "SIZE_LIMIT",
                "uncompressed_bytes": info.file_size}
    try:
        with tempfile.TemporaryFile() as temp:
            with parent.open(info) as source:
                shutil.copyfileobj(source, temp, length=HASH_CHUNK)
            temp.seek(0)
            with zipfile.ZipFile(temp) as child:
                infos = child.infolist()
                total = sum(member.file_size for member in infos if not member.is_dir())
                if len(infos) > MAX_ENTRIES or total > MAX_TOTAL_UNCOMPRESSED:
                    return {"name": label, "depth": depth, "inspection": "CHILD_LIMIT",
                            "entry_count": len(infos), "total_uncompressed_bytes": total}
                ext_counts = collections.Counter()
                child_entries = []
                dup_hashes = collections.defaultdict(list)
                unsafe = []
                encrypted_members = []
                nested_children = []
                bad = []
                for member in infos:
                    member_ext = Path(member.filename).suffix.lower()
                    mode = member.external_attr >> 16
                    symlink = stat.S_ISLNK(mode)
                    safe = safe_member_name(member.filename)
                    if member_ext in DATA_EXTENSIONS:
                        ext_counts[member_ext] += 1
                    if not safe or symlink:
                        unsafe.append(member.filename)
                    if member.flag_bits & 1:
                        encrypted_members.append(member.filename)
                    row = {"name": member.filename, "directory": member.is_dir(),
                           "extension": member_ext, "compressed_bytes": member.compress_size,
                           "uncompressed_bytes": member.file_size, "safe_path": safe,
                           "symlink": symlink, "encrypted": bool(member.flag_bits & 1),
                           "crc32": f"{member.CRC:08x}"}
                    if member.is_dir() or not safe or symlink or member.flag_bits & 1:
                        pass
                    elif member.file_size > MAX_MEMBER_UNCOMPRESSED:
                        row["content_hash_skipped"] = "SIZE_LIMIT"
                    else:
                        try:
                            with child.open(member) as payload:
                                row["content_sha256"] = sha256_stream(payload)
                            dup_hashes[row["content_sha256"]].append(member.filename)
                        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
                            row["read_error"] = str(error)
                            bad.append({"name": member.filename, "error": str(error)})
                    child_entries.append(row)
                    if member_ext == ".zip":
                        nested_children.append(inspect_nested(child, member, depth + 1))
                try:
                    crc_failure = child.testzip()
                except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
                    crc_failure = None
                    bad.append({"name": None, "error": f"Archive test failed: {error}"})
                if crc_failure:
                    bad.append({"name": crc_failure, "error": "CRC failure from ZipFile.testzip"})
                duplicates = [names for names in dup_hashes.values() if len(names) > 1]
                return {"name": label, "depth": depth, "inspection": "COMPLETE",
                        "entry_count": len(child_entries),
                        "file_count": sum(not row["directory"] for row in child_entries),
                        "directory_count": sum(row["directory"] for row in child_entries),
                        "total_uncompressed_bytes": total,
                        "extension_counts": dict(sorted(ext_counts.items())),
                        "nested_archives": [row["name"] for row in nested_children],
                        "nested_archive_inventories": nested_children,
                        "duplicate_content_groups": duplicates, "corrupt_entries": bad,
                        "encrypted_entries": encrypted_members, "unsafe_or_symlink_entries": unsafe,
                        "entries": child_entries}
    except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
        return {"name": label, "depth": depth, "inspection": "FAILED", "error": str(error)}


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Required archive missing: {SOURCE}")
    archive_hash = hashlib.sha256()
    with SOURCE.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK):
            archive_hash.update(chunk)
    entries = []
    extension_counts = collections.Counter()
    duplicate_names = collections.Counter()
    duplicate_content = collections.defaultdict(list)
    nested_archives = []
    corrupt = []
    unsafe_names = []
    encrypted = []
    total_uncompressed = 0
    skipped_content_hash = []
    nested_inventories = []
    with zipfile.ZipFile(SOURCE) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_ENTRIES:
            raise RuntimeError(f"Archive has {len(infos)} entries; safety ceiling is {MAX_ENTRIES}")
        total_uncompressed = sum(info.file_size for info in infos if not info.is_dir())
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            raise RuntimeError(f"Archive expands to {total_uncompressed} bytes; safety ceiling is {MAX_TOTAL_UNCOMPRESSED}")
        names = [info.filename for info in infos]
        duplicate_names.update(name for name, count in collections.Counter(names).items() if count > 1)
        for info in infos:
            name = info.filename
            ext = Path(name).suffix.lower()
            mode = info.external_attr >> 16
            is_symlink = stat.S_ISLNK(mode)
            safe = safe_member_name(name)
            if not safe or is_symlink:
                unsafe_names.append(name)
            if info.flag_bits & 0x1:
                encrypted.append(name)
            if ext in DATA_EXTENSIONS:
                extension_counts[ext] += 1
            if ext in {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz"}:
                nested_archives.append(name)
            row = {"name": name, "directory": info.is_dir(), "extension": ext,
                   "compressed_bytes": info.compress_size, "uncompressed_bytes": info.file_size,
                   "safe_path": safe, "symlink": is_symlink, "encrypted": bool(info.flag_bits & 0x1),
                   "crc32": f"{info.CRC:08x}"}
            if info.is_dir() or not safe or is_symlink or info.flag_bits & 0x1:
                pass
            elif info.file_size > MAX_MEMBER_UNCOMPRESSED:
                skipped_content_hash.append(name)
            else:
                try:
                    with bundle.open(info) as member:
                        row["content_sha256"] = sha256_stream(member)
                    duplicate_content[row["content_sha256"]].append(name)
                except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
                    row["read_error"] = str(error)
                    corrupt.append({"name": name, "error": str(error)})
            entries.append(row)
        try:
            corrupt_member = bundle.testzip()
        except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as error:
            corrupt_member = None
            corrupt.append({"name": None, "error": f"Archive test failed: {error}"})
        if corrupt_member:
            corrupt.append({"name": corrupt_member, "error": "CRC failure from ZipFile.testzip"})
        nested_inventories = [inspect_nested(bundle, info) for info in infos
                              if Path(info.filename).suffix.lower() == ".zip" and not info.is_dir()
                              and safe_member_name(info.filename) and not (info.flag_bits & 1)]
    duplicate_groups = [names for names in duplicate_content.values() if len(names) > 1]
    report = {
        "source_path": str(SOURCE),
        "exists": True,
        "archive_bytes": SOURCE.stat().st_size,
        "archive_sha256": archive_hash.hexdigest(),
        "entry_count": len(entries),
        "file_count": sum(not item["directory"] for item in entries),
        "directory_count": sum(item["directory"] for item in entries),
        "total_uncompressed_bytes": total_uncompressed,
        "extension_counts": dict(sorted(extension_counts.items())),
        "nested_archives": nested_archives,
        "nested_archive_inventories": nested_inventories,
        "duplicate_names": dict(duplicate_names),
        "duplicate_content_groups": duplicate_groups,
        "corrupt_entries": corrupt,
        "encrypted_entries": encrypted,
        "unsafe_or_symlink_entries": unsafe_names,
        "content_hash_skipped_oversize": skipped_content_hash,
        "entries": entries,
        "extraction_performed": False,
        "executables_or_macros_run": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "source_path", "archive_bytes", "archive_sha256", "entry_count", "file_count",
        "directory_count", "total_uncompressed_bytes", "extension_counts", "nested_archives",
        "duplicate_content_groups", "corrupt_entries", "encrypted_entries", "unsafe_or_symlink_entries",
        "content_hash_skipped_oversize", "extraction_performed")}, indent=2))
    print(f"Detailed inventory: {OUT}")


if __name__ == "__main__":
    main()
