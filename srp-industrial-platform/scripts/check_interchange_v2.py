import sys
import unittest

from context import APM
sys.path.insert(0,str(APM/"backend"))
from interchange import import_file


class InterchangeTests(unittest.TestCase):
    def setUp(self):
        self.data=dict(kind="surface",filename="example.txt",well_id="TEST_1",stroke_id="3",
                       position_unit="ft",load_unit="kN",mapping=dict(position="Travel",load="Force",index="Ordinal",timestamp="Time"),
                       content="Ordinal|Travel|Force|Time\n2|0|2|2026-01-01T00:00:02Z\n"
                               "0|1|4|2026-01-01T00:00:00Z\n1|2|3|2026-01-01T00:00:01Z\n")

    def test_mapping_sorting_and_idempotency(self):
        first=import_file(self.data)
        card=first["cards"][0]
        self.assertEqual(card["position_m"],[.3048,.6096,0.])
        self.assertEqual(card["load_n"],[4000,3000,2000])
        self.assertEqual(card["time_s"],[0.,1.,2.])
        self.assertEqual(import_file(self.data)["dataset_id"],first["dataset_id"])

    def test_reject_duplicates_and_nonfinite(self):
        for replacement in ("0|2|3","1|2|inf"):
            with self.assertRaises(ValueError):
                import_file(self.data|dict(content=self.data["content"].replace("1|2|3",replacement)))

    def test_declared_gaps_degrade_geometry(self):
        record=import_file(self.data|dict(content=self.data["content"].replace("2|0|2","4|0|2")))["cards"][0]
        self.assertEqual(record["quality"],"DEGRADED")
        self.assertIsNone(record["area_j"])


if __name__=="__main__":
    unittest.main(verbosity=2)
