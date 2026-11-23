import json
import sys
import unittest
from datetime import timedelta

from context import ROOT, APM
sys.path.insert(0,str(APM/"backend"))

from fault_detection.monitor import compare_stroke
from model_registry.registry import Registry
from server import Ingest
from shared.contracts import Sample, Well
from storage import Store


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.ingest = Ingest(self.store, Registry(), 256)
        records = ROOT/"data/generated/healthy.telemetry.jsonl"
        self.samples = [Sample.model_validate_json(line) for line in records.read_text().splitlines()]
        last = self.samples[-1]
        self.well = Well.model_validate(json.loads((ROOT/"docker/assets.json").read_text())[1])
        self.store.asset(self.well)
        self.boundary = last.model_copy(update=dict(sequence=last.sequence+1,stroke_id=last.stroke_id+1,
            timestamp=last.timestamp+timedelta(seconds=.02),sample_index=0,crank_angle_deg=0.))

    def tearDown(self):
        self.ingest.stop_worker()
        self.store.db.close()

    def card(self):
        stored = self.store.execute("SELECT payload FROM cards WHERE asset=?",(self.well.asset_id,)).fetchone()
        return json.loads(stored[0])

    def test_duplicate_late_recovery_and_run_geometry(self):
        for sample in self.samples[:50]+self.samples[51:]:
            self.ingest.consume(sample)
        self.ingest.consume(self.boundary)
        self.ingest.start_worker()
        state=self.ingest.wait_for_stroke(self.well.asset_id,self.samples[0].run_id,self.samples[0].stroke_id,timeout=10)
        self.assertEqual(state["state"],"COMPLETED")
        self.assertEqual(self.card()["quality"],"DEGRADED")
        self.store.asset(self.well.model_copy(update={"damping_s":2.}))
        self.ingest.consume(self.samples[50])
        self.ingest.consume(self.boundary)
        self.ingest.wait_for_stroke(self.well.asset_id,self.samples[0].run_id,self.samples[0].stroke_id,timeout=10)
        card=self.card()
        self.assertEqual(card["quality"],"GOOD")
        self.assertEqual(len(card["downhole"]["position_m"]),256)
        self.assertEqual(card["asset_configuration"]["damping_s"],self.well.damping_s)
        self.assertEqual(self.store.execute("SELECT count(*) FROM cards").fetchone()[0],1)
        self.assertEqual(self.ingest.stats["duplicates"],1)
        self.assertEqual(self.ingest.stats["out_of_order"],1)
        self.assertEqual(self.ingest.stats["observed_gaps"],1)

    def test_monitor_alerts_on_captured_valve_leak(self):
        fixture=json.loads((ROOT/"data/evaluation/acceptance_cards.json").read_text())
        healthy, altered=fixture["healthy"],fixture["altered"]
        reference=[dict(healthy,stroke_id=stroke) for stroke in range(3)]
        self.assertEqual(compare_stroke(healthy,reference)["status"],"WITHIN_REFERENCE")
        self.assertEqual(compare_stroke(altered,reference)["status"],"DYNACARD_CHANGE")
        self.assertEqual(compare_stroke(altered,reference[:2])["status"],"AWAITING_REFERENCE")

    def test_reset_after_accelerated_run_follows_new_samples(self):
        old=self.samples[0]
        reset=old.model_copy(update=dict(run_id="RESET",sequence=0,
                                         timestamp=old.timestamp-timedelta(minutes=2)))
        self.ingest.consume(old)
        self.ingest.consume(reset)
        self.ingest.consume(self.samples[1])
        self.assertEqual(self.ingest.latest[old.asset_id].run_id,"RESET")
        self.assertEqual(self.ingest.latest[old.asset_id].sequence,0)

    def test_run_and_asset_isolation(self):
        second = self.well.model_copy(update={"asset_id":"FIELD_2"})
        self.store.asset(second)
        for sample in (self.samples[0],self.samples[0].model_copy(update={"asset_id":second.asset_id,"source":"FIELD"}),
                       self.samples[0].model_copy(update={"run_id":"REPLACEMENT"})):
            self.ingest.consume(sample)
        self.assertEqual(self.ingest.stats["accepted"],3)
        self.assertEqual(self.ingest.stats["duplicates"],0)
        self.assertEqual(len(self.ingest.raw(self.well.asset_id,self.samples[0].run_id,self.samples[0].stroke_id)),1)
        self.assertEqual(len(self.ingest.raw(second.asset_id,self.samples[0].run_id,self.samples[0].stroke_id)),1)

    def test_optional_calibration_metadata_round_trip(self):
        # Old payloads remain valid, while documented field metadata persists.
        field=self.samples[0].model_copy(update=dict(source="FIELD",sensor_id="LOAD-17",
            calibration_id="CAL-2026-04",calibration_date=self.samples[0].timestamp,
            load_uncertainty_lbf=4.2,position_uncertainty_in=.01,
            acquisition_method="portable_dynamometer"))
        payload=field.model_dump_json()
        restored=Sample.model_validate_json(payload)
        self.assertEqual(restored.sensor_id,"LOAD-17")
        self.assertEqual(restored.calibration_id,"CAL-2026-04")
        self.assertEqual(restored.load_uncertainty_lbf,4.2)
        self.assertIsNone(self.samples[0].sensor_id)


if __name__=="__main__":
    unittest.main(verbosity=2)
