"""Extract the user-provided nested TWM example bundle into reference-only storage."""
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\HARSHIT\Downloads\OneDrive_2026-11-16 (2).zip")
AUDIT = ROOT / "reports/PHASE3_2/ONEDRIVE_ARCHIVE_AUDIT.json"
DEST = ROOT / "data/external_reference/onedrive_twm_examples"
CHUNK = 1024 * 1024
MAX_TOTAL = 2_000_000_000


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def safe_target(root, name):
    normalized = name.replace("\\", "/")
    rel = PurePosixPath(normalized)
    if rel.is_absolute() or ".." in rel.parts or (rel.parts and ":" in rel.parts[0]):
        raise ValueError(f"Unsafe archive path: {name}")
    target = (root / Path(*rel.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Archive path escaped output directory: {name}")
    return target


def main():
    if DEST.exists():
        raise FileExistsError(f"Refusing to overwrite existing reference bundle: {DEST}")
    archive_audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    expected_archive_sha = archive_audit["archive_sha256"]
    if digest_file(SOURCE) != expected_archive_sha:
        raise ValueError("The supplied ZIP changed after the audit; refusing extraction")
    outer_audit = archive_audit["nested_archive_inventories"][0]
    if outer_audit["inspection"] != "COMPLETE":
        raise ValueError("Nested TWM archive did not pass safe inventory")
    expected_hashes = {row["name"]: row.get("content_sha256") for row in outer_audit["entries"]}
    if outer_audit["total_uncompressed_bytes"] > MAX_TOTAL:
        raise ValueError("Nested archive exceeds extraction size limit")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".onedrive_twm_examples_", dir=DEST.parent))
    extracted = []
    try:
        with zipfile.ZipFile(SOURCE) as outer:
            nested_info = outer.getinfo("OneDrive_2026-11-16.zip")
            with tempfile.TemporaryFile() as nested_stream:
                with outer.open(nested_info) as source:
                    shutil.copyfileobj(source, nested_stream, length=CHUNK)
                nested_stream.seek(0)
                with zipfile.ZipFile(nested_stream) as bundle:
                    bad = bundle.testzip()
                    if bad:
                        raise zipfile.BadZipFile(f"Nested archive CRC failed for {bad}")
                    for info in bundle.infolist():
                        mode = info.external_attr >> 16
                        if stat.S_ISLNK(mode):
                            raise ValueError(f"Symlink not permitted: {info.filename}")
                        target = safe_target(staging, info.filename)
                        if info.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        if info.flag_bits & 1:
                            raise ValueError(f"Encrypted member not extracted: {info.filename}")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        digest = hashlib.sha256()
                        written = 0
                        with bundle.open(info) as member, target.open("xb") as dest:
                            while chunk := member.read(CHUNK):
                                written += len(chunk)
                                if written > info.file_size or written > MAX_TOTAL:
                                    raise ValueError(f"Unexpected expansion while extracting {info.filename}")
                                digest.update(chunk)
                                dest.write(chunk)
                        actual = digest.hexdigest()
                        if expected_hashes.get(info.filename) != actual:
                            raise ValueError(f"Content hash mismatch: {info.filename}")
                        extracted.append({"name": info.filename, "bytes": written, "sha256": actual})
        if len(extracted) != outer_audit["file_count"]:
            raise RuntimeError(f"Extracted {len(extracted)} files; audit listed {outer_audit['file_count']}")
        provenance = {
            "dataset_id": "onedrive-twm-example-bundle",
            "source_archive": str(SOURCE),
            "source_archive_sha256": expected_archive_sha,
            "nested_archive": "OneDrive_2026-11-16.zip",
            "nested_archive_sha256": next(row.get("content_sha256") for row in archive_audit["entries"]
                                           if row["name"] == "OneDrive_2026-11-16.zip"),
            "extracted_at": "2026-11-17",
            "extracted_files": len(extracted),
            "training_eligible": False,
            "permission_status": "PERMISSION_UNVERIFIED",
            "data_origin": "ECHOMETER_TWM_TUTORIAL_DEMONSTRATION_UNKNOWN_MEASURED_OR_SIMULATED",
            "use": "Reference-only local TWM engineering examples; no fault labels inferred from filenames.",
            "files": extracted,
        }
        (staging / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        staging.replace(DEST)
    except Exception:
        # Keep staging evidence for review; never delete the original archive.
        raise
    print(json.dumps({"destination": str(DEST), "files_extracted": len(extracted),
                      "bytes": sum(row["bytes"] for row in extracted),
                      "training_eligible": False, "permission_status": "PERMISSION_UNVERIFIED"}, indent=2))


if __name__ == "__main__":
    main()
