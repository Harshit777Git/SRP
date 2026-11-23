"""Reproduce baseline and bounded one-factor sensitivity without calibration."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps" / "srp-apm"), str(ROOT)]
from shared.contracts import INCH, LBF, Well  # noqa: E402
from wave_equation.solver import reconstruct  # noqa: E402

PILOT = ROOT / "data" / "STATE93" / "pilot" / "Tagging Down Hard"
OUT = ROOT / "data" / "STATE93" / "pilot" / "STATE-077"
REPORT = ROOT / "reports" / "STATE93"


def load(name):
    rows = list(csv.DictReader((PILOT / "normalized" / name).open(encoding="utf-8")))
    return np.array([float(row["position_in"]) for row in rows]), np.array([float(row["load_lbf"]) for row in rows])


def area(x, y):
    return float(abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2))


def main():
    config = json.loads((PILOT / "normalized" / "engineering_config.json").read_text())
    base = Well.model_validate(config["apm_well"] | {"asset_id": "STATE-077"})
    sx, sy = load("surface_dynacard.csv")
    tx, ty = load("vendor_downhole_dynacard.csv")
    if len(sx) != len(tx) or len(sx) != 174:
        raise ValueError("Expected paired 174-point cards")
    period = 60 / base.spm
    variants = [
        ("baseline", "none", None, "Existing APM baseline"),
        ("modulus_low", "rod_modulus_pa", 190e9, "Steel range sensitivity, not calibration"),
        ("modulus_high", "rod_modulus_pa", 215e9, "Steel range sensitivity, not calibration"),
        ("density_low", "rod_density_kg_m3", 7750, "Steel density sensitivity"),
        ("density_high", "rod_density_kg_m3", 7950, "Steel density sensitivity"),
        ("damping_low", "damping_s", .3, "Model parameter sensitivity"),
        ("damping_high", "damping_s", 1.2, "Model parameter sensitivity"),
        ("liquid_density_low", "fluid_kg_m3", 900, "Unmeasured mixture sensitivity"),
        ("liquid_density_high", "fluid_kg_m3", 1050, "Unmeasured mixture sensitivity"),
        ("rod_gap_hypothesis", "last_rod_extra_ft", 61, "Hypothetical 61-ft assembly; not a source fact"),
        ("spm_low", "spm", base.spm*.98, "Estimated timebase sensitivity"),
        ("spm_high", "spm", base.spm*1.02, "Estimated timebase sensitivity"),
    ]
    rows = []
    for label, parameter, value, note in variants:
        well = base.model_copy(deep=True)
        if parameter == "rod_modulus_pa":
            for rod in well.rods:rod.modulus = value
        elif parameter == "rod_density_kg_m3":
            for rod in well.rods:rod.density = value
        elif parameter == "last_rod_extra_ft":
            well.rods[-1].length_m += value * .3048
        elif parameter != "none":
            setattr(well, parameter, value)
        try:
            predicted = reconstruct(sx*INCH, sy*LBF, 60/well.spm, well)
            x = np.asarray(predicted["position_m"])/INCH
            y = np.asarray(predicted["load_n"])/LBF
            rows.append({"variant":label,"parameter":parameter,"value":value or "", "note":note,
                         "status":"SOLVED","load_rmse_lbf":float(np.sqrt(np.mean((y-ty)**2))),
                         "displacement_rmse_in":float(np.sqrt(np.mean((x-tx)**2))),
                         "card_area_error_percent":100*(area(x,y)-area(tx,ty))/area(tx,ty)})
        except ValueError as exc:
            rows.append({"variant":label,"parameter":parameter,"value":value or "", "note":note,
                         "status":str(exc),"load_rmse_lbf":"","displacement_rmse_in":"","card_area_error_percent":""})
    if abs(rows[0]["load_rmse_lbf"]-627.3106625247694) > .001:
        raise ValueError("Baseline drifted")
    OUT.mkdir(parents=True, exist_ok=True)
    for source, target in (("apm_downhole_dynacard.csv","apm_reconstructed_card.csv"),
                           ("vendor_downhole_dynacard.csv","vendor_reference_card.csv")):
        (OUT/target).write_bytes((PILOT/"normalized"/source).read_bytes())
    (OUT/"engineering_configuration.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    originals = PILOT/"original"/"user_exports"
    manifest = {"state_id":"STATE-077","version":"phase4-1","source_files":[],
                "units":{"surface":"in,lbf","vendor_pump":"in,lbf","apm_pump":"in,lbf"},
                "timebase":"ORDERED_POINTS; uniform sample timing estimated from 10.384282394 SPM",
                "test_identity":"Tagging Down Hard DYN 03-13-2003 02:09:20 local; UTC correspondence inferred"}
    for p in sorted(originals.iterdir()):
        manifest["source_files"].append({"path":str(p.resolve()),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size})
    (OUT/"source_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    REPORT.mkdir(exist_ok=True)
    with (REPORT/"STATE077_PARAMETER_SENSITIVITY.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
    m=json.loads((REPORT/"STATE077_IMPORT_VALIDATION.json").read_text())["metrics"]
    with (REPORT/"STATE077_SOLVER_COMPARISON.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["metric","value"]);w.writerows(m.items())
    print(json.dumps({"variants":len(rows),"solved":sum(r["status"]=="SOLVED" for r in rows),
                      "baseline_load_rmse_lbf":rows[0]["load_rmse_lbf"]},indent=2))


if __name__ == "__main__":
    main()
