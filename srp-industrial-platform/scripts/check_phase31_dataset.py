import hashlib
import json
import unittest
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/generated/phase31"


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((DATA/"manifest.json").read_text())

    def test_csv_parquet_roundtrip_and_identity(self):
        for name in ("dynamometer","electrical","pressure","features"):
            csv=pd.read_csv(DATA/f"ml_inputs/{name}.csv")
            parquet=pd.read_parquet(DATA/f"ml_inputs/{name}.parquet")
            self.assertEqual(list(csv.columns),list(parquet.columns))
            self.assertEqual(len(csv),len(parquet))
            self.assertEqual(csv["asset_id"].tolist(),parquet["asset_id"].tolist())
        dynamometer=pd.read_parquet(DATA/"ml_inputs/dynamometer.parquet")
        self.assertFalse(dynamometer.duplicated(["asset_id","run_id","sequence"]).any())
        self.assertEqual(dynamometer.asset_id.nunique(),30)

    def test_truth_and_label_isolation(self):
        for file in (DATA/"ml_inputs").iterdir():
            if file.suffix=="parquet":
                columns=set(pd.read_parquet(file).columns)
                self.assertFalse(columns & {"fault","fault_mechanism","severity","pump_load_n",
                                            "pump_position_m","chamber_pa"},file.name)
        self.assertTrue((DATA/"simulation_truth/scenario_labels.jsonl").exists())
        self.assertTrue((DATA/"simulation_truth/downhole_truth.jsonl").exists())

    def test_checksums_and_validation_counts(self):
        for entry in self.manifest["files"]:
            path=ROOT/entry["path"]
            self.assertEqual(path.stat().st_size,entry["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry["sha256"])
        rows=[json.loads(line) for line in (DATA/"validation.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows),self.manifest["completed_strokes"])
        self.assertEqual(sum(x["status"]=="SYNTHETIC_VALIDATED" for x in rows),self.manifest["valid_strokes"])
        self.assertEqual(len({(x["asset_id"],x["run_id"],x["stroke_id"]) for x in rows}),len(rows))


if __name__=="__main__":unittest.main(verbosity=2)
