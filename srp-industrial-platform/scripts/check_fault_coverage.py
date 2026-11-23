from concurrent.futures import ProcessPoolExecutor
import json
from typing import get_args

from context import ROOT
from configurations.presets import presets
from evaluate_wave import cycle
from fault_detection.monitor import compare_stroke
from fault_injection.scenarios import Fault, FaultName
from physics.engine import Engine
from stroke_processing.cards import build
from virtual_sensors.sampling import Sensors


FAULTS=[name for name in get_args(FaultName) if name!="healthy"]
LEVELS=(.001,.01,.1,.5,.8,1.)


def make_reference(well):
    engine=Engine(well)
    sensor=Sensors(engine,"reference")
    buffer=[]
    cards=[]
    while len(cards)<6:
        sample,boundary=sensor.read(engine.advance(1/well.dynamometer_hz))
        if boundary:
            if buffer and sample:
                card=build(buffer,sample,well)
                if card["quality"]=="GOOD" and card["downhole"]["status"]=="SOLVED":
                    cards.append(card)
            buffer=[]
        if sample:
            buffer.append(sample)
    return cards


def sweep_asset(well):
    cards=make_reference(well)
    reference=cards[:3]
    healthy=[compare_stroke(card,reference)["status"] for card in cards[3:]]
    rows=[]
    for name in FAULTS:
        for level in LEVELS:
            try:
                card,*_=cycle(well,Fault(kind=name,severity=level))
                result=compare_stroke(card,reference)
            except (ValueError,RuntimeError) as error:
                result=dict(status="STROKE_UNAVAILABLE",error=str(error))
            rows.append(dict(fault=name,severity_pct=100*level,**result))
    return dict(asset=well.asset_id,healthy_controls=healthy,cases=rows)


def main():
    with ProcessPoolExecutor(max_workers=3) as pool:
        studies=list(pool.map(sweep_asset,presets()))
    alerts={"DYNACARD_CHANGE","STROKE_RATE_CHANGE"}
    counts={str(100*level):sum(row["status"] in alerts for study in studies for row in study["cases"]
                              if row["severity_pct"]==100*level) for level in LEVELS}
    result=dict(scope="Synthetic, steady stroke; default sensor settings",alerts_per_30_cases=counts,studies=studies)
    output=ROOT/"data/evaluation/v2/fault_severity_coverage.json"
    output.write_text(json.dumps(result,indent=2))
    print(json.dumps(counts),flush=True)
    assert all(s=="WITHIN_REFERENCE" for study in studies for s in study["healthy_controls"]), "healthy alert"
    assert all(row["status"] in alerts for study in studies for row in study["cases"]
               if row["severity_pct"]>=50), "50–100% test point missed an alert"


if __name__=="__main__":
    main()
