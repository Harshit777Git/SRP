from datetime import datetime, timedelta, timezone
import math

import numpy as np

from shared.contracts import INCH, LBF, Sample


class Sensors:
    def __init__(self, engine, run_id, epoch=None):
        self.engine = engine
        self.run_id = run_id
        self.epoch = epoch or datetime.now(timezone.utc)
        self.start_time = engine.time
        self.rng = np.random.default_rng(engine.well.seed)
        self.sequence = 0
        self.stroke_id = -1
        self.index = 0
        self.site_id = None

    def read(self, state):
        e, w = self.engine, self.engine.well
        stroke = int(e.phase/math.tau)
        new_stroke = stroke != self.stroke_id
        if new_stroke:
            self.stroke_id, self.index = stroke, 0
        drift = e.fault.at(e.time, "load_cell_drift")
        encoder = e.fault.at(e.time, "position_sensor_fault")
        sample = Sample(asset_id=w.asset_id, site_id=self.site_id, source="SIMULATOR", run_id=self.run_id,
                        physics_model_version=state.get("physics_model_version"),
                        timestamp=self.epoch+timedelta(seconds=e.time-self.start_time),
                        sequence=self.sequence, stroke_id=stroke, sample_index=self.index,
                        polished_rod_position_in=(state["position_m"]*(1-.45*encoder)
                            +w.position_bias_m+self.rng.normal(0, w.noise_position_m))/INCH,
                        polished_rod_load_lbf=(state["load_n"]+3000*drift
                            +w.load_bias_n+self.rng.normal(0, w.noise_load_n))/LBF,
                        crank_angle_deg=state["crank_angle_deg"], spm=state["spm"], quality="GOOD")
        self.sequence += 1
        self.index += 1
        return (None if self.rng.random() < w.missing_probability else sample), new_stroke
