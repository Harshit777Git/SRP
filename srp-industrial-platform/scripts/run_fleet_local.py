"""Launch configured field simulators, gateway, APM and browser frontends."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
import socket
from contextlib import ExitStack
from pathlib import Path

from context import ROOT, SIM, APM
from run_acceptance import http, wait_for


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--state-dir",type=Path)
    parser.add_argument("--sim-api-port",type=int,default=18001)
    parser.add_argument("--apm-api-port",type=int,default=18002)
    parser.add_argument("--sim-ui-port",type=int,default=13001)
    parser.add_argument("--apm-ui-port",type=int,default=13002)
    parser.add_argument("--site-port-base",type=int,default=18131)
    parser.add_argument("--mqtt-port",type=int,default=18883)
    args=parser.parse_args()
    launch_lock=(Path(tempfile.gettempdir())/f'srp-fleet-{args.sim_api_port}-{args.apm_api_port}.lock').open('a+b')
    if launch_lock.tell()==0:launch_lock.write(b'0');launch_lock.flush()
    launch_lock.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(launch_lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(launch_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('A fleet launcher already owns these API ports; refusing duplicate startup')
    state=(args.state_dir or Path(tempfile.gettempdir())/'srp_dataset_120_20hz').resolve()
    state.mkdir(parents=True,exist_ok=True)
    fleet_path=ROOT/'config/fleet/dataset_120_calibrated.json'
    if not fleet_path.exists():
        fleet_path=ROOT/'config/fleet/us_srp_30_wells.json'
    sites=sorted({entry["site_id"] for entry in json.loads(fleet_path.read_text())["wells"]})
    for port in [args.sim_api_port,args.apm_api_port,args.sim_ui_port,args.apm_ui_port,args.mqtt_port,
                 *range(args.site_port_base,args.site_port_base+len(sites))]:
        try:
            with socket.socket() as probe:probe.bind(('127.0.0.1',port))
        except OSError as error:
            raise SystemExit(f'Port {port} is unavailable; refusing partial fleet startup: {error}')
    common=dict(os.environ,MQTT_PORT=str(args.mqtt_port),MQTT_HOST="127.0.0.1",
                PYTHONUNBUFFERED="1",CARD_POINTS="200",SITE_PORT_BASE=str(args.site_port_base),
                SIM_FLEET_PATH=str(fleet_path),SIM_AUTO_START='1',API_HOST='127.0.0.1')
    dynacard_model = ROOT/'data/training/dynacard_fault_model.joblib'
    contour_model = dynacard_model if dynacard_model.exists() else ROOT/'data/training/downhole_contour.joblib'
    if contour_model.exists():
        common.update(SRP_MODEL_PATH=str(contour_model),SRP_ALLOW_EXPERIMENTAL_MODEL='1',SRP_PROBABILITY_MODEL_PATH='')
    processes=[]
    with ExitStack() as stack:
        def launch(name,command,environment):
            output=stack.enter_context((state/f"{name}.log").open("w",encoding="utf8"))
            child=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT)
            processes.append(child)
            return child
        launch("broker",[shutil.which("node"),str(ROOT/"scripts/test_broker.mjs")],common)
        apm_env=dict(common,API_PORT=str(args.apm_api_port),APM_DATA=str(state/"apm"),
                     APM_ASSETS="",
                     PYTHONPATH=os.pathsep.join([str(ROOT),str(APM),common.get("PYTHONPATH","")]))
        launch("apm",[sys.executable,str(APM/"backend/server.py")],apm_env)
        for index,site in enumerate(sites):
            sim_env=dict(common,API_PORT=str(args.site_port_base+index),SIM_SITE_ID=site,
                         SIM_DATA=str(state/site),MQTT_CLIENT_ID=f"srp-simulator-{site}",
                         PYTHONPATH=os.pathsep.join([str(ROOT),str(SIM),common.get("PYTHONPATH","")]))
            launch(site,[sys.executable,str(SIM/"backend/server.py")],sim_env)
        gateway_env=dict(common,API_PORT=str(args.sim_api_port),
                         PYTHONPATH=os.pathsep.join([str(ROOT),str(SIM),common.get("PYTHONPATH","")]))
        launch("gateway",[sys.executable,str(SIM/"backend/fleet_gateway.py")],gateway_env)
        for name,app,ui_port,api_port in (("sim-ui",SIM,args.sim_ui_port,args.sim_api_port),
                                          ("apm-ui",APM,args.apm_ui_port,args.apm_api_port)):
            launch(name,[shutil.which("node"),"node_modules/vite/bin/vite.js",str(app/"frontend"),
                "--host","127.0.0.1","--port",str(ui_port),"--strictPort"],
                dict(common,VITE_API_URL=f"http://127.0.0.1:{api_port}"))
        def manifest(status):
            (ROOT/'state/dataset_runtime.json').write_text(json.dumps(dict(launcher_pid=os.getpid(),child_pids=[p.pid for p in processes],
                state_dir=str(state),sim_api_port=args.sim_api_port,apm_api_port=args.apm_api_port,status=status),indent=2))
        manifest('starting')
        try:
            for port in [args.apm_api_port,args.sim_api_port]:
                wait_for(lambda p=port:http(f"http://127.0.0.1:{p}","/health").get("connected"),
                         f"fleet API {port}",timeout=900)
            manifest('ready')
            print(f"Simulator: http://127.0.0.1:{args.sim_ui_port}",flush=True)
            print(f"APM: http://127.0.0.1:{args.apm_ui_port}",flush=True)
            print("Fleet started automatically. Press Ctrl+C to stop.",flush=True)
            while True:time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill()


if __name__=="__main__":main()
