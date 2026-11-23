import json
import os
import queue
import sqlite3
import socket
import threading
import time
from datetime import datetime, timezone

from shared.mqtt import client, connect, qos


class Outbox:
    def __init__(self, path, maximum=150000):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path,check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS outbox
                        (id INTEGER PRIMARY KEY, topic TEXT, body TEXT, retain INTEGER, queued REAL)""")
        if "ready" not in {row[1] for row in self.db.execute("PRAGMA table_info(outbox)")}:
            self.db.execute("ALTER TABLE outbox ADD COLUMN ready REAL NOT NULL DEFAULT 0")
        self.count = self.db.execute("SELECT count(*) FROM outbox").fetchone()[0]
        self.maximum = maximum
        self.sent = self.failures = self.dropped = self.lag = 0
        self.inflight = {}
        self.inflight_ids = set()
        self.acknowledged = queue.SimpleQueue()
        self.pending_appends = queue.Queue()
        self.max_inflight = 500
        self.topics = set()
        self.send_after = 0.
        self.client = client(os.getenv("MQTT_CLIENT_ID", "srp-simulator"))
        self.qos = qos()
        self.client.will_set("srp/v1/simulator/status",'{"connected":false}',self.qos,True)
        self.client.on_connect = self.connected
        self.client.max_queued_messages_set(5000)
        self.client.max_inflight_messages_set(self.max_inflight)
        self.client.on_publish = self.published
        self.client.on_socket_open = self.configure_socket
        connect(self.client)
        threading.Thread(target=self.persist,daemon=True).start()
        threading.Thread(target=self.send,daemon=True).start()

    def configure_socket(self, conn, userdata, active_socket):
        active_socket.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)

    def connected(self, conn, userdata, flags, reason, properties):
        if not reason.is_failure:
            # Give subscribers a short window to restore subscriptions after broker restart.
            self.send_after = time.monotonic()+1.5
            conn.publish("srp/v1/simulator/status",'{"connected":true}',self.qos,True)

    def published(self, conn, userdata, mid, reason, properties):
        # Paho may hold its own message lock during this callback. Do not take
        # the outbox lock here while send() may be inside client.publish().
        self.acknowledged.put(mid)

    def append(self, messages, delay_s=0.):
        # Group concurrent well writes into one durable transaction. Callers
        # still wait for COMMIT, so a returned append has the same durability.
        completed = threading.Event()
        errors = []
        self.pending_appends.put((messages,delay_s,time.time(),completed,errors))
        completed.wait()
        if errors:
            raise errors[0]

    def persist(self):
        while True:
            batch = [self.pending_appends.get()]
            deadline = time.monotonic()+.003
            while len(batch)<256:
                remaining = deadline-time.monotonic()
                if remaining<=0:break
                try:batch.append(self.pending_appends.get(timeout=remaining))
                except queue.Empty:break
            try:
                accepted_count = dropped_count = 0
                with self.lock:
                    rows=[]
                    capacity=max(0,self.maximum-self.count)
                    for messages,delay_s,queued,_,_ in batch:
                        accepted=messages[:capacity]
                        rows.extend((name,json.dumps(body,allow_nan=False),retain,queued,queued+delay_s)
                                    for name,body,retain in accepted)
                        capacity-=len(accepted)
                        accepted_count+=len(accepted)
                        dropped_count+=len(messages)-len(accepted)
                    with self.db:
                        self.db.executemany('INSERT INTO outbox(topic,body,retain,queued,ready) VALUES (?,?,?,?,?)',rows)
                    self.count+=accepted_count
                    self.dropped+=dropped_count
            except Exception as error:
                for *_,errors in batch:errors.append(error)
            finally:
                for _,_,_,completed,_ in batch:
                    completed.set()
                    self.pending_appends.task_done()

    def send(self):
        while True:
            with self.lock:
                completed=[]
                while not self.acknowledged.empty():
                    mid=self.acknowledged.get_nowait()
                    item=self.inflight.pop(mid,None)
                    if item is not None:
                        row,_=item
                        completed.append(row)
                if completed:
                    with self.db:
                        self.db.executemany("DELETE FROM outbox WHERE id=?",[(row[0],) for row in completed])
                    for row in completed:
                        self.inflight_ids.discard(row[0])
                        self.topics.add(row[1])
                        self.lag=time.time()-row[4]
                    self.sent+=len(completed)
                    self.count-=len(completed)
                # A timed-out publish stays durable and can be replayed. APM's
                # (asset, run, sequence) primary key makes a replay idempotent.
                expired=[mid for mid,(_,started) in self.inflight.items()
                         if time.monotonic()-started>10]
                for mid in expired:
                    row,_=self.inflight.pop(mid)
                    self.inflight_ids.discard(row[0])
                    self.failures+=1
                if self.client.is_connected() and time.monotonic()>=self.send_after:
                    capacity=self.max_inflight-len(self.inflight)
                    if capacity>0:
                        rows=self.db.execute("""SELECT id,topic,body,retain,queued FROM outbox
                            WHERE ready<=? ORDER BY id LIMIT ?""",
                            (time.time(),self.max_inflight+capacity)).fetchall()
                        for row in rows:
                            if row[0] in self.inflight_ids:
                                continue
                            receipt=self.client.publish(row[1],row[2],self.qos,bool(row[3]))
                            if receipt.rc != 0:
                                self.failures+=1
                                break
                            self.inflight[receipt.mid]=(row,time.monotonic())
                            self.inflight_ids.add(row[0])
                            capacity-=1
                            if capacity==0:
                                break
            time.sleep(.005 if self.count else .025)

    def status(self):
        with self.lock:
            return dict(connected=self.client.is_connected(), queued=self.count, sent=self.sent,
                        retry_failures=self.failures, dropped=self.dropped,
                        ack_lag_s=self.lag, inflight=len(self.inflight),topics=sorted(self.topics))
