import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT/"apps/srp-simulator"
APM = ROOT/"apps/srp-apm"
sys.path[:0] = [str(ROOT),str(SIM),str(APM)]
