"""Read-only vendor inventory and extraction of standalone ASCII demo traces."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/engineering_reference/echometer"
SOURCES = {
    "qrod_install": Path("C:/Program Files (x86)/Echometer/QRod 3"),
    "twm_examples": Path("C:/TWM/Examples"),
    "tam_install": Path("C:/Program Files (x86)/Echometer/TAM"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    entries = []
    for source, base in SOURCES.items():
        if not base.is_dir():
            entries.append(dict(source=source, path=str(base), status="NOT_FOUND"))
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relevant = (source == "twm_examples" or
                        source == "tam_install" and (".DYN." in path.name.upper() or
                                                    path.name.upper().endswith(".DYN")) or
                        source == "qrod_install" and path.suffix.lower() in (".qrd", ".dyn"))
            if not relevant:
                continue
            data = path.read_bytes()
            entries.append(dict(source=source, path=str(path), bytes=len(data), sha256=sha(data),
                                status="NATIVE_FORMAT_NOT_EXPORTED", numerical_points=None,
                                permission="PERMISSION_UNVERIFIED"))
    archive = ROOT / "state/vendor/echometer-session20.zip"
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            if not member.lower().endswith(".dyn"):
                continue
            data = z.read(member)
            lines = data.decode("ascii").splitlines()
            count = int(lines[0].strip())
            points = [tuple(map(float, line.split(","))) for line in lines[1:count+1]]
            if len(points) != count or not all(len(pair) == 2 for pair in points):
                raise ValueError(f"Invalid card {member}")
            target = DEST / Path(member).name
            target.write_bytes(data)
            entries.append(dict(source="session20_ascii", path=str(archive), member=member,
                                extracted_path=str(target.relative_to(ROOT)), bytes=len(data),
                                sha256=sha(data), status="NUMERICAL_SURFACE_CARD_EXTRACTED",
                                numerical_points=count, original_units="in,lbf",
                                origin="DEMONSTRATION_UNVERIFIED", permission="BENCHMARK_ONLY"))
    manifest = dict(schema_version="phase3.1", archive_sha256=sha(archive.read_bytes()),
                    records=entries, numerical_extracted=sum(x.get("status") == "NUMERICAL_SURFACE_CARD_EXTRACTED" for x in entries))
    (ROOT / "data/engineering_reference/echometer_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(dict(inventoried=len(entries), extracted=manifest["numerical_extracted"])))


if __name__ == "__main__":
    main()
