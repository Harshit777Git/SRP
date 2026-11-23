from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from context import ROOT, APM
import sys
sys.path.insert(0,str(APM/"backend"))
from interchange import import_file


def audit_archive(path):
    audit=dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               surface_cards=[],tam_containers=[])
    with ZipFile(path) as archive:
        audit["entries"]=archive.namelist()
        for member in archive.namelist():
            if member.lower().endswith(".dyn"):
                raw=archive.read(member)
                name=PurePosixPath(member).name
                parsed=import_file(dict(kind="surface",filename=name,content=raw.decode("ascii"),
                                well_id="DEMO",stroke_id=1,position_unit="in",load_unit="lbf",
                                provenance="Vendor training archive"))
                card=parsed["cards"][0]
                audit["surface_cards"].append(dict(file=name,sha256=hashlib.sha256(raw).hexdigest(),
                        points=parsed["records"],record_type="surface demonstration trace",
                        travel_m=card["stroke_m"],area_j=card["area_j"],label=None,well_id_verified=False,
                        training_permission_verified=False))
            elif member.lower().endswith(".tam_exp"):
                with ZipFile(BytesIO(archive.read(member))) as container:
                    entries=[i.filename for i in container.infolist() if not i.is_dir()]
                counts={kind:sum(f".{kind}." in entry for entry in entries)
                        for kind in ("DYN","ACU","CBE")}
                audit["tam_containers"].append(dict(name=member,members=len(entries),test_files=counts,
                    example_well_folders=len({PurePosixPath(e).parts[1] for e in entries if e.startswith("Wells/")}),
                    extracted_strokes=0,training_permission_verified=False))
    return audit


def main():
    evidence=ROOT/"data/evaluation"
    archive_dir=ROOT/"state/vendor"
    entries=[audit_archive(f) for f in sorted(archive_dir.glob("echometer-session*.zip"))]
    twm=Path("C:/TWM/Examples")
    tam=Path("C:/Program Files (x86)/Echometer/TAM/Documents/Echometer/TAM/Wells")
    installed=dict(twm_extension_counts=Counter(f.suffix.lower() for f in twm.iterdir() if f.is_file()) if twm.is_dir() else {},
                   tam_demo_folders=len([f for f in tam.iterdir() if f.is_dir()]) if tam.is_dir() else None,
                   tam_demo_dynamometer_test_files=sum(".DYN." in f.name for f in tam.rglob("*") if f.is_file()))
    (evidence/"real_acquisition_audit.json").write_text(json.dumps(dict(archives=entries,installed=installed),indent=2))
    print(json.dumps(dict(archives=[dict(archive=a["path"],cards=len(a["surface_cards"]),
                                         containers=a["tam_containers"]) for a in entries],installed=installed),indent=2))


if __name__=="__main__":
    main()
