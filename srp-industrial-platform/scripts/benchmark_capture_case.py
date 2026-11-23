"""Time one complete synthetic fault stroke to diagnose capture runtimes."""
import copy
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/srp-simulator"), str(ROOT / "apps/srp-apm")]
from fault_injection.scenarios import Fault
from physics.engine import Engine
from shared.contracts import Well
from stroke_processing.cards import build
from virtual_sensors.sampling import Sensors


def main():
    fleet = json.loads((ROOT / "config/fleet/us_srp_30_wells.json").read_text())["wells"]
    entry = fleet[0]
    well = Well.model_validate(entry["well"])
    start = time.perf_counter()
    baseline = Engine(well)
    warmup_s = time.perf_counter() - start
    engine = copy.deepcopy(baseline)
    severity = .8
    engine.fault = Fault(kind="incomplete_fillage", severity=severity, ramp_s=0,
                         onset_s=engine.time, duration_s=1e6)
    samples_needed = math.ceil(well.dynamometer_hz * 60 / well.spm) + 2
    sensors = Sensors(engine, "capture-case-benchmark", datetime.now(timezone.utc))
    sensors.site_id = entry["site_id"]
    previous = []
    emitted = 0
    stepping_start = time.perf_counter()
    card_seconds = []
    built = []
    while emitted < samples_needed:
        state = engine.advance(1 / well.dynamometer_hz)
        sample, boundary = sensors.read(state)
        if sample is not None:
            previous.append(sample)
            emitted += 1
        if boundary and previous and sample is not None:
            if previous[0].sample_index == 0:
                solve_start = time.perf_counter()
                card = build(previous[:-1], sample, well)
                card_seconds.append(time.perf_counter() - solve_start)
                if card:
                    built.append({"quality": card["quality"], "sample_count": card["sample_count"],
                                  "downhole_status": card["downhole"]["status"]})
            previous = [sample]
    step_seconds = time.perf_counter() - stepping_start
    print(json.dumps({"asset": well.asset_id, "fault": "incomplete_fillage", "severity": severity,
                      "warmup_seconds": warmup_s, "telemetry_rows": emitted,
                      "stepping_seconds_including_card_build": step_seconds,
                      "card_build_seconds": card_seconds, "cards": built}, indent=2), flush=True)


if __name__ == "__main__":
    main()
