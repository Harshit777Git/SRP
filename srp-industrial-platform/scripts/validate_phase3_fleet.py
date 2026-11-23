"""Offline synthetic self-consistency study; no external engineering validation."""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT), str(ROOT / "apps/srp-simulator"), str(ROOT / "apps/srp-apm")]
from evaluate_wave import cycle, compare
from shared.contracts import Well


def main():
    fleet = json.loads((ROOT / "config/fleet/us_srp_30_wells.json").read_text())["wells"]
    output = ROOT / "data/evaluation/phase3"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in fleet:
        well = Well.model_validate(entry["well"])
        try:
            card, samples, truth = cycle(well, run_id=f"phase3-{well.asset_id}")
            metrics = compare(card, truth)
            surface = card["surface"]
            downhole = card["downhole"]
            result = dict(site_id=entry["site_id"], asset_id=well.asset_id,
                          status="SYNTHETIC_VALIDATED" if card["quality"] == "GOOD" else "INVALID",
                          sample_count=len(samples), surface_card_count=1,
                          downhole_card_count=int(downhole["status"] == "SOLVED"),
                          surface_load_min_n=float(min(surface["load_n"])),
                          surface_load_max_n=float(max(surface["load_n"])),
                          surface_stroke_m=float(np.ptp(surface["position_m"])), **metrics)
            if not all(math.isfinite(v) for v in metrics.values()):
                result["status"] = "INVALID"
            (output / f"{well.asset_id}.sensor.jsonl").write_text(
                "\n".join(s.model_dump_json() for s in samples) + "\n")
            (output / f"{well.asset_id}.truth.json").write_text(json.dumps(truth))
            (output / f"{well.asset_id}.cards.json").write_text(json.dumps(card))
        except Exception as exc:
            result = dict(site_id=entry["site_id"], asset_id=well.asset_id,
                          status="INVALID", error=str(exc), sample_count=0,
                          surface_card_count=0, downhole_card_count=0)
        rows.append(result)
        print(result["asset_id"], result["status"], flush=True)
    (output / "validation.json").write_text(json.dumps(dict(origin="SYNTHETIC",
        independent_reference=False, cases=rows), indent=2))
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (ROOT / "reports/PHASE3/SIMULATION_PHYSICS_VALIDATION.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(wells=len(rows), valid=sum(r["status"] == "SYNTHETIC_VALIDATED" for r in rows),
                          surface_cards=sum(r["surface_card_count"] for r in rows),
                          downhole_cards=sum(r["downhole_card_count"] for r in rows))))


if __name__ == "__main__":
    (ROOT / "reports/PHASE3").mkdir(parents=True, exist_ok=True)
    main()
