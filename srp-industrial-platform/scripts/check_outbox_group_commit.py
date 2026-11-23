"""Check durable return, per-well order, capacity, and invalid-write rollback."""
import json
import queue
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from context import ROOT
from mqtt_publisher.outbox import Outbox

with tempfile.TemporaryDirectory(prefix='srp-outbox-check-') as folder:
    path=Path(folder)/'outbox.db'
    out=Outbox.__new__(Outbox)
    out.lock=threading.Lock();out.db=sqlite3.connect(path,check_same_thread=False)
    out.db.execute('CREATE TABLE outbox(id INTEGER PRIMARY KEY,topic TEXT,body TEXT,retain INTEGER,queued REAL,ready REAL)')
    out.db.commit();out.count=out.dropped=0;out.maximum=10000;out.pending_appends=queue.Queue()
    threading.Thread(target=out.persist,daemon=True).start()
    def write(well):
        for sequence in range(20):
            name=f'well-{well}'
            out.append([(name,{'sequence':sequence},False)],delay_s=.25)
            # A second connection must see the row when append returns.
            with closing(sqlite3.connect(path)) as check:
                assert check.execute('SELECT count(*) FROM outbox WHERE topic=?',(name,)).fetchone()[0]==sequence+1
    with ThreadPoolExecutor(max_workers=30) as pool:list(pool.map(write,range(30)))
    with out.lock:
        assert out.count==600
        for well in range(30):
            rows=out.db.execute('SELECT body,ready-queued FROM outbox WHERE topic=? ORDER BY id',(f'well-{well}',)).fetchall()
            assert [json.loads(r[0])['sequence'] for r in rows]==list(range(20))
            assert all(abs(r[1]-.25)<1e-6 for r in rows)
    out.maximum=607
    out.append([('overflow',{'sequence':i},False) for i in range(10)])
    assert out.count==607 and out.dropped==3
    out.maximum=10000
    try:out.append([('invalid',{'value':float('nan')},False)])
    except ValueError:pass
    else:raise AssertionError('nonfinite payload accepted')
    assert out.count==607
    out.append([('recovery',{'value':1},False)])
    assert out.count==608
    with closing(sqlite3.connect(path)) as reopened:assert reopened.execute('SELECT count(*) FROM outbox').fetchone()[0]==608
    out.db.close()
print('PASS: concurrent durable return, per-well ordering, capacity, rollback and recovery')
