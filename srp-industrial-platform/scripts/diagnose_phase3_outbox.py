"""Measure SQLite outbox without simulation or APM."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"apps/srp-simulator")]
from mqtt_publisher.outbox import Outbox


def main():
    env=os.environ.copy();env["MQTT_PORT"]="18890";os.environ["MQTT_PORT"]="18890"
    broker=subprocess.Popen(["node",str(ROOT/"scripts/test_broker.mjs")],cwd=ROOT,env=env,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        temporary=tempfile.mkdtemp(prefix="srp-outbox-")
        if True:
            outbox=Outbox(Path(temporary)/"outbox.db")
            deadline=time.monotonic()+10
            while not outbox.status()["connected"] and time.monotonic()<deadline:time.sleep(.05)
            print("connected",flush=True)
            start=time.perf_counter()
            for i in range(3000):
                outbox.append([("phase3/outbox",dict(asset_id="TEST",sequence=i),False)])
            enqueue_s=time.perf_counter()-start
            print("enqueued",flush=True)
            before=outbox.status()
            time.sleep(15)
            after=outbox.status()
            result=dict(messages=3000,enqueue_s=enqueue_s,enqueue_rate=3000/enqueue_s,
                        sent_in_15_s=after["sent"]-before["sent"],queue_before=before["queued"],
                        queue_after=after["queued"],ack_lag_s=after["ack_lag_s"])
            target=ROOT/"reports/PHASE3_1/outbox_only.json"
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2))
            print(json.dumps(result))
    finally:
        broker.terminate();broker.wait(timeout=5)


if __name__=="__main__":main()
