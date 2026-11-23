"""One simulator API for independently running site processes."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shared.http_api import serve

ROOT=Path(__file__).resolve().parents[3]
default_fleet = ROOT/"config/fleet/dataset_120_calibrated.json"
if not default_fleet.exists():
    default_fleet = ROOT/"config/fleet/us_srp_30_wells.json"
FLEET=json.loads(Path(os.getenv("SIM_FLEET_PATH",str(default_fleet))).read_text())["wells"]
SITES=sorted({entry["site_id"] for entry in FLEET})
PORTS={site:int(os.getenv("SITE_PORT_BASE","18131"))+index for index,site in enumerate(SITES)}
ASSET_SITE={entry["well"]["asset_id"]:entry["site_id"] for entry in FLEET}


def forward(site,method,route,query=None,body=None):
    query_text=("?"+urlencode(query)) if query else ""
    payload=json.dumps(body).encode() if method=="POST" else None
    request=Request(f"http://127.0.0.1:{PORTS[site]}/"+"/".join(route)+query_text,
                    data=payload,headers={"Content-Type":"application/json"} if payload else {})
    try:
        with urlopen(request,timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code==404:raise KeyError() from error
        try:message=json.load(error).get("error",str(error))
        except Exception:message=str(error)
        raise ValueError(message) from error


def aggregate_health():
    parts=[forward(site,"GET",["health"]) for site in SITES]
    return dict(ready=all(p["ready"] for p in parts),connected=all(p["connected"] for p in parts),
                queued=sum(p["queued"] for p in parts),sent=sum(p["sent"] for p in parts),
                dropped=sum(p["dropped"] for p in parts),
                retry_failures=sum(p["retry_failures"] for p in parts),
                ack_lag_s=max(p["ack_lag_s"] for p in parts),
                topics=sorted({topic for p in parts for topic in p["topics"]}))


def dispatch(method,route,query,body):
    if route==["health"]:return aggregate_health()
    if route==["assets"] and method=="GET":
        return [well for site in SITES for well in forward(site,"GET",route)
                if well["asset_id"] in ASSET_SITE]
    if route==["fleet"] and method=="GET":
        parts=[forward(site,"GET",route) for site in SITES]
        return dict(site_ids=SITES,wells=[well for p in parts for well in p["wells"]
                                        if well["asset_id"] in ASSET_SITE])
    if route==["reference-cards"]:return forward(SITES[0],method,route,query,body)
    if route==["snapshot"]:
        asset=query.get("asset","SRP_001")
        site=ASSET_SITE.get(asset,SITES[0])
        snapshot=forward(site,"GET",route,query)
        snapshot["mqtt"]=aggregate_health()
        return snapshot
    if len(route)==2 and route[0]=="fleet" and route[1] in ("start","stop","pause","resume","speed"):
        parts=[forward(site,method,route,query,body) for site in SITES]
        return dict(action=route[1],target_count=sum(p["target_count"] for p in parts),
                    running=sum(p["running"] for p in parts))
    if len(route)==3 and route[0]=="sites":
        if route[1] not in PORTS:raise KeyError()
        return forward(route[1],method,route,query,body)
    if len(route)==3 and route[0]=="assets":
        site=ASSET_SITE.get(route[1])
        if site is None:raise KeyError()
        return forward(site,method,route,query,body)
    raise KeyError()


if __name__=="__main__":
    serve(int(os.getenv("API_PORT","8001")),dispatch)
