import unittest

from context import ROOT, APM
import numpy as np
from configurations.presets import presets
from evaluate_wave import cycle
from fault_injection.scenarios import Fault
from physics.engine import Engine
from shared.contracts import INCH,LBF,Sample
from stroke_processing.cards import build
from surface_dynacard.geometry import area
from wave_equation.solver import reconstruct,traverse


class PhysicsTests(unittest.TestCase):
    def test_motion_and_stability(self):
        for w in presets():
            e = Engine(w)
            positions = [e.motion.position(x) for x in np.linspace(0,2*np.pi,2049)]
            self.assertAlmostEqual(min(positions),0)
            self.assertAlmostEqual(max(positions),w.stroke_m)
            phase = e.phase
            state = e.advance(60/w.spm)
            self.assertAlmostEqual(e.phase-phase,2*np.pi,places=7)
            self.assertGreater(state["load_n"],0)
            self.assertLess(np.max(np.abs(e.v)),10)
            self.assertTrue(np.isfinite(e.x).all())

    def test_refinement(self):
        well = presets()[0]
        a, b = Engine(well), Engine(well.model_copy(update={"physics_step_s":.001}))
        for _ in range(120):
            x,y = a.advance(.02),b.advance(.02)
            self.assertLess(abs(x["load_n"]-y["load_n"]),500)
            self.assertLess(abs(x["pump_position_m"]-y["pump_position_m"]),.03)

    def test_determinism_and_fault(self):
        w = presets()[0]
        good,samples,_ = cycle(w)
        repeat,_,_ = cycle(w)
        changed,_,_ = cycle(w,Fault(kind="traveling_valve_leak",severity=.9))
        self.assertEqual(good,repeat)
        self.assertEqual(samples[0].physics_model_version,"srp-forward-2.0-plunger-clearance")
        self.assertGreater(abs(good["surface"]["area_j"]-changed["surface"]["area_j"]),50.)
        self.assertEqual(good["surface"]["position_m"][0],samples[0].polished_rod_position_in*INCH)
        self.assertEqual(good["surface"]["load_n"][0],samples[0].polished_rod_load_lbf*LBF)
        self.assertTrue(np.isfinite(good["downhole"]["load_n"]).all())
        with self.assertRaises(ValueError):
            Sample.model_validate(samples[0].model_dump()|{"fault":"healthy"})

    def test_incomplete_fillage_changes_load_transfer(self):
        from fault_detection.monitor import compare_stroke
        well=presets()[0]
        healthy,_,_=cycle(well)
        underfilled,_,_=cycle(well,Fault(kind="incomplete_fillage",severity=.8))
        reference=[dict(healthy,stroke_id=stroke) for stroke in range(3)]
        self.assertEqual(compare_stroke(healthy,reference)["status"],"WITHIN_REFERENCE")
        result=compare_stroke(underfilled,reference)
        self.assertEqual(result["status"],"DYNACARD_CHANGE")
        self.assertEqual(result["symptom"],"DELAYED_PUMP_UNLOADING")

    def test_pump_wear_uses_clearance_path_not_traveling_valve_path(self):
        well=presets()[0]
        engines=[]
        cases=(("healthy",0.),("pump_wear",.8),("traveling_valve_leak",.8),
               ("pump_wear",.1),("pump_wear",1.))
        for kind,severity in cases:
            engine=Engine(well)
            engine.fault=Fault(kind=kind,severity=severity,ramp_s=0,onset_s=engine.time)
            engines.append(engine)
        traces=[[] for _ in engines]
        states=[None for _ in engines]
        for _ in range(150):
            for i,engine in enumerate(engines):
                states[i]=engine.advance(.02)
                traces[i].append(states[i]["load_n"])
        healthy,worn,tv,low_wear,high_wear=states
        self.assertGreater(worn["pump_clearance_m"],healthy["pump_clearance_m"])
        self.assertGreater(worn["plunger_leak_conductance_m3_pa_s"],
                           healthy["plunger_leak_conductance_m3_pa_s"])
        self.assertEqual(tv["pump_clearance_m"],healthy["pump_clearance_m"])
        self.assertGreater(max(abs(a-b) for a,b in zip(traces[1],traces[2])),1.)
        expected_ratio=(high_wear["pump_clearance_m"]/low_wear["pump_clearance_m"])**3
        measured_ratio=(high_wear["plunger_leak_conductance_m3_pa_s"]/
                        low_wear["plunger_leak_conductance_m3_pa_s"])
        self.assertAlmostEqual(measured_ratio,expected_ratio,places=9)

    def test_cards_and_missing_data(self):
        w = presets()[0]
        card,samples,_ = cycle(w)
        dt = samples[1].timestamp-samples[0].timestamp
        last = samples[-1]
        closing = last.model_copy(update=dict(sequence=last.sequence+1,stroke_id=last.stroke_id+1,
                         timestamp=last.timestamp+dt,crank_angle_deg=0.,sample_index=0))
        missing = build(samples[:100]+samples[105:],closing,w)
        self.assertLess(missing["completeness"],1)
        self.assertEqual(missing["quality"],"DEGRADED")
        self.assertEqual(missing["downhole"]["status"],"DOWNHOLE CARD UNAVAILABLE")
        self.assertEqual(build(samples,closing,None)["downhole"]["reason"],"equipment metadata unavailable")
        self.assertTrue(build(samples,closing,w)["identity_consistent"])
        for field,value in (("asset_id","OTHER_WELL"),("run_id","OTHER_RUN"),("stroke_id",999)):
            mixed=list(samples)
            mixed[20]=mixed[20].model_copy(update={field:value})
            rejected=build(mixed,closing,w)
            self.assertFalse(rejected["identity_consistent"])
            self.assertEqual(rejected["downhole"]["status"],"DOWNHOLE CARD UNAVAILABLE")
        wrong_boundary=closing.model_copy(update={"run_id":"OTHER_RUN"})
        self.assertFalse(build(samples,wrong_boundary,w)["identity_consistent"])
        self.assertAlmostEqual(area(np.array([0,1,1,0]),np.array([0,0,1,1])),1)

    def test_static_analytic_reference(self):
        well = presets()[2]
        u,t = traverse(np.array([2.]),np.array([10000.]),np.array([0.]),well.rods,well.damping_s)
        compliance=sum(r.length_m/(r.modulus*np.pi*r.diameter_m**2/4) for r in well.rods)
        self.assertAlmostEqual(u[0].real,2.-10000.*compliance)
        self.assertAlmostEqual(t[0].real,10000.)


if __name__=="__main__":
    unittest.main(verbosity=2)
