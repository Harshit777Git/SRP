"""Generate isolated multi-stroke synthetic evidence; never trains an ML model."""
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"scripts"),str(ROOT),str(ROOT/"apps/srp-simulator"),str(ROOT/"apps/srp-apm")]
from evaluate_wave import compare
from physics.engine import Engine
from shared.contracts import Well
from stroke_processing.cards import build
from virtual_sensors.sampling import Sensors

TARGET=ROOT/"data/generated/phase31"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf8") as output:
        for row in rows:output.write(json.dumps(row,allow_nan=False)+"\n")


def main():
    fleet=json.loads((ROOT/"config/fleet/us_srp_30_wells.json").read_text())["wells"]
    TARGET.mkdir(parents=True,exist_ok=True)
    dynamometer=[];electrical=[];pressure=[];truth=[];cards=[];features=[];labels=[];validation=[]
    for entry in fleet:
        well=Well.model_validate(entry["well"])
        run_id=f"phase31-{well.asset_id}-{well.seed}"
        engine=Engine(well)
        sensors=Sensors(engine,run_id,datetime(2026,11,17,tzinfo=timezone.utc))
        sensors.site_id=entry["site_id"]
        previous=[];actual=[];stroke_results=[]
        limit=math.ceil(5*60/well.spm*well.dynamometer_hz)
        for index in range(limit):
            state=engine.advance(1/well.dynamometer_hz)
            sample,boundary=sensors.read(state)
            if sample:
                dynamometer.append(sample.model_dump(mode="json"))
                truth.append(dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                    sequence=sample.sequence,stroke_id=sample.stroke_id,
                    timestamp=sample.timestamp.isoformat(),pump_position_m=state["pump_position_m"],
                    pump_load_n=state["pump_load_n"],chamber_pa=state["chamber_pa"],
                    intake_pa=state["intake_pa"],fault="healthy",severity=0))
                common=dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                    timestamp=sample.timestamp.isoformat(),source_sequence=sample.sequence,
                    stroke_id=sample.stroke_id,quality="GOOD")
                if index%max(1,well.dynamometer_hz//well.electrical_hz)==0:
                    electrical.append(dict(common,motor_rpm=state["motor_rpm"],voltage_v=state["voltage_v"],
                        current_a=state["current_a"],power_w=state["power_w"],
                        gearbox_torque_nm=state["gearbox_torque_nm"]))
                if index%max(1,well.dynamometer_hz//well.pressure_hz)==0:
                    pressure.append(dict(common,tubing_pa=state["tubing_pa"],casing_pa=state["casing_pa"],
                        intake_pa=state["intake_pa"],net_delivered_m3=state["net_delivered_m3"]))
            if boundary and previous and sample:
                try:
                    card=build(previous,sample,well)
                    metrics=compare(card,actual) if card["downhole"]["status"]=="SOLVED" else {}
                    status=("SYNTHETIC_VALIDATED" if card["quality"]=="GOOD" and metrics and
                            metrics["load_rmse_fraction_of_range"]<.03 and
                            metrics["centered_position_rmse_m"]<.02 else "INVALID")
                    row=dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                             stroke_id=card["stroke_id"],status=status,samples=len(previous),
                             period_s=card["period_s"],surface_min_load_n=card["surface"]["min_load_n"],
                             surface_max_load_n=card["surface"]["max_load_n"],
                             surface_stroke_m=card["surface"]["stroke_m"],
                             surface_area_j=card["surface"]["area_j"],
                             downhole_status=card["downhole"]["status"],
                             energy_balance_status="UNAVAILABLE_MODEL_LACKS_FULL_DRIVE_ENERGY",**metrics)
                    cards.append(card);validation.append(row);stroke_results.append(row)
                    features.append(dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                        stroke_id=card["stroke_id"],surface_max_load_n=row["surface_max_load_n"],
                        surface_min_load_n=row["surface_min_load_n"],surface_stroke_m=row["surface_stroke_m"],
                        surface_area_j=row["surface_area_j"],spm=60/row["period_s"],
                        quality_status=status))
                except Exception as error:
                    row=dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                             stroke_id=previous[0].stroke_id,status="INVALID",error=str(error))
                    validation.append(row);stroke_results.append(row)
                previous=[];actual=[]
                if len(stroke_results)>=3:break
            if sample:
                previous.append(sample)
                actual.append(dict(time=sample.timestamp.timestamp(),x=state["pump_position_m"],
                                   f=state["pump_load_n"]))
        labels.append(dict(asset_id=well.asset_id,site_id=entry["site_id"],run_id=run_id,
                           origin="SIMULATED",fault_mechanism="healthy",severity=0,
                           seed=well.seed,completed_strokes=len(stroke_results)))
        print(well.asset_id,len(stroke_results),flush=True)
    ml=TARGET/"ml_inputs";isolated=TARGET/"simulation_truth";ml.mkdir(exist_ok=True);isolated.mkdir(exist_ok=True)
    outputs=[]
    for name,rows in [("dynamometer",dynamometer),("electrical",electrical),("pressure",pressure),
                      ("features",features)]:
        table=pd.DataFrame(rows)
        for suffix in ("csv","parquet"):
            path=ml/f"{name}.{suffix}"
            table.to_csv(path,index=False) if suffix=="csv" else table.to_parquet(path,index=False)
            outputs.append(path)
    for path,rows in [(ml/"cards.jsonl",cards),(isolated/"downhole_truth.jsonl",truth),
                      (isolated/"scenario_labels.jsonl",labels),(TARGET/"validation.jsonl",validation)]:
        write_jsonl(path,rows);outputs.append(path)
    config_path=TARGET/"configuration.json"
    config_path.write_text(json.dumps(fleet,indent=2));outputs.append(config_path)
    split_path=ROOT/"data/evaluation/phase3/future_split_manifest.json"
    manifest=dict(schema_version="phase3.1",origin="SYNTHETIC",model_training_performed=False,
        physics_step_s=.0067,sensor_rates_hz=dict(dynamometer=50,electrical=10,pressure=1),
        wells=len(fleet),completed_strokes=len(validation),
        valid_strokes=sum(x["status"]=="SYNTHETIC_VALIDATED" for x in validation),
        raw_dynamometer_samples=len(dynamometer),electrical_samples=len(electrical),
        pressure_samples=len(pressure),
        split_manifest=str(split_path.relative_to(ROOT)),split_sha256=sha(split_path),
        files=[dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=sha(path)) for path in outputs],
        truth_isolation="simulation_truth directory excluded from ml_inputs")
    (TARGET/"manifest.json").write_text(json.dumps(manifest,indent=2))
    summary=dict(manifest=manifest,validation=validation)
    report=ROOT/"reports/PHASE3_1/continuous_physics.json"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:manifest[k] for k in ("wells","completed_strokes","valid_strokes",
        "raw_dynamometer_samples","electrical_samples","pressure_samples")}),flush=True)


if __name__=="__main__":main()
