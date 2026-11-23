import json
import math
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from zipfile import ZipFile

from configurations.presets import presets
from fault_injection.scenarios import Fault
from mqtt_publisher.outbox import Outbox
from physics.engine import Engine
from shared.contracts import Well, topic
from shared.contracts import INCH, LBF
from shared.telemetry_privacy import assert_label_blind
from shared.http_api import serve
from virtual_sensors.sampling import Sensors


class Run:
    def __init__(self, well, speed, root, site_id=None):
        self.lock = threading.RLock()
        self.engine = Engine(well)
        self.reference_ready_phase=(math.floor((self.engine.phase+1e-7)/math.tau)+4)*math.tau
        self.id = uuid.uuid4().hex
        self.site_id = site_id
        self.sensors = Sensors(self.engine,self.id)
        self.sensors.site_id = site_id
        self.mode = "running"
        self.speed = speed
        self.state = self.engine.state()
        self.history = deque(maxlen=300)
        self.electrical_due = self.pressure_due = self.engine.time
        self.truth = root / f"{self.id}.jsonl"
        self.message_sequence = 0

    def sample(self, outbox, truth_file):
        e, w = self.engine, self.engine.well
        self.state = e.advance(1/w.dynamometer_hz)
        sample, new_stroke = self.sensors.read(self.state)
        messages = []
        timestamp = (self.sensors.epoch.timestamp()+e.time-self.sensors.start_time)
        identity = dict(schema_version="1.0",asset_id=w.asset_id,run_id=self.id,
                        source="SIMULATOR",timestamp_unix_s=timestamp,site_id=self.site_id,quality="GOOD")
        if sample is not None:
            payload = sample.model_dump(mode="json")
            messages.append((topic(w.asset_id,"telemetry/dynamometer"),payload,False))
        if new_stroke:
            messages.append((topic(w.asset_id,"events/stroke"),dict(identity,stroke_id=self.sensors.stroke_id),False))
        for name, due, rate, keys in [
            ("electrical","electrical_due",w.electrical_hz,
                ("motor_rpm","voltage_v","current_a","power_w","gearbox_torque_nm")),
            ("pressure","pressure_due",w.pressure_hz,
                ("tubing_pa","casing_pa","intake_pa","net_delivered_m3"))
        ]:
            if e.time+1e-8 >= getattr(self,due):
                messages.append((topic(w.asset_id,f"telemetry/{name}"),
                                 dict(identity,**{k:self.state[k] for k in keys},
                                      units=({"motor_rpm":"rpm","voltage_v":"V","current_a":"A",
                                              "power_w":"W","gearbox_torque_nm":"N m"} if name=="electrical" else
                                             {"tubing_pa":"Pa","casing_pa":"Pa","intake_pa":"Pa",
                                              "net_delivered_m3":"m3"})),False))
                setattr(self,due,getattr(self,due)+1/rate)
        truth = dict(identity, **{k:v for k,v in self.state.items() if k != "linkage"},
                     sequence=self.sensors.sequence-1,stroke_id=self.sensors.stroke_id,
                     sample_index=self.sensors.index-1,origin="SIMULATED",
                     fault=e.fault.kind,severity=e.fault.at(e.time,e.fault.kind))
        truth_file.write(json.dumps(truth)+"\n")
        if new_stroke:
            truth_file.flush()
        # Ground truth remains local to the Twin. Never publish fault labels,
        # severity or scenario identity into the MQTT inference channel.
        if self.sensors.sequence % max(1,w.dynamometer_hz//10)==0:
            self.history.append(self.state)
        for _, payload, _ in messages:
            assert_label_blind(payload)
            if "sequence" not in payload:
                payload["sequence"] = self.message_sequence
                self.message_sequence += 1
        outbox.append(messages,w.sensor_latency_s)


def main():
    root = Path(os.getenv("SIM_DATA","state/simulator"))
    root.mkdir(parents=True,exist_ok=True)
    catalog_path = root/"assets.json"
    wells = {w.asset_id:w for w in presets()}
    fleet_dir = Path(__file__).resolve().parents[3]/"config/fleet"
    default_fleet = fleet_dir/"dataset_120_calibrated.json"
    if not default_fleet.exists():
        default_fleet = fleet_dir/"us_srp_30_wells.json"
    fleet_path = Path(os.getenv("SIM_FLEET_PATH",str(default_fleet)))
    site_by_asset = {}
    initial_faults = {}
    calibration_by_asset = {}
    if fleet_path.exists():
        fleet = json.loads(fleet_path.read_text())
        if 'dataset_120' in fleet_path.name:
            wells = {}
        site_filter = os.getenv("SIM_SITE_ID")
        for entry in fleet["wells"]:
            if site_filter and entry["site_id"] != site_filter:
                continue
            well = Well.model_validate(entry["well"])
            wells[well.asset_id] = well
            site_by_asset[well.asset_id] = entry["site_id"]
            if entry.get('initial_fault'):
                initial_faults[well.asset_id] = entry['initial_fault']
            calibration_by_asset[well.asset_id] = entry.get('calibration_result')
    if catalog_path.exists():
        for item in json.loads(catalog_path.read_text()):
            well=Well.model_validate(item)
            if well.asset_id not in site_by_asset:
                wells[well.asset_id]=well
    outbox = Outbox(root/"outbox.db")
    lock = threading.RLock()
    runs = {}

    def publish_status(asset, run):
        with run.lock:
            payload = dict(schema_version="1.0", asset_id=asset, site_id=site_by_asset.get(asset),
                           run_id=run.id, source="SIMULATOR", timestamp_unix_s=time.time(),
                           sequence=run.message_sequence, quality="GOOD", units={}, mode=run.mode)
            run.message_sequence += 1
        outbox.append([(topic(asset,"status"),payload,True)])

    def reference_cards():
        """Read only counted ASCII demo traces; never infer a fault label."""
        cards=[]
        for archive_path in sorted((Path(__file__).resolve().parents[3]/"state/vendor").glob("echometer-session*.zip")):
            with ZipFile(archive_path) as archive:
                for member in archive.namelist():
                    if not member.lower().endswith(".dyn"):
                        continue
                    lines=archive.read(member).decode("ascii").splitlines()
                    count=int(lines[0].strip())
                    if not 2<=count<=15000 or len(lines)<count+1:
                        continue
                    points=[]
                    for line in lines[1:count+1]:
                        x,f=map(float,line.split(","))
                        if not (math.isfinite(x) and math.isfinite(f)):
                            raise ValueError("Nonfinite vendor card point")
                        points.append((x*INCH,f*LBF))
                    cards.append(dict(id=f"{archive_path.stem}:{member}",source=archive_path.name,
                                      name=Path(member).name,kind="surface",label=None,
                                      provenance="Echometer demonstration archive",points=len(points),
                                      position_m=[p[0] for p in points],load_n=[p[1] for p in points]))
        return cards

    def worker(run):
        next_sample = time.monotonic()
        with run.truth.open("a",encoding="utf8",buffering=262144) as output:
            while run.mode != "stopped":
                if run.mode == "paused":
                    time.sleep(.05)
                    next_sample = time.monotonic()
                    continue
                with run.lock:
                    if run.mode == "running":
                        run.sample(outbox,output)
                next_sample += 1/(run.speed*run.engine.well.dynamometer_hz)
                time.sleep(max(0,next_sample-time.monotonic()))

    def dispatch(method, route, query, body):
        if route==["health"]:
            return dict(ready=True,**outbox.status())
        if method=="GET" and route==["reference-cards"]:
            return reference_cards()
        if method=="GET" and route==["fleet"]:
            with lock:
                return dict(wells=[dict(asset_id=asset,site_id=site_by_asset.get(asset),
                                        mode=runs[asset].mode if asset in runs else "idle",
                                        run_id=runs[asset].id if asset in runs else None,
                                        latest_sequence=runs[asset].sensors.sequence-1 if asset in runs else None,
                                        ground_truth=(dict(kind=runs[asset].engine.fault.kind,
                                            active_severity=runs[asset].engine.fault.at(runs[asset].engine.time,runs[asset].engine.fault.kind)) if asset in runs else None),
                                        calibration=calibration_by_asset.get(asset))
                                   for asset in wells],
                            site_ids=sorted(set(site_by_asset.values())))
        if method=="POST" and len(route) in (2, 3) and route[0] in ("fleet", "sites"):
            action = route[-1]
            if action not in ("start", "pause", "resume", "stop", "speed"):
                raise KeyError()
            if route[0] == "sites":
                if len(route) != 3:
                    raise KeyError()
                targets = [asset for asset, site in site_by_asset.items() if site == route[1]]
                if not targets:
                    raise KeyError()
            elif route == ["fleet", action]:
                targets = list(site_by_asset)
            else:
                raise KeyError()
            speed = float(body.get("speed", 1.))
            if not .1 <= speed <= 20:
                raise ValueError("simulation speed must be between 0.1 and 20")
            pending_workers = []
            with lock:
                for asset in targets:
                    run = runs.get(asset)
                    if action in ("start", "resume"):
                        if run and run.mode == "paused":
                            run.mode = "running"
                        elif not run or run.mode == "stopped":
                            replacement = Run(wells[asset], speed, root, site_by_asset.get(asset))
                            if asset in initial_faults:
                                replacement.engine.fault = Fault.model_validate(dict(initial_faults[asset],onset_s=replacement.engine.time))
                            runs[asset] = replacement
                            pending_workers.append(replacement)
                    elif run:
                        if action=='speed':run.speed=speed
                        else:run.mode = "paused" if action == "pause" else "stopped"
                    if asset in runs:
                        publish_status(asset, runs[asset])
                for pending in pending_workers:
                    threading.Thread(target=worker, args=(pending,), daemon=True).start()
            return dict(action=action, target_count=len(targets),
                        running=sum(runs[a].mode == "running" for a in targets if a in runs))
        if method=="POST" and route==["assets"]:
            well = Well.model_validate(body)
            from physics.engine import Mechanism
            Mechanism(well)
            with lock:
                wells[well.asset_id] = well
                temp = catalog_path.with_suffix(".tmp")
                temp.write_text(json.dumps([w.model_dump() for w in wells.values()]))
                temp.replace(catalog_path)
            return well.model_dump()
        if route==["assets"]:
            with lock:
                return [w.model_dump() for w in wells.values()]
        if route==["snapshot"]:
            with lock:
                asset = query.get("asset","SRP_001")
                run = runs.get(asset)
                configuration=wells[asset].model_dump()
            result=dict(asset_id=asset,configuration=configuration,mqtt=outbox.status(),
                        mode="idle",run_id=None,state=None,history=[],fault=None,
                        calibration=calibration_by_asset.get(asset))
            if run:
                with run.lock:
                    result.update(mode=run.mode,run_id=run.id,state=run.state,
                                  history=list(run.history),fault=run.engine.fault.model_dump())
            return result
        if method!="POST" or len(route)!=3 or route[0]!="assets":
            raise KeyError()
        _, asset, action = route
        with lock:
            well = wells[asset]
            run = runs.get(asset)
            if action in ("start","reset"):
                if action=="start" and run and run.mode in ("running","paused"):
                    run.mode = "running"
                else:
                    speed = float(body.get("speed",1.))
                    if not .1<=speed<=20:
                        raise ValueError("simulation speed must be between 0.1 and 20")
                    replacement = Run(well,speed,root,site_by_asset.get(asset))
                    if asset in initial_faults:
                        replacement.engine.fault = Fault.model_validate(dict(initial_faults[asset],onset_s=replacement.engine.time))
                    if body.get("paused") is True:
                        replacement.mode = "paused"
                    if run:
                        run.mode = "stopped"
                    run = runs[asset] = replacement
                    threading.Thread(target=worker,args=(run,),daemon=True).start()
            elif not run:
                raise KeyError()
            elif action in ("pause","stop"):
                with run.lock:
                    run.mode = {"pause":"paused","stop":"stopped"}[action]
            elif action=="fault":
                fault = Fault.model_validate(body)
                with run.lock:
                    delay_for_reference=0.
                    if fault.kind!="healthy" and body.get("wait_for_reference") is True:
                        delay_for_reference=max(0.,(run.reference_ready_phase-run.engine.phase)*60/
                                                (math.tau*run.engine.well.spm))
                    requested_delay=fault.onset_s
                    fault.onset_s=run.engine.time+max(requested_delay,delay_for_reference)
                    run.engine.fault = fault
                return dict(run_id=run.id,mode=run.mode,waiting_for_reference=delay_for_reference>requested_delay)
            else:
                raise KeyError()
            publish_status(asset,run)
            return dict(run_id=run.id, mode=run.mode)
    # All wells default to running (ON) immediately upon startup
    if os.getenv("SIM_AUTO_START", "1") != "0":
        dispatch("POST", ["fleet", "start"], {}, {"speed": 1.})
    serve(int(os.getenv("API_PORT",8001)),dispatch)


if __name__=="__main__":
    main()
