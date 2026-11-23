import json
import os
import time
import uuid
from contextlib import ExitStack

import psutil

from context import ROOT
from run_acceptance import http, local, wait_for


SIM = "http://127.0.0.1:18101"
APM = "http://127.0.0.1:18102"


def main():
    (ROOT/"state/acceptance").mkdir(parents=True,exist_ok=True)
    cases=[]
    with ExitStack() as stack:
        local(stack, sim=18101, apm=18102, mqtt_port=18884, frontends=False, scope=f"benchmark/{uuid.uuid4().hex[:10]}")
        wait_for(lambda:http(SIM,"/health")["connected"],"simulator")
        wait_for(lambda:http(APM,"/health")["connected"],"APM")
        template=http(SIM,"/assets")[0]
        prefix = f"BENCH_{time.time_ns() % 1000000}"
        process_ids = [p.pid for p in psutil.Process().children()]
        process = [psutil.Process(pid) for pid in process_ids]
        for count in (1,5,10):
            assets=[]
            for i in range(count):
                asset=f"{prefix}_{count}_{i}"
                well=template|{"asset_id":asset,"dynamometer_hz":50}
                http(SIM,"/assets",well)
                http(APM,"/assets",well)
                assets.append(asset)
            for asset in assets:
                http(SIM,f"/assets/{asset}/start",{"speed":1,"paused":True})
            wait_for(lambda:http(SIM,"/health")["queued"]==0,"pre-benchmark outbox drain")
            for asset in assets:
                http(SIM,f"/assets/{asset}/start",{})
            time.sleep(3)
            before=http(APM,"/health")["counts"]
            publisher_before=http(SIM,"/health")
            for p in process:
                p.cpu_percent()
            t0=time.perf_counter()
            runtime_samples=[]
            for _ in range(10):
                time.sleep(1)
                info=http(SIM,"/health")
                runtime_samples.append(dict(cpu=sum(p.cpu_percent() for p in process),
                    rss=sum(p.memory_info().rss for p in process), lag=info["ack_lag_s"],
                    queued=info["queued"]))
            elapsed=time.perf_counter()-t0
            after=http(APM,"/health")["counts"]
            pub=http(SIM,"/health")
            difference=lambda field: after.get(field,0)-before.get(field,0)
            samples=difference("accepted")
            cases.append(dict(wells=count,duration_s=elapsed,dyno_hz_per_well=50,samples=samples,
                received_per_s=samples/elapsed,expected_per_s=50*count,
                broker_acks_per_s=(pub["sent"]-publisher_before["sent"])/elapsed,
                observed_missing_sequences=difference("observed_gaps"),
                publisher_dropped=pub["dropped"]-publisher_before["dropped"],
                ingest_mean_processing_ms=(difference("ingest_processing_us")/max(1,samples))/1000,
                mean_process_cpu_pct=sum(s["cpu"] for s in runtime_samples)/len(runtime_samples),
                peak_combined_rss_mib=max(s["rss"] for s in runtime_samples)/1024**2,
                peak_sampled_publisher_ack_lag_s=max(s["lag"] for s in runtime_samples),
                peak_sampled_outbox_rows=max(s["queued"] for s in runtime_samples),
                processor_count=os.cpu_count()))
            for asset in assets:
                http(SIM,f"/assets/{asset}/stop",{})
            if count<10:
                wait_for(lambda:http(SIM,"/health")["queued"]==0,"post-benchmark outbox drain")
                time.sleep(.5)
    report=dict(broker="Aedes",database="SQLite WAL",cases=cases)
    (ROOT/"data/evaluation/performance.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
