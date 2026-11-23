"""Measure native 30-well publish behavior; results never imply physics validation."""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORT = 18121


def api(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(f"http://127.0.0.1:{PORT}/{path}", data=data,
                         headers={"Content-Type": "application/json"} if data else {}), timeout=180) as reply:
        return json.load(reply)


def main():
    state_base = Path(os.getenv("SRP_BENCHMARK_STATE_ROOT", str(ROOT / "data/evaluation/phase3/runtime")))
    root = state_base / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(MQTT_PORT="18887", API_PORT=str(PORT), SIM_DATA=str(root),
               PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "apps/srp-simulator"),
                                            str(ROOT / ".audit_deps")]))
    logs = []
    processes = []
    try:
        for name, command in [("broker", ["node", str(ROOT / "scripts/test_broker.mjs")]),
                              ("simulator", [sys.executable, str(ROOT / "apps/srp-simulator/backend/server.py")])]:
            handle = (root / f"{name}.log").open("w")
            logs.append(handle)
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=handle,
                                              stderr=subprocess.STDOUT))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if api("health")["connected"]:
                    break
            except Exception:
                time.sleep(.25)
        else:
            raise RuntimeError("Native simulator/broker failed to become ready")
        start = time.monotonic()
        response = api("fleet/start", {"speed": 1})
        startup_s = time.monotonic() - start
        before = api("health")
        time.sleep(15)
        after = api("health")
        fleet = api("fleet")
        result = dict(origin="MEASURED_NATIVE_RUNTIME", runtime_state=str(root), benchmark_duration_s=15,
                      startup_s=startup_s, command_result=response,
                      active_wells=sum(x["mode"] == "running" for x in fleet["wells"] if x["site_id"]),
                      before=before, after=after,
                      published_delta=after["sent"] - before["sent"],
                      published_messages_per_s=(after["sent"] - before["sent"]) / 15,
                      dropped_delta=after["dropped"] - before["dropped"],
                      topic_count=len(after["topics"]))
        (ROOT / "reports/PHASE3/MQTT_MULTIWELL_BENCHMARK.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    main()
