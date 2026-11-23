"""Replay actual Phase 3 sensor payloads to measure APM ingestion independently."""
import json
import argparse
from datetime import datetime, timedelta
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import paho.mqtt.client as mqtt

ROOT=Path(__file__).resolve().parents[1]
BROKER_PORT=18891
API_PORT=18122


def health():
    with urlopen(f"http://127.0.0.1:{API_PORT}/health",timeout=5) as reply:
        return json.load(reply)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cycles",type=int,default=1)
    args=parser.parse_args()
    state=Path(tempfile.mkdtemp(prefix="srp-apm-bench-"))
    env=os.environ.copy()
    env.update(MQTT_PORT=str(BROKER_PORT),API_PORT=str(API_PORT),APM_DATA=str(state),
               PYTHONPATH=os.pathsep.join([str(ROOT),str(ROOT/"apps/srp-apm"),str(ROOT/".audit_deps")]))
    handles=[(state/"broker.log").open("w"),(state/"apm.log").open("w")]
    processes=[]
    try:
        for command,handle in [(["node",str(ROOT/"scripts/test_broker.mjs")],handles[0]),
            ([sys.executable,str(ROOT/"apps/srp-apm/backend/server.py")],handles[1])]:
            processes.append(subprocess.Popen(command,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            try:
                if health()["connected"]:break
            except Exception:time.sleep(.1)
        else:raise RuntimeError("APM/broker not ready")
        samples=[]
        for path in sorted((ROOT/"data/evaluation/phase3").glob("*.sensor.jsonl")):
            asset=path.name.split(".sensor.jsonl")[0]
            original=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if not original:continue
            start=datetime.fromisoformat(original[0]["timestamp"])
            period=60/original[0]["spm"]
            for cycle in range(args.cycles):
                for sample in original:
                    copy=dict(sample)
                    copy["sequence"]+=cycle*len(original)
                    copy["stroke_id"]+=cycle
                    copy["timestamp"]=(datetime.fromisoformat(sample["timestamp"])+timedelta(seconds=cycle*period)).isoformat()
                    samples.append((f"srp/v1/{asset}/telemetry/dynamometer",json.dumps(copy)))
        publisher=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="phase31-apm-replay")
        publisher.max_inflight_messages_set(1000)
        publisher.max_queued_messages_set(len(samples)+100)
        publisher.connect("127.0.0.1",BROKER_PORT,20)
        publisher.loop_start()
        start=time.perf_counter()
        for topic,payload in samples:
            publisher.publish(topic,payload,qos=1)
        publish_enqueue_s=time.perf_counter()-start
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            accepted=health()["counts"].get("accepted",0)
            if accepted>=len(samples):break
            time.sleep(.1)
        elapsed=time.perf_counter()-start
        counts=health()["counts"]
        db=sqlite3.connect(state/"apm.db")
        persisted=db.execute("select count(*) from telemetry").fetchone()[0]
        assets=db.execute("select count(distinct asset) from telemetry").fetchone()[0]
        cards=db.execute("select count(*) from cards").fetchone()[0]
        result=dict(state=str(state),cycles=args.cycles,submitted=len(samples),publish_enqueue_s=publish_enqueue_s,
                    elapsed_s=elapsed,accepted=counts.get("accepted",0),persisted=persisted,
                    active_wells=assets,cards=cards,ingest_rate_per_s=persisted/elapsed,
                    counts=counts)
        target=ROOT/"reports/PHASE3_1/apm_only.json";target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2));print(json.dumps(result))
        publisher.disconnect();publisher.loop_stop()
    finally:
        for process in reversed(processes):
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        for handle in handles:handle.close()


if __name__=="__main__":main()
