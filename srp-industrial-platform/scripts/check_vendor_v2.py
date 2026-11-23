import argparse
import hashlib
import json
import sys
from zipfile import ZipFile

from context import APM, ROOT
sys.path.insert(0,str(APM/"backend"))
from interchange import benchmark, import_file


def main():
    p=argparse.ArgumentParser()
    p.add_argument("training_archive")
    args=p.parse_args()
    reference_json=ROOT/"data/evaluation/v2/reference_stroke.json"
    reference=json.loads(reference_json.read_text()) if reference_json.exists() else None
    evidence=[]
    with ZipFile(args.training_archive) as archive:
        for path in archive.namelist():
            if not path.lower().endswith(".dyn"):
                continue
            file=archive.read(path)
            filename=path.rsplit("/",1)[-1]
            result=import_file(dict(kind="surface",filename=filename,content=file.decode("ascii"),
                well_id="OVERTRAVEL" if filename.startswith("Overtravel") else "UNDERTRAVEL",
                stroke_id=1,position_unit="in",load_unit="lbf",provenance="Echometer session 20 training examples"))
            count=132 if filename.startswith("Overtravel") else 216
            assert result["records"]==count
            assert result["cards"][0]["time_s"] is None
            assert result["cards"][0]["sample_index"]==list(range(count))
            card=result["cards"][0]
            comparison=benchmark(reference,card,result["provenance"],False) if reference else None
            if comparison:
                assert comparison["alignment"]=="GEOMETRY_ONLY" and comparison["rmse_n"] is None
            evidence.append(dict(filename=filename,records=count,sha256=hashlib.sha256(file).hexdigest(),
                sample_order="preserved",stroke_m=card["stroke_m"],min_load_n=card["min_load_n"],
                max_load_n=card["max_load_n"],area_j=card["area_j"],comparison=comparison))
    assert len(evidence)==2
    (ROOT/"data/evaluation/v2/vendor_examples.json").write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))


if __name__=="__main__":
    main()
