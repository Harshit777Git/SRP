"""Native multi-process site load test with independent producer/APM counts."""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

import psutil

ROOT=Path(__file__).resolve().parents[1]
SITES=["US_TX_MIDLAND","US_NM_DELAWARE","US_ND_WILLISTON","US_OK_ANADARKO","US_CO_DJ","US_TX_EAGLEFORD"]
BROKER_PORT=18893
APM_PORT=18140
SITE_PORTS={site:18131+i for i,site in enumerate(SITES)}


def http(port,route,body=None):
    data=json.dumps(body).encode() if body is not None else None
    with urlopen(Request(f"http://127.0.0.1:{port}/{route}",data=data,
                         headers={"Content-Type":"application/json"} if data else {}),timeout=10) as response:
        return json.load(response)


def wait_ready(port,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            if http(port,"health").get("connected"):return
        except Exception:pass
        time.sleep(.15)
    raise RuntimeError(f"Service on {port} not ready")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage-seconds",type=int,default=10)
    parser.add_argument("--final-seconds",type=int,default=30)
    parser.add_argument("--restart",action="store_true")
    parser.add_argument("--counts",default="1,5,10,20,30")
    parser.add_argument("--output",default="multiwell_stages.json")
    args=parser.parse_args()
    state=Path(tempfile.mkdtemp(prefix="srp-phase31-sites-"))
    env=os.environ.copy()
    env["MQTT_PORT"]=str(BROKER_PORT)
    env["PYTHONUNBUFFERED"]="1"
    env["PYTHONPATH"]=os.pathsep.join([str(ROOT),str(ROOT/".audit_deps")])
    processes=[];handles=[];named_processes={}
    def launch(name,command,custom):
        handle=(state/f"{name}.log").open("w",encoding="utf8")
        handles.append(handle)
        process=subprocess.Popen(command,cwd=ROOT,env=dict(env,**custom),
                                 stdout=handle,stderr=subprocess.STDOUT)
        processes.append(process)
        named_processes[name]=process
        return process
    def broker(name="broker"):
        return launch(name,["node",str(ROOT/"scripts/test_broker.mjs")],{})
    try:
        broker_process=broker()
        launch("apm",[sys.executable,str(ROOT/"apps/srp-apm/backend/server.py")],
               dict(API_PORT=str(APM_PORT),APM_DATA=str(state/"apm"),
                    PYTHONPATH=os.pathsep.join([str(ROOT),str(ROOT/"apps/srp-apm"),str(ROOT/".audit_deps")])))
        for site in SITES:
            launch(site,[sys.executable,str(ROOT/"apps/srp-simulator/backend/server.py")],
                   dict(API_PORT=str(SITE_PORTS[site]),SIM_SITE_ID=site,
                        SIM_DATA=str(state/site),MQTT_CLIENT_ID=f"srp-simulator-{site}",
                        PYTHONPATH=os.pathsep.join([str(ROOT),str(ROOT/"apps/srp-simulator"),str(ROOT/".audit_deps")])))
        wait_ready(APM_PORT)
        for port in SITE_PORTS.values():wait_ready(port)
        fleet=json.loads((ROOT/"config/fleet/us_srp_30_wells.json").read_text())["wells"]
        ordered=[(entry["site_id"],entry["well"]["asset_id"]) for entry in fleet]
        active=[];stages=[]
        def snapshot():
            sim=[http(port,"health") for port in SITE_PORTS.values()]
            apm=http(APM_PORT,"health")
            ram=sum(psutil.Process(p.pid).memory_info().rss for p in processes if p.poll() is None)
            cpu={name:sum(psutil.Process(process.pid).cpu_times()[:2]) for name,process in named_processes.items()
                 if process.poll() is None}
            return dict(sent=sum(x["sent"] for x in sim),queued=sum(x["queued"] for x in sim),
                        dropped=sum(x["dropped"] for x in sim),
                        accepted=apm["counts"].get("accepted",0),
                        errors=apm["counts"].get("processing_errors",0),
                        rejected=apm["counts"].get("rejected",0),
                        ram_bytes=ram,cpu_seconds=cpu,sim=sim)
        counts=[int(value) for value in args.counts.split(",")]
        for count in counts:
            for site,asset in ordered[len(active):count]:
                http(SITE_PORTS[site],f"assets/{asset}/start",{"speed":1})
                active.append(asset)
            duration=args.final_seconds if count==30 else args.stage_seconds
            before=snapshot();start=time.monotonic()
            time.sleep(duration)
            after=snapshot();elapsed=time.monotonic()-start
            stage=dict(active_wells=count,duration_s=elapsed,
                broker_ack_rate_per_s=(after["sent"]-before["sent"])/elapsed,
                apm_persist_rate_per_s=(after["accepted"]-before["accepted"])/elapsed,
                queued_before=before["queued"],queued_after=after["queued"],
                dropped_delta=after["dropped"]-before["dropped"],
                rejected_delta=after["rejected"]-before["rejected"],
                processing_error_delta=after["errors"]-before["errors"],
                ram_before_bytes=before["ram_bytes"],ram_after_bytes=after["ram_bytes"])
            stage["cpu_core_equivalents"]={name:(value-before["cpu_seconds"].get(name,value))/elapsed
                                            for name,value in after["cpu_seconds"].items()}
            stages.append(stage)
            print(json.dumps(stage),flush=True)
        recovery=None
        if args.restart:
            before=snapshot()
            broker_process.terminate();broker_process.wait(timeout=5)
            time.sleep(3)
            during=snapshot()
            broker_process=broker("broker-restart")
            wait_ready(APM_PORT,timeout=30)
            for port in SITE_PORTS.values():wait_ready(port,timeout=30)
            time.sleep(15)
            after=snapshot()
            recovery=dict(before=before["queued"],during=during["queued"],after=after["queued"],
                          sent_after_restart=after["sent"]-during["sent"],
                          apm_accepted_after_restart=after["accepted"]-during["accepted"],
                          drops=after["dropped"]-before["dropped"])
            for site,asset in ordered[:len(active)]:
                http(SITE_PORTS[site],f"assets/{asset}/pause",{})
            deadline=time.monotonic()+30
            previous_accepted=-1;stable=0
            while time.monotonic()<deadline:
                final=snapshot()
                stable=stable+1 if final["accepted"]==previous_accepted else 0
                previous_accepted=final["accepted"]
                if final["queued"]==0 and stable>=4:break
                time.sleep(.5)
            recovery.update(final_queued=final["queued"],final_apm_accepted=final["accepted"],
                            drained=final["queued"]==0)
            print("recovery",json.dumps(recovery),flush=True)
        db=sqlite3.connect(state/"apm/apm.db")
        persisted=db.execute("select count(*) from telemetry").fetchone()[0]
        cards=db.execute("select count(*) from cards").fetchone()[0]
        per_asset=db.execute("select asset,count(*),min(sequence),max(sequence),count(distinct run) from telemetry group by asset").fetchall()
        sequence_gaps=sum(x[3]-x[2]+1-x[1] for x in per_asset if x[4]==1)
        result=dict(state=str(state),stages=stages,recovery=recovery,
                    persisted_samples=persisted,completed_cards=cards,
                    persisted_wells=len(per_asset),observed_sequence_gaps=sequence_gaps,
                    per_asset=[dict(asset_id=x[0],samples=x[1],
                        min_sequence=x[2],max_sequence=x[3],run_count=x[4]) for x in per_asset])
        target=ROOT/"reports/PHASE3_1"/args.output
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2))
        print("result",target,flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill()
        for handle in handles:handle.close()


if __name__=="__main__":main()
