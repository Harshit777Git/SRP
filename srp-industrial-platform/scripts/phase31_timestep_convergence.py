"""Compare fleet numerical step sizes at fixed 50 Hz sensor cadence."""
import json
import argparse
import math
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"apps/srp-simulator")]
from physics.engine import Engine
from shared.contracts import Well


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=30)
    args=parser.parse_args()
    entries=json.loads((ROOT/"config/fleet/us_srp_30_wells.json").read_text())["wells"]
    entries=entries[:args.limit]
    results=[]
    for entry in entries:
        base=Well.model_validate(entry["well"])
        candidates=[base.model_copy(update={"physics_step_s":step}) for step in (.001,.002,.004,.0067)]
        engines=[Engine(well) for well in candidates]
        count=round(60/base.spm*base.dynamometer_hz)
        traces=[]
        for engine in engines:
            traces.append([engine.advance(1/base.dynamometer_hz) for _ in range(count)])
        def measure(a,b):
            af=np.array([s["load_n"] for s in traces[a]]);bf=np.array([s["load_n"] for s in traces[b]])
            ax=np.array([s["pump_position_m"] for s in traces[a]]);bx=np.array([s["pump_position_m"] for s in traces[b]])
            return dict(load_rmse_n=float(np.sqrt(np.mean((af-bf)**2))),
                        load_rmse_range_fraction=float(np.sqrt(np.mean((af-bf)**2))/max(1,np.ptp(af))),
                        pump_position_rmse_m=float(np.sqrt(np.mean((ax-bx)**2))),
                        pump_position_rmse_stroke_fraction=float(np.sqrt(np.mean((ax-bx)**2))/base.stroke_m))
        results.append(dict(asset_id=base.asset_id, site_id=entry["site_id"],
                            reference_001_vs_002=measure(0,1), candidate_002_vs_004=measure(1,2),
                            candidate_002_vs_0067=measure(1,3)))
        print(base.asset_id,results[-1]["candidate_002_vs_0067"]["load_rmse_range_fraction"],flush=True)
    target=ROOT/"reports/PHASE3_1/physics_timestep_convergence.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(results,indent=2))
    print(target)


if __name__=="__main__":main()
