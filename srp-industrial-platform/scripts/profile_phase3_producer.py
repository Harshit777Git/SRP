import cProfile
import io
import json
import pstats
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"apps/srp-simulator")]
from backend.server import Run
from shared.contracts import Well

class Sink:
    def append(self,messages,delay_s=0):pass

well=Well.model_validate(json.loads((ROOT/"config/fleet/us_srp_30_wells.json").read_text())["wells"][0]["well"])
run=Run(well,1,ROOT/"data/evaluation/phase3")
profile=cProfile.Profile()
stream=io.StringIO();sink=Sink()
profile.enable()
for _ in range(1000):run.sample(sink,stream)
profile.disable()
report=io.StringIO();pstats.Stats(profile,stream=report).sort_stats("cumulative").print_stats(20)
print(report.getvalue())
