import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, suppress
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from context import ROOT, SIM, APM
from evaluate_wave import compare


def http(base, route, body=None):
    request = Request(base+route,data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type":"application/json"})
    with urlopen(request,timeout=5) as response:
        return json.load(response)


def wait_for(check, label, timeout=75):
    deadline = time.monotonic()+timeout
    last = None
    while time.monotonic()<deadline:
        try:
            if result:=check():
                return result
        except OSError as error:
            last = error
        time.sleep(.3)
    raise RuntimeError(f"Timed out waiting for {label}: {last}")


def start(stack, name, command, env):
    log_root = Path(env.get("SRP_TEST_STATE",ROOT/"state/acceptance"))
    logfile = stack.enter_context((log_root/f"{name}.log").open("w",encoding="utf8"))
    child = subprocess.Popen(command,cwd=ROOT,env=env,stdout=logfile,stderr=subprocess.STDOUT)
    def stop():
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    stack.callback(stop)
    return child


def local(stack, model_path=None, sim=8001, apm=8002, sim_ui=3001, apm_ui=3002,
          mqtt_port=18883, frontends=True, scope="acceptance",probability_model=None):
    state = ROOT/"state"/scope
    state.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ,MQTT_PORT=str(mqtt_port),MQTT_HOST="127.0.0.1",CARD_POINTS="200",
               APM_ASSETS=str(ROOT/"docker/assets.json"),
               PYTHONUNBUFFERED="1",SIM_DATA=str(state/"sim"),SRP_TEST_STATE=str(state),
               APM_DATA=str(state/"apm"),SRP_MODEL_PATH=str(model_path or ""),SRP_ALLOW_EXPERIMENTAL_MODEL="1" if model_path else "0",
               VITE_API_URL="",SRP_PROBABILITY_MODEL_PATH=str(probability_model or ""))
    py_path = env.get("PYTHONPATH","")
    broker_command = [shutil.which("node"),"scripts/test_broker.mjs"]
    broker = start(stack,"broker",broker_command,env)
    for name,app,port in (("sim",SIM,sim),("apm",APM,apm)):
        app_env = dict(env,API_PORT=str(port),PYTHONPATH=os.pathsep.join((str(ROOT),str(app),py_path)))
        start(stack,name,[sys.executable,str(app/"backend/server.py")],app_env)
    if frontends:
        for name,app,port,api_port in (("sim-ui",SIM,sim_ui,sim),("apm-ui",APM,apm_ui,apm)):
            start(stack,name,[shutil.which("node"),"node_modules/vite/bin/vite.js",
                str(app/"frontend"),"--host","127.0.0.1","--port",str(port),"--strictPort"],
                dict(env,VITE_API_URL=f"http://127.0.0.1:{api_port}"))
    return broker,broker_command,env


def browser_evidence(sim_ui,apm_ui,asset):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as playwright:
        options = {"headless":True}
        if edge:=os.getenv("PLAYWRIGHT_BROWSER_PATH"):
            options["executable_path"]=edge
        browser=playwright.chromium.launch(**options)
        p=browser.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        p.on("pageerror",lambda error:errors.append(str(error)))
        p.goto(sim_ui,wait_until="domcontentloaded")
        expect(p.get_by_role("heading",name="Live Pumping Unit",exact=True)).to_be_visible()
        p.get_by_role("combobox",name="Well",exact=True).select_option(asset,timeout=15000)
        expect(p.get_by_text("MQTT connected",exact=True)).to_be_visible(timeout=15000)
        expect(p.get_by_role("img",name="Calculated pumpjack linkage and plunger")).to_be_visible()
        expect(p.locator("svg").get_by_text("FOUR-BAR LINKAGE")).to_be_visible(timeout=15000)
        p.get_by_role("button",name="Pause",exact=True).click()
        expect(p.get_by_text("paused",exact=True)).to_be_visible(timeout=10000)
        p.get_by_role("button",name="Start",exact=True).click()
        expect(p.get_by_text("running",exact=True)).to_be_visible(timeout=10000)
        p.screenshot(path=ROOT/"data/evaluation/simulator.png")
        p.get_by_role("button",name="Virtual Sensors").click()
        expect(p.get_by_role("img",name="Motor current",exact=True)).to_be_visible()
        p.get_by_role("button",name="Fault Laboratory").click()
        expect(p.get_by_text("Scenario active",exact=True)).to_be_visible()
        p.goto(apm_ui,wait_until="domcontentloaded")
        expect(p.get_by_role("heading",name="Dual-Card Comparison",exact=True)).to_be_visible()
        p.get_by_role("combobox",name="Well",exact=True).select_option(asset,timeout=15000)
        for label in ("Surface Dynacard","Downhole Dynacard"):
            expect(p.get_by_role("img",name=label,exact=True)).to_be_visible(timeout=20000)
        expect(p.get_by_role("heading",name="Fault diagnosis")).to_be_visible()
        expect(p.get_by_text("Dynacard change detected",exact=False)).to_be_visible(timeout=15000)
        expect(p.get_by_role("link",name="Surface CSV")).to_be_visible()
        assert p.get_by_role("link",name="Surface CSV").evaluate("(a) => fetch(a.href).then(r => r.ok)")
        p.screenshot(path=ROOT/"data/evaluation/apm.png")
        p.get_by_role("button",name="Live Surface Dynacard").click()
        expect(p.get_by_text("Solid line shows the live stroke",exact=False)).to_be_visible()
        p.get_by_role("button",name="ML Model Registry").click()
        expect(p.get_by_text("model_version",exact=False)).to_be_visible()
        assert not errors,errors
        browser.close()
    return "PASS"


