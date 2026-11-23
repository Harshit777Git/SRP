"""Matched fleet-wide physics sensitivity, never classifier training."""
import copy
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"apps/srp-simulator"),str(ROOT/"apps/srp-apm")]
from fault_injection.scenarios import Fault
from physics.engine import Engine
from shared.contracts import Well,LBF,INCH
from stroke_processing.cards import build
from virtual_sensors.sampling import Sensors

FAULTS=["incomplete_fillage","gas_interference","traveling_valve_leak",
        "standing_valve_leak","rod_friction","pump_wear","restricted_inflow",
        "load_cell_drift","position_sensor_fault","abnormal_speed"]
SEVERITIES=(.2,.8)


def collect(engine,well,run_id):
    sensor=Sensors(engine,run_id,datetime(2026,11,17,tzinfo=timezone.utc))
    previous=[];states=[]
    limit=math.ceil(3*60/well.spm*well.dynamometer_hz)
    for _ in range(limit):
        state=engine.advance(1/well.dynamometer_hz)
        sample,boundary=sensor.read(state)
        if boundary and previous and sample:
            card=build(previous,sample,well)
            if card["quality"]=="GOOD":
                return card,previous,states
            previous=[];states=[]
        if sample:
            previous.append(sample);states.append(state)
    raise RuntimeError("No completed stroke")


def signal(card,key):
    data=card[key]
    if data.get("status") not in (None,"SOLVED"):
        return None,None
    x=np.asarray(data["position_m"]);load=np.asarray(data["load_n"])
    phase=np.linspace(0,1,len(x),endpoint=False);grid=np.linspace(0,1,200,endpoint=False)
    return np.interp(grid,phase,x,period=1),np.interp(grid,phase,load,period=1)


def rmse(a,b):
    return float(np.sqrt(np.mean((a-b)**2)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=30)
    args=parser.parse_args()
    fleet=json.loads((ROOT/"config/fleet/us_srp_30_wells.json").read_text())["wells"]
    fleet=fleet[:args.limit]
    target=ROOT/"reports/PHASE3_1/fault_observability.jsonl"
    target.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    with target.open("w",encoding="utf8") as output:
        for entry in fleet:
            well=Well.model_validate(entry["well"])
            base=Engine(well)
            healthy_engine=copy.deepcopy(base)
            healthy_engine.warmup(2)
            healthy,healthy_samples,healthy_states=collect(healthy_engine,well,"healthy")
            hx,hf=signal(healthy,"surface");hdx,hdf=signal(healthy,"downhole")
            for severity in SEVERITIES:
                for kind in FAULTS:
                    try:
                        engine=copy.deepcopy(base)
                        engine.fault=Fault(kind=kind,severity=severity,ramp_s=0,onset_s=engine.time)
                        engine.warmup(2)
                        card,samples,states=collect(engine,well,f"{kind}-{severity}")
                        x,f=signal(card,"surface");dx,df=signal(card,"downhole")
                        row=dict(site_id=entry["site_id"],asset_id=well.asset_id,
                            mechanism=kind,severity=severity,status="MEASURED_SYNTHETIC_SENSITIVITY",
                            surface_load_rmse_n=rmse(hf,f),surface_position_rmse_m=rmse(hx,x),
                            downhole_load_rmse_n=rmse(hdf,df) if df is not None and hdf is not None else None,
                            downhole_position_rmse_m=rmse(hdx,dx) if dx is not None and hdx is not None else None,
                            downhole_status=card["downhole"]["status"],
                            raw_load_mean_delta_n=(sum(s.polished_rod_load_lbf for s in samples)/len(samples)-
                                                   sum(s.polished_rod_load_lbf for s in healthy_samples)/len(healthy_samples))*LBF,
                            motor_current_mean_delta_a=(sum(s["current_a"] for s in states)/len(states)-
                                                        sum(s["current_a"] for s in healthy_states)/len(healthy_states)),
                            chamber_pressure_mean_delta_pa=(sum(s["chamber_pa"] for s in states)/len(states)-
                                                           sum(s["chamber_pa"] for s in healthy_states)/len(healthy_states)),
                            intake_pressure_mean_delta_pa=(sum(s["intake_pa"] for s in states)/len(states)-
                                                          sum(s["intake_pa"] for s in healthy_states)/len(healthy_states)),
                            delivered_volume_delta_m3=((states[-1]["net_delivered_m3"]-states[0]["net_delivered_m3"])-
                                                      (healthy_states[-1]["net_delivered_m3"]-healthy_states[0]["net_delivered_m3"])))
                    except Exception as error:
                        row=dict(site_id=entry["site_id"],asset_id=well.asset_id,
                                 mechanism=kind,severity=severity,status="FAILED",error=str(error))
                    results.append(row)
                    output.write(json.dumps(row,allow_nan=False)+"\n")
                    output.flush()
            print(well.asset_id,len(results),flush=True)
    summary=dict(wells=len(fleet),mechanisms=FAULTS,severities=SEVERITIES,
                 cases=len(results),failed=sum(x["status"]=="FAILED" for x in results),
                 study="MATCHED_SYNTHETIC_SENSITIVITY_NOT_DIAGNOSTIC_ACCURACY")
    (ROOT/"reports/PHASE3_1/fault_observability_summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=="__main__":main()
