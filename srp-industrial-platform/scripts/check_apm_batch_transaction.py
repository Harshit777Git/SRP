"""Verify nested inserts, duplicate counting and rollback for MQTT batching."""
import sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
from context import ROOT,APM
sys.path.insert(0,str(APM/'backend'))
from storage import Store
from shared.contracts import Sample

with tempfile.TemporaryDirectory(prefix='srp-apm-batch-') as folder:
    store=Store(Path(folder)/'test.db')
    def sample(sequence):
        return Sample(asset_id='BATCH_TEST',source='SIMULATOR',timestamp=datetime.now(timezone.utc),run_id='batch',
            sequence=sequence,stroke_id=0,sample_index=sequence,polished_rod_position_in=1,
            polished_rod_load_lbf=1000,crank_angle_deg=sequence,spm=6,quality='GOOD')
    with store.transaction():
        assert store.insert_many([sample(0)])==1
        assert store.insert_many([sample(0)])==0
        assert store.insert_many([sample(1),sample(2)])==2
    assert store.execute('SELECT count(*) FROM telemetry').fetchone()[0]==3
    try:
        with store.transaction():
            store.insert_many([sample(3)])
            raise RuntimeError('rollback check')
    except RuntimeError:pass
    assert store.execute('SELECT count(*) FROM telemetry').fetchone()[0]==3
    assert store.insert_many([sample(3)])==1
    store.db.close()
print('PASS: grouped inserts, accurate duplicate counts, rollback and recovery')
