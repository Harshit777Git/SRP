import argparse
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.request import urlopen

from context import ROOT
from run_acceptance import http, local, wait_for


def main():
    parser = argparse.ArgumentParser(description="Launch the native SRP simulator, APM and local MQTT broker")
    parser.add_argument("--sim-api-port",type=int,default=18001)
    parser.add_argument("--apm-api-port",type=int,default=18002)
    parser.add_argument("--sim-ui-port",type=int,default=13001)
    parser.add_argument("--apm-ui-port",type=int,default=13002)
    parser.add_argument("--mqtt-port",type=int,default=18883)
    parser.add_argument("--model",type=Path)
    args = parser.parse_args()
    with ExitStack() as stack:
        local(stack,args.model,args.sim_api_port,args.apm_api_port,args.sim_ui_port,args.apm_ui_port,
              args.mqtt_port,scope="desktop",probability_model=ROOT/"data/training/remediation_physics_features.joblib")
        for port in (args.sim_api_port,args.apm_api_port):
            wait_for(lambda:http(f"http://127.0.0.1:{port}","/health").get("connected"),f"API and MQTT on {port}")
        for name,port in (("Simulator",args.sim_ui_port),("APM",args.apm_ui_port)):
            with urlopen(f"http://127.0.0.1:{port}",timeout=10):
                print(f"{name} UI http://127.0.0.1:{port}",flush=True)
        print("Press Ctrl+C to stop the native processes.",flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__=="__main__":
    main()
