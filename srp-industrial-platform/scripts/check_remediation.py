import os
import unittest
from unittest.mock import patch

from context import ROOT
import numpy as np
from configurations.presets import presets
from evaluate_wave import cycle
from fault_detection.models import baseline, inputs
from fault_detection.remediation import live_inputs, physical_inputs
from model_registry.registry import Registry, gate_passes


class RemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card,*_=cycle(presets()[0])
        cls.artifact=ROOT/"data/training/remediation_physics_features.joblib"

    def test_offline_live_parity_and_time_validation(self):
        a=live_inputs(self.card)
        b=physical_inputs(inputs(self.card)[0],self.card["asset_configuration"],self.card["spm"])
        for left,right in zip(a,b):
            np.testing.assert_array_equal(left,right)
        broken=self.card|dict(downhole=self.card["downhole"]|dict(time_s=self.card["downhole"]["time_s"][::-1]))
        with self.assertRaisesRegex(ValueError,"shared 200-point timebase"):
            live_inputs(broken)

    def test_abstention_carries_ranked_evidence(self):
        card=self.card|dict(condition_monitor=dict(symptom="DELAYED_PUMP_UNLOADING",late_downstroke_excess_n=1100))
        result=baseline(card)
        self.assertEqual(result["label"],"FAULT_TYPE_UNDETERMINED")
        self.assertEqual(len(result["suspected_causes"]),2)
        self.assertIn("1100 N",result["suspected_causes"][0]["evidence"])

    def test_artifact_fails_production_gate_but_runs_offline(self):
        env={"SRP_MODEL_PATH":str(self.artifact),"SRP_ALLOW_EXPERIMENTAL_MODEL":"0"}
        with patch.dict(os.environ,env):
            registry=Registry()
            self.assertIsNone(registry.artifact)
            self.assertTrue(registry.metadata()["artifact_rejection"])
        with patch.dict(os.environ,env|{"SRP_ALLOW_EXPERIMENTAL_MODEL":"1"}):
            registry=Registry()
            self.assertFalse(gate_passes(registry.metadata()))
            result=registry.predict(self.card)
            self.assertEqual(len(result["candidate_scores"]),3)
            preview=registry.preview(self.card)
            self.assertEqual(len(preview["scores"]),8)
            self.assertAlmostEqual(sum(row["score"] for row in preview["scores"]),1.)
            self.assertIsNone(registry.preview(self.card|{"source":"FIELD"}))
            _,features=live_inputs(self.card)
            artifact=registry.artifact
            p=artifact["estimator"].predict_proba([features]).clip(1e-6)
            expected=artifact["calibrator"].predict_proba(np.log(p))[0]
            self.assertAlmostEqual(result["confidence"],float(expected.max()),places=12)
            self.assertEqual(registry.predict(self.card|{"quality":"BAD"})["label"],"FAULT_TYPE_UNDETERMINED")
            self.assertNotIn("candidate_scores",registry.predict(self.card|{"source":"FIELD"}))


if __name__=="__main__":
    unittest.main(verbosity=2)
