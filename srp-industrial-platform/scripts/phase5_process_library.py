"""Resume Phase 5 from verified exports; never infer missing strokes or projects."""
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from import_vendor_reference import four_column, dyn_surface  # noqa: E402

DATA = ROOT / "data" / "state93"
REPORT = ROOT / "reports" / "STATE93" / "PHASE5"
MATRIX = ROOT / "reports" / "STATE93" / "93_STATE_COMPATIBILITY_MATRIX.csv"
DIRECTORIES = ["01_TAM", "02_TWM", "03_AWP2000", "04_QROD", "05_NUMERICAL_DATA",
               "06_ENGINEERING_CONFIGURATION", "07_APM_RECONSTRUCTION",
               "08_DIAGNOSTIC_EVIDENCE", "09_VALIDATION"]
PILOT = {
    "STATE-001": {"test":"1995-06-07_215400", "stroke":"4", "reported_strokes":4,
                  "comment":"Unanchored Tubing - 071440.D01"},
    "STATE-002": {"test":"2002-01-11_012908", "stroke":"99", "reported_strokes":99,
                  "comment":"Anchored Tubing and Deep Fluid Level - Dynamometer Test"},
    "STATE-003": {"test":"1997-12-13_045700", "stroke":"1", "reported_strokes":5,
                  "comment":"Asphaltenes Sticking TV - TV goes on Seat at different Points"},
    "STATE-004": {"test":"1995-02-25_100152", "stroke":"7", "reported_strokes":7,
                  "comment":"Example in TWM Manual - v11TTD24.D01"},
    "STATE-005": {"test":"1996-02-22_043000", "stroke":"5", "reported_strokes":5,
                  "comment":"Repaired Tail Bearing - After Repair Tail Bearing"},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)


