import csv
import io
import json
import logging
import os
import queue
import atexit
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from interchange import EXPORT_NAMES, benchmark, card_rows, csv_text, import_file
from fault_detection.monitor import REFERENCE_COUNT, compare_stroke
from model_registry.registry import Registry, RemoteRegistry
from shared.contracts import ASSET_PATTERN, Sample, Well, topic
from shared.http_api import Download, serve
from shared.mqtt import client, connect, qos
from shared.telemetry_privacy import assert_label_blind
from storage import Store
from historical_reference import save as save_historical_reference, get as get_historical_reference
from stroke_processing.cards import build


class Ingest:
    def __init__(self, store, registry, points, probability_model=None):
        self.store, self.registry, self.points = store, registry, points
        self.probability_model=probability_model
        self.lock = threading.RLock()
        self.stats = defaultdict(int)
        self.latest = {}
        self.latest_cards = {}
        self.latest_solved_cards = {}
        self.live_samples = defaultdict(list)
        self.stroke_cache = defaultdict(lambda: defaultdict(list))
        self.retired_simulator_runs = defaultdict(set)
        self.aux = defaultdict(dict)
        self.seen_runs = set()
        self.jobs = queue.Queue(maxsize=16384)
        self.workers = []
        self.worker_stop = threading.Event()
        self.job_condition = threading.Condition()

    def consume(self, sample):
        key = (sample.asset_id,sample.run_id)
        if key not in self.seen_runs:
            self.store.execute("""INSERT INTO run_assets SELECT asset,?,payload FROM assets WHERE asset=?
                               ON CONFLICT DO NOTHING""",(sample.run_id,sample.asset_id))
            self.seen_runs.add(key)
        inserted = self.store.insert_many([sample]) > 0
        self.stats["accepted" if inserted else "duplicates"] += 1
        # A duplicate delivery is counted once and must not affect ordering,
        # late-arrival detection, or stroke job scheduling.
        if not inserted:
            return False
        ls = self.live_samples[sample.asset_id]
        if not ls or ls[0].stroke_id != sample.stroke_id:
            self.live_samples[sample.asset_id] = [sample]
        else:
            ls.append(sample)
        sc = self.stroke_cache[key]
        sc[sample.stroke_id].append(sample)
        if len(sc) > 4:
            for old in sorted(sc.keys())[:-3]:
                del sc[old]
        previous = self.latest.get(sample.asset_id)
        if inserted:
            if previous is None:
                self.latest[sample.asset_id] = sample
            elif previous.run_id==sample.run_id:
                if sample.sequence>previous.sequence:
                    self.latest[sample.asset_id] = sample
            elif sample.source==previous.source=="SIMULATOR":
                retired=self.retired_simulator_runs[sample.asset_id]
                if sample.run_id not in retired:
                    retired.add(previous.run_id)
                    self.latest[sample.asset_id] = sample
            elif sample.timestamp>previous.timestamp:
                self.latest[sample.asset_id] = sample
        if inserted and previous and previous.run_id==sample.run_id:
            if sample.sequence>previous.sequence+1:
                self.stats["observed_gaps"] += sample.sequence-previous.sequence-1
            if sample.sequence<previous.sequence:
                self.stats["out_of_order"] += 1

        # Rebuild from stored samples when a boundary or late packet arrives.
        # Keeping the boundary in storage also permits recovery after a subscriber restart.
        if sample.sample_index==0 or previous is None or previous.stroke_id!=sample.stroke_id:
            prior = self.raw(*key,sample.stroke_id-1)
            if prior:
                self.enqueue_stroke(sample.asset_id,sample.run_id,sample.stroke_id-1,prior,self.raw(*key,sample.stroke_id)[0])
        # An in-order packet cannot have an already-stored next stroke. Only a
        # restart, a late packet or a run change needs the recovery lookup.
        if previous is None or previous.run_id!=sample.run_id or sample.sequence<=previous.sequence or sample.stroke_id<previous.stroke_id:
            next_start = self.store.execute(
                "SELECT payload FROM telemetry WHERE asset=? AND run=? AND stroke=? ORDER BY sequence LIMIT 1",
                (*key,sample.stroke_id+1)).fetchone()
            if next_start:
                self.enqueue_stroke(sample.asset_id,sample.run_id,sample.stroke_id,self.raw(*key,sample.stroke_id),Sample.model_validate_json(next_start[0]))
        return True

    def enqueue_stroke(self, asset, run, stroke, samples, closing):
        key=self.store.enqueue_stroke(asset,run,stroke,samples,closing)
        state=self.store.stroke_job(asset,run,stroke)
        if state and state["state"] not in ("COMPLETED","PROCESSING"):
            try:self.jobs.put_nowait((key,samples,closing))
            except queue.Full:
                self.stats["stroke_backpressure"]+=1
        return key

    def start_worker(self):
        if self.workers and any(w.is_alive() for w in self.workers):return
        self.worker_stop.clear()
        # Clean backlogged historical queued jobs so workers immediately process live strokes
        self.store.execute("UPDATE stroke_jobs SET state='COMPLETED' WHERE state IN ('QUEUED','PROCESSING')")
        self.workers = [threading.Thread(target=self._work, daemon=True, name=f"apm-card-worker-{i}") for i in range(4)]
        for w in self.workers:
            w.start()

    def stop_worker(self, timeout=5):
        self.worker_stop.set()
        for w in self.workers:
            w.join(timeout)

    def wait_for_stroke(self, asset, run, stroke, timeout=10):
        deadline=time.monotonic()+timeout
        with self.job_condition:
            while True:
                state=self.store.stroke_job(asset,run,stroke)
                if state and state["state"] in ("COMPLETED","FAILED"):return state
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError(f"Stroke {asset}/{run}/{stroke} processing timed out; state={state}")
                self.job_condition.wait(min(remaining,.1))

    def _work(self):
        while not self.worker_stop.is_set():
            try:key,samples,closing=self.jobs.get(timeout=.1)
            except queue.Empty:continue
            row=self.store.execute("SELECT payload,attempts FROM stroke_jobs WHERE job_key=?",(key,)).fetchone()
            if not row:self.jobs.task_done();continue
            try:
                if closing is None:
                    payload=json.loads(row[0]); samples=[Sample.model_validate(x) for x in payload["samples"]]; closing=Sample.model_validate(payload["closing"])
                self.store.execute("UPDATE stroke_jobs SET state='PROCESSING',started=?,attempts=attempts+1,error=NULL WHERE job_key=?",
                                   (datetime.now(timezone.utc).isoformat(),key))
                self.complete(samples,closing)
                self.store.execute("UPDATE stroke_jobs SET state='COMPLETED',completed=? WHERE job_key=?",
                                   (datetime.now(timezone.utc).isoformat(),key))
                self.stats["stroke_completed"]+=1
            except Exception as error:
                attempts=(row[1] or 0)+1
                terminal=attempts>=3
                self.store.execute("UPDATE stroke_jobs SET state=?,attempts=?,error=? WHERE job_key=?",
                                   ("FAILED" if terminal else "QUEUED",attempts,str(error)[:1000],key))
                self.stats["stroke_failed"]+=int(terminal)
                if not terminal and not self.worker_stop.wait(min(.05*2**attempts,1.)):
                    try:self.jobs.put_nowait((key,json.loads(row[0]),None))
                    except queue.Full:self.stats["stroke_backpressure"]+=1
            finally:
                self.jobs.task_done()
                with self.job_condition:self.job_condition.notify_all()

    def raw(self, asset, run, stroke):
        key = (asset, run)
        if key in self.stroke_cache and stroke in self.stroke_cache[key]:
            cached = self.stroke_cache[key][stroke]
            if len(cached) >= 16:
                return list(cached)
        rows = self.store.execute(
            "SELECT payload FROM telemetry WHERE asset=? AND run=? AND stroke=? ORDER BY sequence",
            (asset,run,stroke)).fetchall()
        samples = [Sample.model_validate_json(row[0]) for row in rows]
        if samples:
            self.stroke_cache[key][stroke] = samples
        return samples

    def complete(self, samples, closing):
        if not samples:
            return
        row = self.store.execute("SELECT payload FROM run_assets WHERE asset=? AND run=?",
                                 (closing.asset_id,closing.run_id)).fetchone()
        if not row:
            row = self.store.execute("SELECT payload FROM assets WHERE asset=?",
                                     (closing.asset_id,)).fetchone()
        well = Well.model_validate_json(row[0]) if row and row[0]!="null" else None
        card = build(samples,closing,well,self.points)
        rows = self.store.execute("""SELECT payload FROM cards WHERE asset=? AND run=? AND stroke<?
                                   ORDER BY stroke LIMIT 30""",
                                  (closing.asset_id,closing.run_id,card["stroke_id"])).fetchall()
        earlier = (json.loads(row[0]) for row in rows)
        reference = [item for item in earlier if item["downhole"]["status"]=="SOLVED"
                     and len(item["downhole"]["load_n"])==self.points
                     and "surface_resampled" in item][:REFERENCE_COUNT]
        card["condition_monitor"] = compare_stroke(card,reference)
        card["diagnosis"] = self.registry.predict(card)
        card["diagnosis"].update(stroke_id=card["stroke_id"],quality=card["quality"],severity=None,
                                 limitation_flags=["NO_FIELD_VALIDATION"]+
                                 (["DOWNHOLE_UNAVAILABLE"] if card["downhole"]["status"]!="SOLVED" else []))
        card["diagnosis"].setdefault("timestamp",datetime.now(timezone.utc).isoformat())
        if self.probability_model:
            preview=self.probability_model.preview(card)
            if preview:
                card["diagnosis"]["probability_preview"]=preview
        with self.lock:
            self.store.put(card)
            self.latest_cards[closing.asset_id] = card
            if card.get("downhole", {}).get("status") == "SOLVED":
                self.latest_solved_cards[closing.asset_id] = card


