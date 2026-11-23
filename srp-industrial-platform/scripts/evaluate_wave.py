import json
from datetime import datetime, timezone

from context import ROOT
import numpy as np
from configurations.presets import presets
from fault_injection.scenarios import Fault
from physics.engine import Engine
from stroke_processing.cards import build
from surface_dynacard.geometry import area
from virtual_sensors.sampling import Sensors


def compare(card, truth):
    x = np.asarray(card["downhole"]["position_m"])
    f = np.asarray(card["downhole"]["load_n"])
    t = np.array([p["time"] for p in truth])
    phase = (t-t[0])/card["period_s"]
    grid = np.arange(len(x))/len(x)
    tx = np.interp(grid,phase,[p["x"] for p in truth],period=1)
    tf = np.interp(grid,phase,[p["f"] for p in truth],period=1)
    # Absolute displacement includes an arbitrary static origin.
    offsets = x-tx
    phase_error = np.angle(np.fft.rfft(x)[1]/np.fft.rfft(tx)[1],deg=True)
    return dict(position_rmse_m=float(np.sqrt(np.mean(offsets**2))),
                centered_position_rmse_m=float(np.std(offsets)),
                load_rmse_n=float(np.sqrt(np.mean((f-tf)**2))),
                load_rmse_fraction_of_range=float(np.sqrt(np.mean((f-tf)**2))/max(1,np.ptp(tf))),
                position_phase_deg=float(phase_error), load_correlation=float(np.corrcoef(f,tf)[0,1]),
                card_area_error_fraction=float(abs(area(x,f)-area(tx,tf))/max(1,area(tx,tf))))


def cycle(well, fault=None, run_id="synthetic"):
    e = Engine(well)
    if fault:
        fault.onset_s = e.time
        e.fault = fault
        e.warmup(3)
    sensor = Sensors(e,run_id,datetime(2026,11,16,tzinfo=timezone.utc))
    previous, truth = [], []
    for _ in range(int(4*60/well.spm*well.dynamometer_hz)):
        state = e.advance(1/well.dynamometer_hz)
        sample, boundary = sensor.read(state)
        if boundary:
            card = build(previous,sample,well) if sample else None
            if card and card["quality"]=="GOOD":
                return card,previous,truth
            previous,truth = [],[]
        if sample:
            previous.append(sample)
            truth.append(dict(time=sample.timestamp.timestamp(),x=state["pump_position_m"],f=state["pump_load_n"]))
    raise RuntimeError("No good synthetic stroke")


def main():
    results = []
    for well in presets():
        for noise in (False,True):
            w = well.model_copy(update=dict(noise_load_n=60,noise_position_m=.002)) if noise else well
            for kind in ("healthy","incomplete_fillage"):
                case = Fault(kind=kind,severity=.8)
                card,samples,truth = cycle(w,case)
                result = dict(asset=w.asset_id,depth_m=w.depth,spm=w.spm,noise=noise,fault=kind,
                              **compare(card,truth))
                results.append(result)
                if w.asset_id=="SRP_002" and not noise:
                    prefix = ROOT/"data/generated"/kind
                    prefix.with_suffix(".telemetry.jsonl").write_text("\n".join(s.model_dump_json() for s in samples)+"\n")
                    prefix.with_suffix(".truth.json").write_text(json.dumps(truth))
                    prefix.with_suffix(".card.json").write_text(json.dumps(card))
    path = ROOT/"data/evaluation/wave.json"
    path.write_text(json.dumps(dict(origin="SIMULATED",method="independent harmonic transfer vs finite-element forward",cases=results),indent=2))
    print(f"{len(results)} reconstruction cases saved to {path}")


if __name__=="__main__":
    main()
