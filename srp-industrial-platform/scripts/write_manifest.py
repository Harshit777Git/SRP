import hashlib
import json
from datetime import datetime, timezone

from context import ROOT

RESULT = ROOT/"data/dataset_manifest.json"
DATA = ROOT/"data"
CSV_ROOT = "https://raw.githubusercontent.com/mulzahrian/production_optimization/main/csv_file/"
COLUMNS = [
    "Well Name","Card Time","Card Type","Stroke Period","SPM","Stroke Length","Hours Since Gauge Off",
    "Surface Max Load","Surface Min Load","PositionLimit","Surface Positions","Surface Loads",
    "Downhole Positions","Downhole Loads",
]
REFERENCE = "https://pure.unileoben.ac.at/ws/files/7159006/2021_Eisner_Langbauer_Fruhwirth_Sucker_rod_pump_downhole_dynamometer_card_determination_based_on_a_novel_finite_element_method_Paper.pdf"


def file_record(path):
    return dict(path=str(path.relative_to(ROOT)).replace(chr(92),"/"),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                file_timestamp_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat())


def main():
    entries = []
    for suffix,rows in (("2020-10-2",43),("2020-9-28",33)):
        entries.append(dict(title=f"ExportedDynaCards_{suffix}",source_url=CSV_ROOT+f"ExportedDynaCards_{suffix}.csv",
                            license_status="No repository license identified. Numerical files excluded.",
                            candidate_rows=rows,valid_cards=None,wells=None,download_timestamp=None,path=None,
                            sha256=None,columns=COLUMNS,units="Not explicitly annotated in header",
                            labels="Card Type present, semantics and validation unknown",
                            available_parameters="Period, SPM, stroke length and load extrema",
                            status="DERIVED_CARD_EXPORT",origin="Unverified surface origin and downhole reconstruction method",
                            suitability="Reference for controller export layout"))
    report = DATA/"external_reference/Eisner-Langbauer-Fruhwirth-2021.pdf"
    record = file_record(report)
    entries.append(dict(record,title="Sucker rod pump downhole dynamometer card determination based on a novel finite element method",
                        source_url=REFERENCE,doi="10.21595/lger.2021.22004",license_status="Creative Commons Attribution",
                        download_timestamp=record["file_timestamp_utc"],raw_records=0,wells=None,columns=[],
                        units="Engineering units in paper figures and tables",labels=[],
                        available_parameters="Rod mechanics, well data and published figure comparisons",
                        status="ENGINEERING_REFERENCE",origin="Published validation study",suitability="Model-method reference"))
    for filename in sorted(DATA.glob("generated/*")):
        if not filename.is_file():
            continue
        fault=filename.name.split(".")[0]
        info=file_record(filename)
        telemetry=filename.name.endswith(".jsonl")
        contents=filename.read_text().splitlines() if telemetry else json.loads(filename.read_text())
        if telemetry:
            columns=list(json.loads(contents[0]))
        elif isinstance(contents,list):
            columns=list(contents[0])
        else:
            columns=list(contents)
        entries.append(dict(info,title=filename.name,source_url=None,generated_by="scripts/evaluate_wave.py",
                            origin="SIMULATED",license_status="Workspace-generated engineering example",
                            records=len(contents) if isinstance(contents,list) else 1,wells=1,columns=columns,
                            units="UTC, inches, lbf, degrees, SPM" if telemetry else "SI, UTC seconds for truth",
                            labels=[] if telemetry else [fault],available_parameters="SRP_002 synthetic equipment preset",
                            status="RAW_SIMULATED_MEASUREMENTS" if telemetry else "SIMULATION_TRUTH_OR_DERIVED_CARD",
                            suitability="Pipeline and synthetic reconstruction verification"))
    training=DATA/"training/simulated_cards.npz"
    if training.exists():
        import numpy as np
        with np.load(training) as table:
            entries.append(dict(file_record(training),title=training.name,source_url=None,
                                generated_by="scripts/train_models.py",origin="SIMULATED",
                                license_status="Workspace-generated training dataset",records=len(table["labels"]),
                                wells=len(set(table["groups"])),labels=sorted(set(table["labels"])),
                                columns=table.files,units="Fixed channel scales recorded in NPZ, features use SI and SPM",
                                available_parameters="Serialized equipment configurations and data quality",
                                status="DERIVED",suitability="Simulated-only train/calibration/held-out evaluation"))
    evaluation=DATA/"evaluation"
    result=evaluation/"acceptance.json"
    if result.exists():
        acceptance=json.loads(result.read_text())
        for name,description in (("mqtt_capture.jsonl","Raw MQTT samples stored and exported by APM"),
                                 ("acceptance_truth.jsonl","Simulation truth from isolated simulator storage"),
                                 ("acceptance_cards.json","Healthy and fault card pairs from APM")):
            path=evaluation/name
            if not path.is_file():
                continue
            content=path.read_text().splitlines() if name.endswith(".jsonl") else json.loads(path.read_text())
            columns=list(json.loads(content[0])) if name.endswith(".jsonl") and content else list(content)
            entries.append(dict(file_record(path),title=name,source_url=None,generated_by="scripts/run_acceptance.py",
                                origin="SIMULATED",license_status="Workspace-generated acceptance evidence",
                                records=len(content),wells=1,asset_id=acceptance.get("asset"),
                                run_id=acceptance.get("run_id"),columns=columns,
                                units="UTC, inches, lbf, degrees, SPM" if name=="mqtt_capture.jsonl" else "SI and UTC",
                                labels=["healthy","traveling_valve_leak"] if name=="acceptance_truth.jsonl" else [],
                                available_parameters=description,status="ACCEPTANCE_EVIDENCE",
                                suitability="MQTT and paired reconstruction verification"))
    RESULT.write_text(json.dumps({"datasets":entries},indent=2))


if __name__=="__main__":
    main()