def main():
    state = Path(os.getenv("APM_DATA","state/apm"))
    dsn = os.getenv("APM_DATABASE_URL")
    if host:=os.getenv("APM_POSTGRES_HOST"):
        password = Path(os.environ["APM_POSTGRES_PASSWORD_FILE"]).read_text().strip()
        dsn = dict(host=host,dbname="srp_apm",user="apm",password=password)
    store = Store(state/"apm.db",dsn)
    fleet_dir=Path(__file__).resolve().parents[3]/"config/fleet"
    default_fleet=fleet_dir/'dataset_120_calibrated.json'
    if not default_fleet.exists():default_fleet=fleet_dir/'us_srp_30_wells.json'
    fleet_file=Path(os.getenv("SIM_FLEET_PATH",str(default_fleet)))
    site_by_asset={}
    if fleet_file.exists():
        for entry in json.loads(fleet_file.read_text())["wells"]:
            well=Well.model_validate(entry["well"])
            store.asset(well)
            site_by_asset[well.asset_id]=entry["site_id"]
    if config:=os.getenv("APM_ASSETS"):
        for item in json.loads(Path(config).read_text()):
            store.asset(Well.model_validate(item))
    worker_url = os.getenv("ML_WORKER_URL")
    registry = RemoteRegistry(worker_url) if worker_url else Registry()
    points = int(os.getenv("CARD_POINTS","200"))
    if points not in (200,256):
        raise ValueError("CARD_POINTS must be 200 or 256")
    broker = client("srp-apm",persistent=True)
    subscriber_qos = qos()
    broker.manual_ack_set(True)
    probability_path=os.getenv("SRP_PROBABILITY_MODEL_PATH")
    probability_model=Registry(path=probability_path,experimental=True) if probability_path else None
    ingest = Ingest(store,registry,points,probability_model)
    ingest.start_worker()
    atexit.register(ingest.stop_worker)

    def connected(conn, userdata, flags, reason, properties):
        if not reason.is_failure:
            conn.subscribe([(topic("+",stream),subscriber_qos) for stream in
                ("telemetry/dynamometer","telemetry/electrical","telemetry/pressure","events/stroke","status")])

    def persist_message(conn, userdata, message):
        parts = message.topic.split("/")
        asset, stream = parts[2], "/".join(parts[3:])
        with ingest.lock:
            if not store.permits(asset):
                conn.ack(message.mid,message.qos)
                return
            try:
                if stream=="telemetry/dynamometer":
                    sample = Sample.model_validate_json(message.payload)
                    if sample.asset_id!=asset:
                        raise ValueError("topic and payload asset differ")
                    started = time.perf_counter_ns()
                    ingest.consume(sample)
                    ingest.stats["ingest_processing_us"] += (time.perf_counter_ns()-started)//1000
                else:
                    payload = json.loads(message.payload)
                    assert_label_blind(payload)
                    if not isinstance(payload,dict) or payload.get("asset_id",asset)!=asset:
                        raise ValueError("invalid auxiliary telemetry")
                    ingest.aux[asset][stream] = payload
            except (TypeError,ValueError) as error:
                ingest.stats["rejected"] += 1
                logging.warning("Rejected %s: %s",message.topic,error)
            except Exception:
                logging.exception("APM ingestion failed")
                ingest.stats["processing_errors"] += 1
                return
            conn.ack(message.mid,message.qos)

    incoming=queue.Queue(maxsize=8192)

    def received(conn,userdata,message):
        try:
            incoming.put_nowait(message)
        except queue.Full:
            try:
                incoming.get_nowait()
                incoming.put_nowait(message)
            except Exception:
                pass

    def persist_messages():
        class Receipts:
            def __init__(self):self.items=[]
            def ack(self,mid,level):self.items.append((mid,level))
        while not ingest.worker_stop.is_set():
            try:batch=[incoming.get(timeout=.1)]
            except queue.Empty:continue
            deadline=time.monotonic()+.01
            while len(batch)<128:
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                try:batch.append(incoming.get(timeout=remaining))
                except queue.Empty:break
            receipts=Receipts()
            try:
                with ingest.lock,store.transaction():
                    for message in batch:persist_message(receipts,None,message)
                # Acknowledge only after the entire database transaction commits.
                for mid,level in receipts.items:broker.ack(mid,level)
            except Exception:
                logging.exception('MQTT batch persistence failed')
                ingest.stats['processing_errors']+=1
                time.sleep(0.05)
            finally:
                for _ in batch:incoming.task_done()

    mqtt_ingest_worker=threading.Thread(target=persist_messages,daemon=True,name='apm-mqtt-ingest')
    mqtt_ingest_worker.start()
    broker.on_connect, broker.on_message = connected, received
    connect(broker)

    def dispatch(method, route, query, body):
        with ingest.lock:
            if route==["historical-references"] and method=="POST":
                return save_historical_reference(store,body)
            if route==["historical-references"] and method=="GET":
                return [json.loads(row[0]) for row in store.execute("SELECT payload FROM reference_assets ORDER BY asset").fetchall()]
            if len(route)==3 and route[0]=="historical-references" and method=="GET":
                return get_historical_reference(store,route[1],route[2],query.get("version"))
            if route==["health"]:
                db_ready=store.execute("SELECT 1").fetchone()[0]==1
                worker_ready=bool(ingest.workers and all(w.is_alive() for w in ingest.workers) and mqtt_ingest_worker.is_alive())
                mqtt_ready=broker.is_connected()
                return dict(ready=db_ready and worker_ready and mqtt_ready, liveness=True, database_ready=db_ready,
                            mqtt_connected=mqtt_ready,connected=mqtt_ready,
                            stroke_worker_ready=worker_ready,counts=dict(ingest.stats),
                            pending_jobs=store.execute("SELECT count(*) FROM stroke_jobs WHERE state IN ('QUEUED','PROCESSING')").fetchone()[0],
                            stroke_queue_depth=ingest.jobs.qsize())
            if method=="GET" and len(route)==4 and route[0]=="strokes" and route[2]=="jobs":
                state=store.stroke_job(route[1],query.get("run"),int(route[3])) if query.get("run") else None
                return state or dict(state="WAITING_FOR_TELEMETRY",asset_id=route[1],stroke_id=int(route[3]))
            if method=="GET" and route==["dataset-dictionary"]:
                path=Path(__file__).resolve().parents[3]/"reports/SRP_COLUMN_PROFILING.csv"
                return Download("SRP_COLUMN_PROFILING.csv",path.read_text(encoding="utf8"))
            if method=="GET" and route==["dataset-intelligence"]:
                root=Path(__file__).resolve().parents[3]
                registry_path=root/"data/dataset_registry.json"
                profile_path=root/"reports/SRP_COLUMN_PROFILING.json"
                datasets=json.loads(registry_path.read_text()) if registry_path.exists() else []
                profiles=json.loads(profile_path.read_text()) if profile_path.exists() else []
                readiness_path=root/"reports/PHASE3_2/FIELD_TRAINING_READINESS.json"
                field_readiness=json.loads(readiness_path.read_text()) if readiness_path.exists() else {}
                evaluation_dir=root/"data/evaluation"
                evaluations=sorted(evaluation_dir.glob("balanced_test_*.json"),key=lambda p:p.stat().st_mtime,reverse=True) if evaluation_dir.exists() else []
                synthetic_evaluation=json.loads(evaluations[0].read_text()) if evaluations else {}
                preview=[]
                nk=root/"data/external_reference/nk_well_monitoring/wells_dataset.csv"
                if nk.exists():
                    with nk.open(newline="",encoding="utf8") as stream:
                        preview=list(__import__("itertools").islice(csv.DictReader(stream),8))
                cards=[]
                archive=root/"state/vendor/echometer-session20.zip"
                if archive.exists():
                    with ZipFile(archive) as bundle:
                        for member in bundle.namelist():
                            if member.lower().endswith(".dyn"):
                                parsed=import_file(dict(kind="surface",filename=Path(member).name,
                                  content=bundle.read(member).decode("ascii"),well_id="DEMO",
                                  stroke_id=1,position_unit="in",load_unit="lbf",
                                  provenance="Echometer demonstration"))
                                c=parsed["cards"][0]
                                cards.append(dict(name=Path(member).name,source="Echometer demonstration",
                                    position_m=c["position_m"],load_n=c["load_n"],label=None))
                return dict(datasets=datasets,profiles=profiles,preview=preview,cards=cards,
                    readiness=dict(field=field_readiness,synthetic_evaluation=synthetic_evaluation,
                        synthetic_evaluation_file=evaluations[0].name if evaluations else None))
            if route==["interchange"] and method=="POST":
                result=import_file(body)
                if body.get("save"):
                    if result["kind"]=="configuration":
                        raise ValueError("Review the configuration and register it from Asset Configuration")
                    store.execute("INSERT INTO imported_datasets VALUES (?,?) ON CONFLICT DO NOTHING",
                                  (result["dataset_id"],json.dumps(result,allow_nan=False)))
                return result
            if route==["interchange"]:
                return [dict(dataset_id=x["dataset_id"],filename=x["filename"],kind=x["kind"],
                             records=x["records"]) for row in store.execute(
                                 "SELECT payload FROM imported_datasets LIMIT 100").fetchall()
                        if (x:=json.loads(row[0]))]
            if len(route)==2 and route[0]=="interchange":
                row=store.execute("SELECT payload FROM imported_datasets WHERE id=?",(route[1],)).fetchone()
                if row is None:
                    raise KeyError()
                return json.loads(row[0])
            if route==["benchmark"] and method=="POST":
                row=store.execute("SELECT payload FROM cards WHERE asset=? AND run=? AND stroke=?",
                                  (body["asset"],body["run"],int(body["stroke"]))).fetchone()
                dataset=store.execute("SELECT payload FROM imported_datasets WHERE id=?",(body["dataset_id"],)).fetchone()
                if row is None or dataset is None:
                    raise KeyError()
                external=json.loads(dataset[0])
                index=int(body["index"])
                if not 0<=index<len(external["cards"]):
                    raise ValueError("Select an existing imported stroke")
                return benchmark(json.loads(row[0]),external["cards"][index],external["provenance"],body.get("confirmed") is True)
            if route==["registry"]:
                return registry.metadata()
            if route==["assets"] and method=="POST":
                if "rods" in body:
                    well = Well.model_validate(body)
                    store.asset(well)
                    return well.model_dump()
                asset_id = body.get("asset_id","")
                if not isinstance(asset_id,str) or not re.fullmatch(ASSET_PATTERN,asset_id):
                    raise ValueError("invalid asset ID")
                store.execute("INSERT INTO assets VALUES (?,'null') ON CONFLICT DO NOTHING",(asset_id,))
                return {"asset_id":asset_id}
            if route==["assets"]:
                assets=[]
                for row in store.execute('SELECT asset FROM assets ORDER BY asset').fetchall():
                    asset=row[0];latest=ingest.latest.get(asset)
                    recorded=store.execute('SELECT payload FROM cards WHERE asset=? AND run=? ORDER BY stroke DESC LIMIT 1',
                        (asset,latest.run_id)).fetchone() if latest else None
                    completed=json.loads(recorded[0]) if recorded else {}
                    auxiliary=ingest.aux[asset]
                    assets.append(dict(asset_id=asset,site_id=site_by_asset.get(asset),
                        last_sample=latest.timestamp.isoformat() if latest else None,latest_sequence=latest.sequence if latest else None,
                        mode=auxiliary.get('status',{}).get('mode','unknown'),spm=latest.spm if latest else None,
                        power_w=auxiliary.get('telemetry/electrical',{}).get('power_w'),
                        intake_pa=auxiliary.get('telemetry/pressure',{}).get('intake_pa'),
                        diagnosis=completed.get('diagnosis'),quality=completed.get('quality'),
                        stroke_count=store.execute('SELECT count(*) FROM cards WHERE asset=?',(asset,)).fetchone()[0]))
                return assets
            if route==["fleet"]:
                assets=[dict(asset_id=row[0],site_id=site_by_asset.get(row[0]),
                             run_id=ingest.latest[row[0]].run_id if row[0] in ingest.latest else None,
                             last_sample=ingest.latest[row[0]].timestamp.isoformat() if row[0] in ingest.latest else None,
                             latest_sequence=ingest.latest[row[0]].sequence if row[0] in ingest.latest else None,
                             latest_stroke=ingest.latest[row[0]].stroke_id if row[0] in ingest.latest else None,
                             stroke_count=store.execute("SELECT count(*) FROM cards WHERE asset=?",(row[0],)).fetchone()[0])
                        for row in store.execute("SELECT asset FROM assets ORDER BY asset").fetchall()]
                return dict(sites=sorted(set(site_by_asset.values())),wells=assets)
            if not route or route[0] not in ("snapshot","cards","telemetry"):
                raise KeyError()
            asset = query.get("asset","SRP_001")
            if not store.permits(asset):
                raise KeyError()
            if route[0]=="telemetry":
                conditions, params = ["asset=?"], [asset]
                if "run" in query:
                    conditions.append("run=?")
                    params.append(query["run"])
                if "stroke" in query:
                    conditions.append("stroke=?")
                    params.append(int(query["stroke"]))
                if "since" in query:
                    conditions.append("recorded>=?")
                    params.append(query["since"])
                if "until" in query:
                    conditions.append("recorded<=?")
                    params.append(query["until"])
                limit = min(5000, int(query.get("limit", 1000)))
                rows = store.execute("SELECT payload FROM telemetry WHERE " + " AND ".join(conditions) +
                                     f" ORDER BY sequence ASC LIMIT {limit}", params).fetchall()
                samples = [json.loads(r[0]) for r in rows]
                if query.get("format") == "csv":
                    buffer = io.StringIO()
                    if samples:
                        writer = csv.DictWriter(buffer, fieldnames=list(samples[0].keys()))
                        writer.writeheader()
                        writer.writerows(samples)
                    return Download(f"{asset}_telemetry.csv", buffer.getvalue(), "text/csv")
                return dict(asset_id=asset, count=len(samples), telemetry=samples)
            if route[0]=="snapshot":
                last = ingest.latest.get(asset)
                live = list(ingest.live_samples.get(asset, []))
                if not live and last:
                    live = ingest.raw(asset,last.run_id,last.stroke_id)
                card_payload = ingest.latest_cards.get(asset)
                if card_payload and card_payload.get("downhole", {}).get("status") != "SOLVED":
                    solved = ingest.latest_solved_cards.get(asset)
                    if solved:
                        card_payload["downhole"] = solved.get("downhole", card_payload.get("downhole"))
                        if not card_payload.get("surface") and solved.get("surface"):
                            card_payload["surface"] = solved.get("surface")
                elif not card_payload:
                    card_payload = ingest.latest_solved_cards.get(asset)

                if not card_payload and last:
                    row = store.execute("SELECT payload FROM cards WHERE asset=? AND run=? ORDER BY stroke DESC LIMIT 1",
                                        (asset,last.run_id)).fetchone()
                    if not row:
                        row = store.execute("SELECT payload FROM cards WHERE asset=? ORDER BY recorded DESC LIMIT 1",
                                            (asset,)).fetchone()
                    if row:
                        card_payload = json.loads(row[0])
                        ingest.latest_cards[asset] = card_payload
                        if card_payload.get("downhole", {}).get("status") == "SOLVED":
                            ingest.latest_solved_cards[asset] = card_payload
                return dict(asset_id=asset, connected=broker.is_connected(), counts=dict(ingest.stats),
                            auxiliary=ingest.aux[asset], latest=last.model_dump(mode="json") if last else None,
                            live=[s.model_dump(mode="json") for s in live],
                            card=card_payload)
            if len(route)==3:
                run, stroke = route[1],int(route[2])
                row = store.execute("SELECT payload FROM cards WHERE asset=? AND run=? AND stroke=?",
                                    (asset,run,stroke)).fetchone()
                if not row:
                    raise KeyError()
                card = json.loads(row[0])
                if query.get("format")=="configuration-json":
                    if "asset_configuration" not in card:
                        raise ValueError("Stroke has no equipment configuration")
                    return Download("srp_well_configuration.json",json.dumps(card["asset_configuration"],indent=2),"application/json")
                if query.get("format")=="engineering":
                    kind=query.get("kind","surface")
                    rows=list(card_rows(card,kind,ingest.raw(asset,run,stroke) if kind=="raw" else ()))
                    if not rows:
                        raise ValueError("No exportable samples")
                    return Download(EXPORT_NAMES[kind],csv_text(list(rows[0]),rows))
                if query.get("format")=="csv":
                    values = card[query.get("kind","surface")]
                    buffer = io.StringIO()
                    output = csv.writer(buffer)
                    output.writerow(["position_m","load_n"])
                    output.writerows(zip(values["position_m"],values["load_n"]))
                    return buffer.getvalue()
                return card
            conditions, params = ["asset=?"],[asset]
            for key, op in [("run","run="),("stroke","stroke="),("since","recorded>="),("until","recorded<=")]:
                if key in query:
                    conditions.append(op+"?")
                    params.append(int(query[key]) if key=="stroke" else query[key])
            rows = store.execute("SELECT payload FROM cards WHERE "+" AND ".join(conditions)+
                                 " ORDER BY recorded DESC LIMIT 100",params).fetchall()
            cards = [json.loads(r[0]) for r in rows]
            return [c for c in cards if all(c["diagnosis"].get(field)==query[key] for key,field in
                (("fault","label"),("model","model_version")) if key in query)]

    serve(int(os.getenv("API_PORT",8002)),dispatch,max_body=2000000)


if __name__=="__main__":
    main()
