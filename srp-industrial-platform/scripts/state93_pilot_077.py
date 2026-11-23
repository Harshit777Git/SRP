"""Run the existing APM inverse solver on verified STATE-077 point exports."""
import csv
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps" / "srp-apm"), str(ROOT)]
from shared.contracts import Rod, Well, INCH, LBF  # noqa: E402
from wave_equation.solver import reconstruct  # noqa: E402
from backend.interchange import import_file  # noqa: E402

SOURCE = Path(r"C:\Users\HARSHIT\Downloads")
OUT = ROOT / "data" / "STATE93" / "pilot" / "Tagging Down Hard"


def filehash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def area(x, y):
    return float(abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2))


def main():
    txt = SOURCE / "TATE-077_Tagging_Down_Hard_Card_Data.txt"
    dyn = SOURCE / "Tagging Down Hard_DYN_4294967295_03-13-2003_02-09-20.dyn"
    pdf = SOURCE / "Tagging Down Hard_Summary.pdf"
    originals = OUT / "original" / "user_exports"
    originals.mkdir(parents=True, exist_ok=True)
    for p in (txt, dyn, pdf):
        target = originals / p.name
        if not target.exists():
            shutil.copy2(p, target)
    lines = txt.read_text(encoding="utf-8-sig").splitlines()
    raw = np.array([[float(x) for x in line.split()] for line in lines[1:] if line.strip()])
    if raw.shape != (174, 4):
        raise ValueError(f"Expected 174 x 4 numeric text export, got {raw.shape}")
    dynlines = dyn.read_text(encoding="utf-8-sig").splitlines()
    count = int(dynlines[0].strip())
    dynpoints = np.array([[float(v) for v in line.split(",")] for line in dynlines[1:count+1]])
    if count != 174 or dynpoints.shape != (174, 2):
        raise ValueError("DYN file point block mismatch")
    if np.max(abs(dynpoints[:, 0] - raw[:, 0])) > 1e-5 or np.max(abs(dynpoints[:, 1] - raw[:, 1] * 1000)) > .01:
        raise ValueError("Surface TXT and DYN point blocks differ")
    # PDF page 4: three D rods, 1552 ft x 1 in, 2750 ft x .875 in,
    # 200 ft x 1 in. The remaining 61 ft to pump intake is not specified.
    rods = [Rod(length_m=feet * .3048, diameter_m=diameter * INCH)
            for feet, diameter in ((1552, 1), (2750, .875), (200, 1))]
    # Production-weighted liquid density is an explicit approximation.
    oil_sg = 141.5 / (29.0 + 131.5)
    liquid_sg = (60 * oil_sg + 300 * 1.010) / 360
    tam = json.loads((OUT / "vendor_exports" / "TAM" / "test_results_summary.json").read_text())
    candidate = [t for t in tam["test_summaries"] if t["type"] == "DYN" and t["datetime"] == "2003-03-12T20:39:20Z"]
    if len(candidate) != 1:
        raise ValueError("Expected unique matching TAM DYN summary")
    spm = candidate[0]["numeric_fields"]["Strokes Per Minute"]
    well = Well(asset_id="STATE077", rods=rods, stroke_m=144 * INCH, spm=spm,
                plunger_m=1.75 * INCH, fluid_kg_m3=liquid_sg * 1000,
                damping_s=.6)
    result = reconstruct(raw[:, 0] * INCH, raw[:, 1] * 1000 * LBF, 60 / spm, well)
    pred_x = np.asarray(result["position_m"]) / INCH
    pred_y = np.asarray(result["load_n"]) / (1000 * LBF)
    vendor_x, vendor_y = raw[:, 2], raw[:, 3]
    shifts = [(i, math.sqrt(float(np.mean((np.roll(pred_x, i)-vendor_x)**2 + (np.roll(pred_y, i)-vendor_y)**2)))) for i in range(174)]
    shift = min(shifts, key=lambda v: v[1])[0]
    aligned_x, aligned_y = np.roll(pred_x, shift), np.roll(pred_y, shift)
    metrics = {"sample_count": 174, "solver_status": result["status"],
               "solver_version": result["solver_version"], "spm": spm,
               "load_rmse_klbf_index_aligned": float(np.sqrt(np.mean((pred_y-vendor_y)**2))),
               "position_rmse_in_index_aligned": float(np.sqrt(np.mean((pred_x-vendor_x)**2))),
               "diagnostic_best_circular_shift_samples": shift,
               "load_rmse_klbf_shifted": float(np.sqrt(np.mean((aligned_y-vendor_y)**2))),
               "position_rmse_in_shifted": float(np.sqrt(np.mean((aligned_x-vendor_x)**2))),
               "surface_stroke_in": float(np.ptp(raw[:, 0])),
               "apm_downhole_stroke_in": float(np.ptp(pred_x)),
               "tam_pump_stroke_in": float(np.ptp(vendor_x)),
               "stroke_length_error_in": float(np.ptp(pred_x)-np.ptp(vendor_x)),
               "apm_card_area_klbf_in": area(pred_x, pred_y),
               "tam_card_area_klbf_in": area(vendor_x, vendor_y)}
    metrics["card_area_error_percent"] = 100 * (metrics["apm_card_area_klbf_in"]-metrics["tam_card_area_klbf_in"]) / metrics["tam_card_area_klbf_in"]
    normalized = OUT / "normalized"
    normalized.mkdir(exist_ok=True)
    for filename, x, y, status in (("surface_dynacard.csv", raw[:, 0], raw[:, 1] * 1000, "MEASURED_ORIGIN_UNVERIFIED"),
                                   ("vendor_downhole_dynacard.csv", vendor_x, vendor_y * 1000, "VENDOR_CALCULATED"),
                                   ("apm_downhole_dynacard.csv", pred_x, pred_y * 1000, "APM_CALCULATED")):
        with (normalized / filename).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["well_id", "stroke_id", "sample_index", "position_in", "load_lbf", "source_status"])
            for i, (a, b) in enumerate(zip(x, y)):
                w.writerow(["STATE077", 1, i, float(a), float(b), status])
    assumptions = {"fluid_density_kg_m3": liquid_sg * 1000,
                   "fluid_density_method": "60 BPD oil at 29 API plus 300 BPD water at SG 1.010; production-weighted approximation",
                   "rod_density_kg_m3": 7850, "rod_modulus_pa": 205e9,
                   "damping_s": .6, "damping_note": "APM model assumption; TAM's 0.1 damping factor has different/unknown units",
                   "uniform_sample_timebase": "assumed; source points have order but no per-point times",
                   "rod_depth_gap_ft": 61, "rod_depth_gap_note": "4502-ft listed rod taper versus 4563-ft intake depth",
                   "pressure_boundary": "not used by inverse solver; omitted",
                   "matched_test_identity": "inferred from DYN filename local time versus TAM UTC timestamp; not independently confirmed in GUI"}
    (normalized / "engineering_config.json").write_text(json.dumps({"verified_pdf": {"pump_intake_depth_ft":4563,"rod_sections_ft_diameter_in":[[1552,1],[2750,.875],[200,1]],"surface_unit":"Lufkin C-640D-356-144","stroke_in":144,"plunger_diameter_in":1.75},"assumptions":assumptions,"apm_well":well.model_dump()},indent=2),encoding="utf-8")
    (OUT / "validation" / "numerical_comparison.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    (OUT / "apm" / "analysis_results.json").write_text(json.dumps({"solver":result,"comparison":metrics},indent=2),encoding="utf-8")
    (OUT / "apm" / "import_manifest.json").write_text(json.dumps({"state":"STATE-077","source_files":{p.name:filehash(p) for p in (txt,dyn,pdf)},"surface_points":174,"vendor_pump_points":174,"apm_solver_status":result["status"],"apm_database_import":"NOT_RUN","note":"Numerical APM solver executed directly; application database and UI import not verified"},indent=2),encoding="utf-8")
    imported = import_file({"kind":"surface","filename":dyn.name,"content":dyn.read_text(),
                            "well_id":"STATE077","stroke_id":"1","provenance":"Echometer DYN user export"})
    if imported["records"] != 174 or len(imported["cards"]) != 1:
        raise ValueError("APM DYN adapter did not retain one 174-point card")
    reimported = import_file({"kind":"surface","filename":"surface_dynacard.csv",
                              "content":(normalized / "surface_dynacard.csv").read_text(),
                              "well_id":"STATE077","stroke_id":"1",
                              "provenance":"STATE077 normalized CSV"})
    if reimported["records"] != 174 or len(reimported["cards"]) != 1:
        raise ValueError("APM CSV adapter did not retain one 174-point card")
    numeric_difference = float(max(np.max(abs(np.asarray(imported["cards"][0][key])-np.asarray(reimported["cards"][0][key]))) for key in ("position_m","load_n")))
    # The DYN load values are printed to 0.01 lbf, while the TXT carries
    # six-decimal k-lbf values; their maximum expected rounding gap is ~0.03 N.
    if numeric_difference > .05:
        raise ValueError(f"DYN/CSV reimport numeric difference {numeric_difference}")
    (OUT / "apm" / "offline_import_results.json").write_text(json.dumps({
        "adapter":"backend.interchange.import_file", "source_records":imported["records"],
        "cards":len(imported["cards"]),"dataset_id":imported["dataset_id"],
        "quality":imported["cards"][0]["quality"],
        "warnings":imported["cards"][0]["warnings"],
        "csv_reimport_records":reimported["records"],
        "dyn_csv_max_si_difference":numeric_difference,
        "database_import":"NOT_RUN"},indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2))


if __name__ == "__main__":
    main()
