import os, sys, shutil, signal, glob, tempfile, subprocess
from pathlib import Path

# 1. Stop all processes
print("Stopping existing processes...")
runtime_path = r'C:\Users\HARSHIT\OneDrive - TAS\Desktop\SRP\srp-industrial-platform\state\dataset_runtime.json'
try:
    import json
    if os.path.exists(runtime_path):
        with open(runtime_path, 'r') as f:
            data = json.load(f)
        pids = [data.get('launcher_pid')] + data.get('child_pids', [])
        for p in pids:
            if p:
                try: os.kill(p, signal.SIGTERM)
                except OSError: pass
except Exception as e:
    print('Runtime stop notice:', e)

# Also kill any python/node processes on the ports
import socket
for port in [8001, 8002, 13001, 13002, 18883, 18131, 18132, 18133, 18134]:
    try:
        cmd = f'powershell -Command "(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess"'
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        for pid_str in out.split():
            try:
                p = int(pid_str)
                os.kill(p, signal.SIGTERM)
                print(f"Killed port {port} owner {p}")
            except (ValueError, OSError):
                pass
    except Exception:
        pass

# Clean locks
for lock in glob.glob(os.path.join(tempfile.gettempdir(), 'srp-fleet-*.lock')):
    try: os.remove(lock)
    except OSError: pass

# 2. Reset state_dir so outboxes and telemetry start fresh
state_dir = Path(tempfile.gettempdir()) / "srp_dataset_120_live"
if state_dir.exists():
    print(f"Clearing stale state_dir: {state_dir}...")
    try:
        shutil.rmtree(state_dir)
        print("Cleared.")
    except Exception as e:
        print("Notice during clearing:", e)

state_dir.mkdir(parents=True, exist_ok=True)
print("State directory is clean and ready.")