def run(args, stack, report):
    sim,apm=args.sim,args.apm
    ports = [urlparse(url).port for url in (sim,apm,args.sim_ui,args.apm_ui)]
    broker_info=local(stack,args.model,*ports,scope=f"acceptance/{uuid.uuid4().hex[:10]}") if args.local else None
    if args.start_compose:
        subprocess.run(["docker","compose","up","--build","-d"],cwd=ROOT,check=True)
    for base in (sim,apm):
        wait_for(lambda:http(base,"/health").get("connected"),f"MQTT connectivity at {base}")
    for front in (args.sim_ui,args.apm_ui):
        wait_for(lambda:urlopen(front,timeout=4).status==200,f"frontend {front}")
    asset="CHECK_"+uuid.uuid4().hex[:7].upper()
    well=http(sim,"/assets")[0] | {"asset_id":asset}
    http(sim,"/assets",well)
    http(apm,"/assets",well)
    run_id=http(sim,f"/assets/{asset}/start",{"speed":4})["run_id"]

    def stop_simulation():
        with suppress(OSError):
            http(sim,f"/assets/{asset}/stop",{})

    stack.callback(stop_simulation)
    url="/cards?"+urlencode({"asset":asset,"run":run_id})

    def cards():
        return [c for c in http(apm,url) if c["downhole"]["status"]=="SOLVED"]

    healthy=wait_for(lambda:(available if len(available:=cards())>=3 else None),"three completed inverse cards")
    card=healthy[0]
    http(sim,f"/assets/{asset}/fault",dict(kind="traveling_valve_leak",severity=.88,onset_s=0,duration_s=1000,ramp_s=0))
    altered=wait_for(lambda:next((c for c in cards() if c["stroke_id"]>=card["stroke_id"]+3),None),
                     "completed fault stroke")
    if args.local:
        path=Path(broker_info[2]["SIM_DATA"])/f"{run_id}.jsonl"
        text=path.read_text()
    else:
        command=["docker","compose","exec","-T","simulator","cat",f"/state/{run_id}.jsonl"]
        text=subprocess.check_output(command,cwd=ROOT,text=True)
    truth=[]
    for line in text.splitlines():
        try:
            truth.append(json.loads(line))
        except ValueError:
            continue
    validation=[]
    for chosen in (card,altered):
        first,last=chosen["raw_sequence"]
        matched=[p for p in truth if first<=p["sequence"]<=last]
        validation.append(compare(chosen,[dict(time=p["timestamp_unix_s"],x=p["pump_position_m"],
                                              f=p["pump_load_n"]) for p in matched]))
    assert any(p["severity"]>0 for p in truth if p["stroke_id"]==altered["stroke_id"])
    relative_delta=abs(card["surface"]["area_j"]-altered["surface"]["area_j"])/card["surface"]["area_j"]
    baseline_area_spread=max(c["surface"]["area_j"] for c in healthy)-min(c["surface"]["area_j"] for c in healthy)
    area_delta=abs(card["surface"]["area_j"]-altered["surface"]["area_j"])
    assert area_delta>max(5.,3*baseline_area_spread),(area_delta,baseline_area_spread)
    snapshot=http(apm,"/snapshot?"+urlencode({"asset":asset}))
    paths=ROOT/"data/evaluation"
    capture=paths/"mqtt_capture.jsonl"
    received=snapshot["live"]
    if len(received)<3:
        time.sleep(.25)
        received=http(apm,"/snapshot?"+urlencode({"asset":asset}))["live"]
    capture.write_text("\n".join(json.dumps(s) for s in received)+"\n")
    if args.local and received:
        from paho.mqtt.publish import single
        duplicate_before=http(apm,"/health")["counts"].get("duplicates",0)
        single(f"srp/v1/{asset}/telemetry/dynamometer",json.dumps(received[0]),qos=1,
               hostname="127.0.0.1",port=int(broker_info[2]["MQTT_PORT"]))
        wait_for(lambda:http(apm,"/health")["counts"].get("duplicates",0)>duplicate_before,
                 "deduplication of an MQTT redelivery")
        report["duplicate_delivery"]="PASS"
    (paths/"acceptance_cards.json").write_text(json.dumps(dict(healthy=card,altered=altered)))
    (paths/"acceptance_truth.jsonl").write_text("\n".join(json.dumps(p) for p in truth)+"\n")
    report.update(asset=asset,run_id=run_id,broker="Aedes" if args.local else "Mosquitto",
                  healthy_solved=len(healthy),fault_stroke=altered["stroke_id"],relative_surface_area_change=relative_delta,
                  surface_area_change_j=area_delta,baseline_area_spread_j=baseline_area_spread,
                  inverse_validation=validation,classification=altered["diagnosis"],
                  publisher=http(sim,"/health"),subscriber=http(apm,"/health"),
                  captured_samples=len(received),origin="SIMULATED",
                  ml_acceptance="INCOMPLETE" if altered["diagnosis"]["status"]!="VALIDATED_ON_HELD_OUT_SIMULATION" else "PASS")
    if not args.skip_browser:
        report["browser"]=browser_evidence(args.sim_ui,args.apm_ui,asset)
    else:
        report["browser"]="HTTP only"
    if broker_info and not args.skip_outage:
        broker,command,env=broker_info
        latest_before_outage=cards()[0]["stroke_id"]
        accepted_before_outage=http(apm,"/health")["counts"]
        broker.terminate()
        broker.wait(timeout=10)
        wait_for(lambda:not http(apm,"/health")["connected"],"subscriber disconnect")
        time.sleep(1)
        status_before=wait_for(lambda:(status if (status:=http(sim,"/health"))["queued"] else None),
                               "durable queued messages")
        queued_before=status_before["queued"]
        start(stack,"broker-restart",command,env)
        wait_for(lambda:http(apm,"/health")["connected"],"subscriber reconnect")
        wait_for(lambda:http(sim,"/health")["connected"],"publisher reconnect")
        wait_for(lambda:http(sim,"/health")["sent"]-status_before["sent"]>=queued_before,"outbox replay")
        recovered=wait_for(lambda:next((c for c in cards() if c["stroke_id"]>latest_before_outage+1),None),
                           "post-reconnect solved card")
        after_outage=http(apm,"/health")
        report["outage"]=dict(queued_before_restart=queued_before,recovered_stroke=recovered["stroke_id"],
                              latest_stroke_before_outage=latest_before_outage,
                              newly_observed_gaps=after_outage["counts"].get("observed_gaps",0)-
                                                  accepted_before_outage.get("observed_gaps",0),
                              subscriber=after_outage,publisher=http(sim,"/health"))
    report["pipeline"]="PASS"


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--local",action="store_true",help="Run native processes with an Aedes MQTT broker")
    cli.add_argument("--start-compose",action="store_true")
    cli.add_argument("--skip-browser",action="store_true")
    cli.add_argument("--skip-outage",action="store_true")
    cli.add_argument("--model",type=Path)
    for key,port in [("sim",8001),("apm",8002),("sim-ui",3001),("apm-ui",3002)]:
        cli.add_argument("--"+key,default=f"http://127.0.0.1:{port}")
    args=cli.parse_args()
    (ROOT/"state/acceptance").mkdir(parents=True,exist_ok=True)
    report={}
    try:
        with ExitStack() as stack:
            run(args,stack,report)
    except Exception as error:
        report.update(pipeline="FAILED",error=str(error))
        raise
    finally:
        (ROOT/"data/evaluation/acceptance.json").write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
