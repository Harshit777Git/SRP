from contextlib import ExitStack
import json
import uuid
from typing import get_args

from context import ROOT
from fault_injection.scenarios import FaultName
from run_acceptance import http, local, wait_for


def main():
    sim,apm="http://127.0.0.1:18301","http://127.0.0.1:18302"
    asset="SRP_001"
    route=f"/assets/{asset}"
    alerts={"DYNACARD_CHANGE","STROKE_RATE_CHANGE"}
    results=[]
    with ExitStack() as stack:
        local(stack,sim=18301,apm=18302,mqtt_port=18886,frontends=False,scope="fault/"+uuid.uuid4().hex[:8])
        for url in (sim,apm):
            wait_for(lambda:http(url,"/health")["connected"],url)
        run=http(sim,route+"/start",{"speed":6})["run_id"]

        def get_card(after, statuses=None):
            card=http(apm,f"/snapshot?asset={asset}").get("card")
            if card and card["run_id"]==run and card["stroke_id"]>after:
                monitor=card.get("condition_monitor",{})
                if statuses is None or monitor.get("status") in statuses:
                    return card

        for fault in (f for f in get_args(FaultName) if f!="healthy"):
            baseline=wait_for(lambda:get_card(-1,{"WITHIN_REFERENCE"}),"healthy operating reference")
            http(sim,route+"/fault",dict(kind=fault,severity=.8,duration_s=900,ramp_s=2))
            first=baseline["stroke_id"]
            card=wait_for(lambda:get_card(first+2),"complete steady fault stroke",timeout=35)
            report=card["condition_monitor"]
            results.append(dict(fault=fault,stroke=card["stroke_id"],**report))
            print(fault,report["status"],report.get("symptom",""),flush=True)
            http(sim,route+"/fault",dict(kind="healthy"))
            wait_for(lambda:get_card(card["stroke_id"]+1,{"WITHIN_REFERENCE"}),"recovery to reference",timeout=35)
    (ROOT/"data/evaluation/v2/live_fault_coverage.json").write_text(json.dumps(results,indent=2))
    assert all(row["status"] in alerts for row in results)


if __name__=="__main__":
    main()
