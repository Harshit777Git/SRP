"""Matched synthetic card distances; descriptive physics study, never ML labels."""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT), str(ROOT / "apps/srp-simulator"), str(ROOT / "apps/srp-apm")]
from evaluate_wave import cycle
from fault_injection.scenarios import Fault
from shared.contracts import Well

KINDS = ["healthy", "incomplete_fillage", "restricted_inflow", "gas_interference",
         "standing_valve_leak", "traveling_valve_leak", "pump_wear", "rod_friction"]


def signature(card, key):
    data = card[key]
    x = np.asarray(data["position_m"])
    f = np.asarray(data["load_n"])
    phase = np.linspace(0, 1, len(f), endpoint=False)
    grid = np.linspace(0, 1, 200, endpoint=False)
    return np.interp(grid, phase, f, period=1), np.interp(grid, phase, x, period=1)


def main():
    well = Well.model_validate(json.loads((ROOT / "config/fleet/us_srp_30_wells.json").read_text())["wells"][0]["well"])
    cards = {}
    for kind in KINDS:
        fault = Fault(kind=kind, severity=.8, ramp_s=0) if kind != "healthy" else None
        cards[kind], _, _ = cycle(well, fault, run_id=f"observability-{kind}")
        print(kind, flush=True)
    rows = []
    for first in KINDS:
        for second in KINDS:
            sf, sx = signature(cards[first], "surface")
            tf, tx = signature(cards[second], "surface")
            df, dx = signature(cards[first], "downhole")
            ef, ex = signature(cards[second], "downhole")
            rows.append(dict(well_id=well.asset_id, severity=0.8, first=first, second=second,
                surface_load_rmse_n=float(np.sqrt(np.mean((sf-tf)**2))),
                surface_position_rmse_m=float(np.sqrt(np.mean((sx-tx)**2))),
                downhole_load_rmse_n=float(np.sqrt(np.mean((df-ef)**2))),
                downhole_position_rmse_m=float(np.sqrt(np.mean((dx-ex)**2))),
                same_configuration=True, independent_reference=False))
    path = ROOT / "reports/FAULT_OBSERVABILITY_MATRIX.csv"
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "reports/PHASE3/fault_observability.json").write_text(json.dumps(rows, indent=2))
    print(path)


if __name__ == "__main__":
    main()
