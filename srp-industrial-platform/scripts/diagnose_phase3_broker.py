"""Measure broker/Paho capacity without physics, SQLite outbox or APM."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
PORT = 18889
TOTAL = 15000


def main():
    env = os.environ.copy()
    env["MQTT_PORT"] = str(PORT)
    process = subprocess.Popen(["node", str(ROOT / "scripts/test_broker.mjs")], cwd=ROOT,
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        received = set()
        acknowledged = set()
        lock = threading.Lock()
        listener = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="phase3-broker-subscriber")
        listener.on_connect = lambda c,u,f,r,p: c.subscribe("phase3/benchmark",qos=1)
        def on_message(c,u,m):
            with lock:
                received.add(int(m.payload))
        listener.on_message = on_message
        publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="phase3-broker-publisher")
        publisher.max_inflight_messages_set(1000)
        publisher.max_queued_messages_set(20000)
        def on_publish(c,u,mid,r,p):
            with lock:
                acknowledged.add(mid)
        publisher.on_publish = on_publish
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                listener.connect("127.0.0.1",PORT,20)
                publisher.connect("127.0.0.1",PORT,20)
                break
            except OSError:
                time.sleep(.1)
        listener.loop_start();publisher.loop_start()
        time.sleep(.5)
        start = time.perf_counter()
        for i in range(TOTAL):
            publisher.publish("phase3/benchmark", str(i),qos=1)
        queued_s = time.perf_counter()-start
        deadline = time.monotonic()+30
        while time.monotonic()<deadline and len(received)<TOTAL:
            time.sleep(.05)
        elapsed = time.perf_counter()-start
        result = dict(messages=TOTAL, enqueue_s=queued_s, elapsed_s=elapsed,
                      acknowledged=len(acknowledged), received=len(received),
                      receive_rate_per_s=len(received)/elapsed, missing=TOTAL-len(received))
        target=ROOT/"reports/PHASE3_1/broker_only.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
        publisher.disconnect();listener.disconnect()
        publisher.loop_stop();listener.loop_stop()
    finally:
        process.terminate()
        process.wait(timeout=5)


if __name__=="__main__":
    main()
