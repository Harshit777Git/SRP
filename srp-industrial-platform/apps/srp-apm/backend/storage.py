import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class Store:
    """Use an isolated SQLite database locally or a PostgreSQL schema in Compose."""

    def __init__(self, path, dsn=None):
        self.lock = threading.RLock()
        self.postgres = bool(dsn)
        if dsn:
            import psycopg
            self.db = (psycopg.connect(autocommit=True,**dsn) if isinstance(dsn,dict)
                       else psycopg.connect(dsn,autocommit=True))
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, timeout=60.0, check_same_thread=False, isolation_level=None)
            self.execute("PRAGMA journal_mode=WAL")
            self.execute("PRAGMA synchronous=NORMAL")
            self.execute("PRAGMA busy_timeout=60000")
            self.execute("PRAGMA foreign_keys=ON")
        self.execute("""CREATE TABLE IF NOT EXISTS telemetry (
            asset TEXT NOT NULL, run TEXT NOT NULL, sequence BIGINT NOT NULL,
            stroke BIGINT NOT NULL, recorded TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(asset,run,sequence))""")
        self.execute("CREATE INDEX IF NOT EXISTS telemetry_stroke ON telemetry(asset,run,stroke,sequence)")
        self.execute("""CREATE TABLE IF NOT EXISTS cards (
            asset TEXT NOT NULL, run TEXT NOT NULL, stroke BIGINT NOT NULL,
            first_sequence BIGINT NOT NULL, recorded TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(asset,run,stroke),
            FOREIGN KEY(asset,run,first_sequence) REFERENCES telemetry(asset,run,sequence))""")
        self.execute("CREATE INDEX IF NOT EXISTS cards_recorded ON cards(asset,recorded)")
        self.execute("CREATE INDEX IF NOT EXISTS cards_asset_stroke ON cards(asset,stroke DESC)")
        self.execute("CREATE INDEX IF NOT EXISTS cards_asset_run_stroke ON cards(asset,run,stroke DESC)")
        self.execute("""CREATE TABLE IF NOT EXISTS stroke_jobs (
            job_key TEXT PRIMARY KEY, asset TEXT NOT NULL, run TEXT NOT NULL, stroke BIGINT NOT NULL,
            state TEXT NOT NULL, enqueued TEXT NOT NULL, started TEXT, completed TEXT,
            attempts INTEGER NOT NULL DEFAULT 0, error TEXT, payload TEXT NOT NULL)""")
        self.execute("CREATE TABLE IF NOT EXISTS assets (asset TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.execute("CREATE TABLE IF NOT EXISTS imported_datasets (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.execute("""CREATE TABLE IF NOT EXISTS historical_references (
            asset TEXT NOT NULL, stroke TEXT NOT NULL, version TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(asset,stroke,version))""")
        self.execute("""CREATE TABLE IF NOT EXISTS reference_assets (
            asset TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            data_mode TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)""")
        self.execute("""CREATE TABLE IF NOT EXISTS run_assets (
                    asset TEXT NOT NULL REFERENCES assets(asset), run TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(asset,run))""")

    def execute(self, query, args=()):
        with self.lock:
            return self.db.execute(query.replace("?", "%s") if self.postgres else query, args)

    def insert(self, sample):
        from datetime import timezone
        return self.execute("INSERT INTO telemetry VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                            (sample.asset_id,sample.run_id,sample.sequence,sample.stroke_id,
                             sample.timestamp.astimezone(timezone.utc).isoformat(),
                             sample.model_dump_json())).rowcount == 1

    def insert_many(self, samples):
        with self.lock:
            from datetime import timezone
            rows=[(s.asset_id,s.run_id,s.sequence,s.stroke_id,
                   s.timestamp.astimezone(timezone.utc).isoformat(),s.model_dump_json()) for s in samples]
            if not rows:
                return 0
            if self.postgres:
                with self.db.cursor() as cursor:
                    cursor.executemany('INSERT INTO telemetry VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',rows)
                    return cursor.rowcount
            if self.db.in_transaction:
                before=self.db.total_changes
                self.db.executemany('INSERT INTO telemetry VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING',rows)
                return self.db.total_changes-before
            self.db.execute("BEGIN")
            try:
                before=self.db.total_changes
                self.db.executemany("INSERT INTO telemetry VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",rows)
                inserted=self.db.total_changes-before
                self.db.execute("COMMIT")
                return inserted
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.postgres:
                with self.db.transaction():yield
            elif self.db.in_transaction:
                yield
            else:
                self.db.execute('BEGIN')
                try:
                    yield
                    self.db.execute('COMMIT')
                except Exception:
                    self.db.execute('ROLLBACK')
                    raise

    def put(self, card):
        self.execute("""INSERT INTO cards VALUES (?,?,?,?,?,?)
                     ON CONFLICT(asset,run,stroke) DO UPDATE SET payload=excluded.payload""",
                     (card["asset_id"],card["run_id"],card["stroke_id"],card["raw_sequence"][0],
                      card["timestamp"],json.dumps(card,allow_nan=False)))

    def asset(self, well):
        self.execute("""INSERT INTO assets VALUES (?,?)
                     ON CONFLICT(asset) DO UPDATE SET payload=excluded.payload""",
                     (well.asset_id,well.model_dump_json()))

    def permits(self, asset):
        return self.execute("SELECT 1 FROM assets WHERE asset=?", (asset,)).fetchone() is not None

    def enqueue_stroke(self, asset, run, stroke, samples, closing):
        key=f"{asset}:{run}:{stroke}"
        payload=json.dumps({"samples":[s.model_dump(mode="json") for s in samples],
                            "closing":closing.model_dump(mode="json")},allow_nan=False)
        from datetime import datetime,timezone
        now=datetime.now(timezone.utc).isoformat()
        self.execute("INSERT INTO stroke_jobs(job_key,asset,run,stroke,state,enqueued,payload) VALUES (?,?,?,?,?,?,?) ON CONFLICT(job_key) DO UPDATE SET state='QUEUED',enqueued=excluded.enqueued,payload=excluded.payload,error=NULL WHERE stroke_jobs.state IN ('COMPLETED','FAILED')",
                     (key,asset,run,stroke,"QUEUED",now,payload))
        return key

    def stroke_job(self, asset, run, stroke):
        row=self.execute("SELECT job_key,asset,run,stroke,state,enqueued,started,completed,attempts,error FROM stroke_jobs WHERE job_key=?",
                         (f"{asset}:{run}:{stroke}",)).fetchone()
        if row is None:return None
        return dict(zip(("job_key","asset_id","run_id","stroke_id","state","enqueued_at","started_at","completed_at","attempts","error"),row))
