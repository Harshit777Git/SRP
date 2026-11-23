"""Measure the revised pump-wear model against other scenarios on synthetic cards.

This is a simulator mechanism pilot, not a field-accuracy evaluation.
"""
import json
from pathlib import Path

import numpy as np

from context import ROOT
from configurations.presets import presets
from evaluate_wave import cycle
from fault_injection.scenarios import Fault
from surface_dynacard.geometry import area


def phase_load(samples, bins=144):
    angle = np.asarray([s.crank_angle_deg for s in samples], dtype=float)
    load = np.asarray([s.polished_rod_load_lbf for s in samples], dtype=float)*4.4482216152605
    order = np.argsort(angle)
    angle, load = angle[order], load[order]
    angle, unique = np.unique(angle, return_index=True)
    load = load[unique]
    target = np.arange(bins, dtype=float)*360/bins
    angle_ext = np.r_[angle[-1]-360, angle, angle[0]+360]
    load_ext = np.r_[load[-1], load, load[0]]
    return np.interp(target, angle_ext, load_ext)


def measure(kind, well, severity=.8):
    fault = None if kind == "healthy" else Fault(kind=kind, severity=severity, ramp_s=0)
    card, samples, _ = cycle(well, fault)
    x = np.asarray(card["surface"]["position_m"], dtype=float)
    f = np.asarray(card["surface"]["load_n"], dtype=float)
    return {
        "card": card,
        "wave": phase_load(samples),
        "metrics": {
            "samples": len(samples),
            "stroke_length_m": float(np.ptp(x)),
            "minimum_load_n": float(np.min(f)),
            "maximum_load_n": float(np.max(f)),
            "card_area_j": float(area(x, f)),
        },
    }


def main():
    well = presets()[0]
    healthy = measure("healthy", well)
    measured = {kind: measure(kind, well, .8) for kind in (
        "pump_wear", "traveling_valve_leak", "standing_valve_leak")}
    measured["healthy"] = healthy
    reference = healthy["wave"]
    baseline_range = max(1., float(np.ptp(reference)))
    results = {}
    for kind, entry in measured.items():
        metrics = entry["metrics"]
        results[kind] = {
            **metrics,
            "load_curve_rmse_vs_healthy_n": float(np.sqrt(np.mean((entry["wave"]-reference)**2))),
            "load_curve_rmse_vs_healthy_fraction_of_range": float(
                np.sqrt(np.mean((entry["wave"]-reference)**2))/baseline_range),
            "card_area_delta_vs_healthy_j": float(metrics["card_area_j"]-measured["healthy"]["metrics"]["card_area_j"]),
        }
    wear_sweep = []
    for severity in np.arange(.1, 1.01, .1):
        entry = measure("pump_wear", well, float(severity))
        load_rmse = float(np.sqrt(np.mean((entry["wave"]-reference)**2)))
        wear_sweep.append({
            "severity": round(float(severity), 1),
            "effective_radial_clearance_m": float(
                well.plunger_radial_clearance_m+well.pump_wear_clearance_growth_m*severity),
            "load_curve_rmse_vs_healthy_n": load_rmse,
            "load_curve_rmse_vs_healthy_fraction_of_range": load_rmse/baseline_range,
            "card_area_j": entry["metrics"]["card_area_j"],
        })
    payload = {
        "status": "SYNTHETIC_MECHANISM_PILOT_ONLY",
        "physics_change": "pump wear uses annular plunger/barrel clearance leakage; traveling-valve leakage remains a separate valve path",
        "well_configuration": well.model_dump(mode="json"),
        "comparison_fault_severity": 0.8,
        "pump_wear_severity_sweep": wear_sweep,
        "sampling_rate_hz": well.dynamometer_hz,
        "phase_alignment": "surface loads interpolated onto 144 crank-angle bins for relative within-simulator comparison",
        "results": results,
        "limitations": [
            "No field data or pump inspection clearance is available; defaults are illustrative.",
            "The pilot shows simulator output separation only, not diagnostic accuracy or physical validation.",
            "The annular flow model omits Couette flow, eccentricity, non-Newtonian fluids and transient effects.",
        ],
    }
    output = ROOT/"reports/PHASE3_2/PUMP_WEAR_PHYSICS_PILOT.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "results": results}, indent=2))


if __name__ == "__main__":
    main()
