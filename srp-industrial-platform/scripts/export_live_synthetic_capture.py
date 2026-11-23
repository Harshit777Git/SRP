"""Export the current APM simulator capture with explicit synthetic provenance."""
import csv, hashlib, json, sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"state/phase32_collect/apm/apm.db"
OUT=ROOT/"data/generated/apm_live_capture_2026-11-17"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(f"file:{DB.as_posix()}?mode=ro",uri=True)
    telemetry=[json.loads(row[0]) for row in db.execute("SELECT payload FROM telemetry ORDER BY asset,run,sequence")]
    cards=[json.loads(row[0]) for row in db.execute("SELECT payload FROM cards ORDER BY asset,run,stroke")]
    jobs=[dict(zip(("job_key","asset","run","stroke","state","enqueued","started","completed","attempts","error"),row))
          for row in db.execute("SELECT job_key,asset,run,stroke,state,enqueued,started,completed,attempts,error FROM stroke_jobs ORDER BY asset,run,stroke")]
    db.close()
    raw=OUT/"telemetry.jsonl"; raw.write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in telemetry),encoding="utf8")
    if telemetry:
        fields=list(dict.fromkeys(k for item in telemetry for k in item))
        with (OUT/"telemetry.csv").open("w",newline="",encoding="utf8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(telemetry)
    (OUT/"cards.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in cards),encoding="utf8")
    (OUT/"stroke_jobs.json").write_text(json.dumps(jobs,indent=2),encoding="utf8")
    streams={}
    for x in telemetry:streams[x.get("source","unknown")]=streams.get(x.get("source","unknown"),0)+1
    manifest={"dataset_id":"phase32-apm-live-synthetic-2026-11-17","origin":"SYNTHETIC_SIMULATOR_TELEMETRY",
      "training_permission":"INTERNAL_SYNTHETIC_EXPERIMENTS_ONLY","fault_labels":"NONE_INDEPENDENTLY_VERIFIED",
      "run_ids":sorted({x["run_id"] for x in telemetry}),"wells":sorted({x["asset_id"] for x in telemetry}),
      "telemetry_samples":len(telemetry),"surface_downhole_cards":len(cards),
      "solved_downhole_cards":sum(x.get("downhole",{}).get("status")=="SOLVED" for x in cards),
      "stroke_jobs":len(jobs),"completed_jobs":sum(x["state"]=="COMPLETED" for x in jobs),
      "failed_jobs":sum(x["state"]=="FAILED" for x in jobs),"source_counts":streams,
      "artifacts":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":main()
