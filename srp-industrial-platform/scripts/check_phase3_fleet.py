import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/srp-simulator")]
from physics.engine import Engine, Mechanism
from shared.contracts import Well
from virtual_sensors.sampling import Sensors


class FleetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fleet = json.loads((ROOT / "config/fleet/us_srp_30_wells.json").read_text())["wells"]

    def test_unique_sites_and_valid_mechanisms(self):
        self.assertEqual(len(self.fleet), 30)
        self.assertEqual(len({x["well"]["asset_id"] for x in self.fleet}), 30)
        sites = {x["site_id"] for x in self.fleet}
        self.assertEqual(len(sites), 6)
        self.assertEqual({sum(x["site_id"] == site for x in self.fleet) for site in sites}, {5})
        for entry in self.fleet:
            Mechanism(Well.model_validate(entry["well"]))

    def test_sensor_metadata_and_truth_isolation(self):
        well = Well.model_validate(self.fleet[0]["well"])
        engine = Engine(well)
        sensor = Sensors(engine, "phase3-check")
        sensor.site_id = self.fleet[0]["site_id"]
        sample, _ = sensor.read(engine.state())
        payload = sample.model_dump()
        self.assertEqual(payload["site_id"], sensor.site_id)
        self.assertEqual(payload["units"]["polished_rod_load_lbf"], "lbf")
        self.assertNotIn("fault", payload)
        self.assertNotIn("pump_load_n", payload)

    def test_future_split_by_complete_well(self):
        manifest = json.loads((ROOT / "data/evaluation/phase3/future_split_manifest.json").read_text())
        groups = [set(ids) for ids in manifest["splits"].values()]
        self.assertEqual([len(g) for g in groups], [18, 6, 6])
        self.assertEqual(len(set.union(*groups)), 30)
        self.assertFalse(any(a & b for i, a in enumerate(groups) for b in groups[i+1:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