def write_xlsx(path, rows):
    book = Workbook()
    sheet = book.active; sheet.title = "Evidence"
    if rows:
        sheet.append(list(rows[0].keys()))
        for row in rows:
            sheet.append([json.dumps(v) if isinstance(v, (list, dict)) else v for v in row.values()])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="17324D")
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(70, max(14, max(len(str(c.value or "")) for c in column[:100]) + 2))
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def pilot_state(state_id, name):
    meta = PILOT[state_id]
    base = DATA / state_id
    test_dir = base / "05_NUMERICAL_DATA" / "TAM" / ("test_" + meta["test"])
    # Phase 5.1 adds stroke-specific files beside the original pilot export.
    # Keep the historical Phase 5 manifest tied to its original pair.
    txts = [p for p in test_dir.glob("*.txt") if "_stroke-" not in p.name]
    dyns = [p for p in test_dir.glob("*.dyn") if "_stroke-" not in p.name]
    pdfs = list((base / "06_ENGINEERING_CONFIGURATION" / "TAM").glob("*.pdf"))
    if len(txts) != 1 or len(dyns) != 1 or len(pdfs) != 1:
        raise ValueError(f"{state_id}: expected one TXT/DYN/Summary pilot set")
    txt, dyn, pdf = txts[0], dyns[0], pdfs[0]
    manifest_path = base/"09_VALIDATION"/"phase5_manifest.json"
    normalized = base / "05_NUMERICAL_DATA" / "normalized" / ("test_"+meta["test"])
    source_files = [{"path":str(p.resolve()),"bytes":p.stat().st_size,"sha256":sha(p),"format":p.suffix.lower()}
                    for p in (txt,dyn,pdf)]
    expected = [normalized/(label+suffix) for label in ("surface","vendor_pump") for suffix in (".csv",".parquet")]
    if manifest_path.exists() and all(p.exists() for p in expected):
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("source_files") == source_files:
            return previous
    raw, surface = four_column(txt), dyn_surface(dyn)
    if len(raw) != len(surface):
        raise ValueError(f"{state_id}: TXT/DYN point count differs")
    dx = float(np.max(np.abs(raw[:,0] - surface[:,0])))
    dy = float(np.max(np.abs(raw[:,1]*1000 - surface[:,1])))
    if dx > 1e-5 or dy > .05:
        raise ValueError(f"{state_id}: TXT/DYN surface mismatch")
    for label, x, y, status in (("surface",raw[:,0],raw[:,1]*1000,"TAM_EXPORTED_SURFACE"),
                                ("vendor_pump",raw[:,2],raw[:,3]*1000,"TAM_CALCULATED_PUMP")):
        rows = [{"state_id":state_id,"test_id":meta["test"],"stroke_id":meta["stroke"],
                 "sample_index":i,"position_in":float(a),"load_lbf":float(b),"source_status":status}
                for i,(a,b) in enumerate(zip(x,y))]
        write_csv(normalized/(label+".csv"), rows)
        pq.write_table(pa.Table.from_pylist(rows), normalized/(label+".parquet"))
    manifest = {"state_id":state_id,"state_name":name,"source_application":"TAM",
                "test_id":meta["test"],"selected_stroke_id":meta["stroke"],
                "reported_test_strokes":meta["reported_strokes"],"exported_unique_strokes":1,
                "sample_count":len(raw),"surface_load_unit":"lbf","pump_load_unit":"lbf",
                "position_unit":"in","pdf_configuration_status":"ORIGINAL_PDF_COLLECTED_NOT_ENGINEERING_REVIEWED",
                "vendor_comment":meta["comment"],"diagnostic_label_status":"COMMENT_ONLY_NOT_FIELD_VERIFIED",
                "txt_dyn_surface_max_position_difference_in":dx,
                "txt_dyn_surface_max_load_difference_lbf":dy,"source_files":source_files,
                "apm_reconstruction":"BLOCKED_REVIEWED_CONFIGURATION_REQUIRED"}
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    source = list(csv.DictReader(MATRIX.open(encoding="utf-8-sig")))
    if len(source) != 93 or len({r["State ID"] for r in source}) != 93:
        raise ValueError("Expected exact 93-state source matrix")
    previous_path = REPORT / "PROCESSING_CHECKPOINT.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {"states":{}}
    states = dict(previous.get("states",{}))
    completion=[]; numerical=[]; engineering=[]; labels=[]; benchmarks=[]; qrod=[]; awp=[]; features=[]; ml=[]
    for r in source:
        sid,name=r["State ID"],r["Original State Name"]
        base=DATA/sid
        for folder in DIRECTORIES:
            (base/folder).mkdir(parents=True,exist_ok=True)
        evidence = None
        if sid in PILOT:
            evidence = pilot_state(sid,name)
            stage="NUMERICAL_EXTRACTED"
        elif sid=="STATE-077":
            validation=json.loads((ROOT/"reports"/"STATE93"/"STATE077_IMPORT_VALIDATION.json").read_text())
            stage="BENCHMARKED" if validation["readback_passed"] else "PARTIAL"
        else:
            stage=states.get(sid,{}).get("status","DISCOVERED")
        states[sid]={"state_name":name,"status":stage,"source_tam_files":int(r["TAM Original"]),
                     "source_twm_files":int(r["TWM Original"]),
                     "next_action":"Export each DYN test and completed stroke from TAM" if int(r["TAM Original"]) else "Verify supported TWM-to-TAM import",
                     "error":None}
        if evidence:
            states[sid].update(exported_unique_strokes=1,reported_test_strokes=evidence["reported_test_strokes"],
                               sample_count=evidence["sample_count"],manifest=str(base/"09_VALIDATION"/"phase5_manifest.json"))
        if sid=="STATE-077":
            states[sid].update(exported_unique_strokes=1,reported_test_strokes=32,sample_count=174,
                               next_action="Export remaining DYN tests and completed strokes")
        # Checkpoint after each state so interruption retains completed progress.
        previous_path.write_text(json.dumps({"schema":"phase5-checkpoint/1","updated_utc":datetime.now(timezone.utc).isoformat(),
                                             "states":states},indent=2),encoding="utf-8")
        count=states[sid].get("sample_count",0)
        completion.append({"State ID":sid,"State":name,"Status":stage,"TAM native sources":int(r["TAM Original"]),
                           "TWM native sources":int(r["TWM Original"]),"TAM open verified":sid in PILOT or sid=="STATE-077",
                           "Numerical exported strokes":states[sid].get("exported_unique_strokes",0),
                           "Reported strokes in inspected test":states[sid].get("reported_test_strokes",""),
                           "Numerical point count per exported stroke":count,"Summary PDF collected":bool(evidence) or sid=="STATE-077",
                           "APM reconstructed strokes":1 if sid=="STATE-077" else 0,"Missing next step":states[sid]["next_action"]})
        if count:
            numerical.append({"State ID":sid,"State":name,"Test ID":evidence["test_id"] if evidence else "2003-03-13_020920",
                              "Selected stroke ID":evidence["selected_stroke_id"] if evidence else "1 (pilot identity)",
                              "Surface points":count,"Vendor Pump points":count,"APM Pump points":count if sid=="STATE-077" else 0,
                              "TXT/DYN surface agreement":bool(evidence) or sid=="STATE-077",
                              "Source manifest":str(base/"09_VALIDATION"/"phase5_manifest.json") if evidence else str(ROOT/"data"/"STATE93"/"pilot"/"STATE-077"/"source_manifest.json")})
        engineering.append({"State ID":sid,"State":name,"Summary PDF collected":bool(evidence) or sid=="STATE-077",
                            "Reviewed solver configuration":sid=="STATE-077","Rod string complete":"NO" if sid=="STATE-077" else "UNVERIFIED",
                            "Missing parameters":"61-ft rod-depth gap; verified pump intake conditions" if sid=="STATE-077" else "Not assessed; review engineering PDF and required application inputs"})
        labels.append({"State ID":sid,"State":name,"Vendor comment":evidence["vendor_comment"] if evidence else "",
                       "Evidence class":"VENDOR_COMMENT" if evidence else "UNVERIFIED",
                       "Field-confirmed diagnosis":False,"Stroke-wide label assigned":False})
        qrod.append({"State ID":sid,"State":name,"Status":"MISSING_REQUIRED_INPUTS" if sid=="STATE-077" else "NOT_ASSESSED","Native design saved/reopened":False})
        awp.append({"State ID":sid,"State":name,"Status":"MISSING_REQUIRED_INPUTS" if sid=="STATE-077" else "NOT_ASSESSED","Native analysis saved/reopened":False})
        features.append({"State ID":sid,"State":name,"Surface card":bool(count),"Vendor Pump Card":bool(count),
                         "APM Pump Card":sid=="STATE-077","Summary PDF":bool(evidence) or sid=="STATE-077",
                         "Reviewed configuration":sid=="STATE-077","Verified per-sample timestamps":False})
        ml.append({"State ID":sid,"State":name,"Numerical candidate":bool(count),
                   "Verified diagnostic label":False,"Source-rights review complete":False,
                   "Training eligible now":False})
    validation=json.loads((ROOT/"reports"/"STATE93"/"STATE077_IMPORT_VALIDATION.json").read_text())
    benchmarks.append({"State ID":"STATE-077","State":"Tagging Down Hard","Exported stroke count":1,
                       **validation["metrics"]})
    outputs={"STATE_COMPLETION_MATRIX":completion,"NUMERICAL_CARD_INVENTORY":numerical,
             "ENGINEERING_CONFIGURATION_DICTIONARY":engineering,"FAULT_LABEL_CATALOG":labels,
             "ALL_STATE_SOLVER_BENCHMARKS":benchmarks,"QROD_COMPATIBILITY_MATRIX":qrod,
             "AWP2000_COMPATIBILITY_MATRIX":awp,"AVAILABLE_FEATURES":features,"ML_DATA_READINESS":ml}
    for name,rows in outputs.items():
        write_csv(REPORT/(name+".csv"),rows)
        write_xlsx(REPORT/(name+".xlsx"),rows)
    summary={"states":93,"tam_open_verified":sum(r["TAM open verified"] for r in completion),
             "exported_unique_strokes":sum(r["Numerical exported strokes"] for r in completion),
             "surface_points":sum(r["Surface points"] for r in numerical),
             "vendor_pump_points":sum(r["Vendor Pump points"] for r in numerical),
             "apm_pump_points":sum(r["APM Pump points"] for r in numerical),
             "states_numerical_exported":len(numerical),"native_qrod_created":0,"native_awp_created":0,
             "reported_strokes_not_yet_exported":sum(max(0,int(r["Reported strokes in inspected test"] or 0)-int(r["Numerical exported strokes"])) for r in completion)}
    (REPORT/"PHASE5_COUNTS.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
