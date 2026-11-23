"""Produce conservative Phase 4 acceptance and scale-out status artifacts."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "STATE93"
PILOT = ROOT / "data" / "STATE93" / "pilot" / "STATE-077"


def main():
    imported=json.loads((REPORT/"STATE077_IMPORT_VALIDATION.json").read_text())
    status = {"asset_id":"STATE-077", "source":"Browser check of local APM on 2026-11-18",
              "reference_view_loaded":True, "stored_version_displayed":imported["version"],
              "database_version_current":imported["version"],
              "browser_version_matches_current_database":True,
              "sample_count_displayed":174,
              "scrub_test":{"from":0,"to":87,"surface_sample_displayed":88,
                            "downhole_sample_displayed":88,"plunger_position_changed":True},
              "play_test":{"cursor_advanced":True,"pause_control_appeared":True,
                           "pause_returned_to_play":True},
              "vendor_overlay_default_on":True,"vendor_overlay_toggle_tested":True,
              "vendor_overlay_plot_counts":{"on":2,"off":1,"restored":2},
              "csv_export_browser_tested":True,"csv_export_rows_including_header":175,
              "csv_export_path":"C:\\Users\\HARSHIT\\Downloads\\STATE-077-comparison.csv",
              "png_export_tested":False,"pdf_export_tested":False,
              "timing_status":"ESTIMATED_FROM_SPM", "valve_and_fillage_status":"UNAVAILABLE",
              "screenshot_saved":False}
    (REPORT/"STATE077_ANIMATION_ACCEPTANCE.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    matrix=list(csv.DictReader((REPORT/"93_STATE_COMPATIBILITY_MATRIX.csv").open(encoding="utf-8-sig")))
    rows=[]
    for r in matrix:
        if r["State ID"] == "STATE-077":continue
        state_dir=Path(r["Standard Directory"])
        files=[p for p in state_dir.rglob("*") if p.is_file()] if state_dir.is_dir() else []
        numerical=[p for p in files if p.suffix.lower() in (".txt",".dyn")]
        summaries=[p for p in files if p.suffix.lower()==".pdf"]
        configs=[p for p in files if p.name.lower() in ("engineering_config.json","engineering_configuration.json")]
        rows.append({"State ID":r["State ID"],"State":r["Original State Name"],
                     "Numerical card available":"EXPORT_PRESENT_UNVERIFIED" if numerical else "NO_VERIFIED_EXPORT",
                     "Vendor export required":"REVIEW_PRESENT_EXPORT" if numerical else "YES",
                     "Engineering configuration available":"PRESENT_UNVERIFIED" if configs else "UNVERIFIED",
                     "Rod-string parameters":"UNVERIFIED",
                     "Ready for APM import":"NO",
                     "Ready for downhole reconstruction":"NO",
                     "Vendor comparison available":"NO_VERIFIED_NUMERICAL_CARD",
                     "QRod configuration possible":"UNVERIFIED",
                     "ML research eligibility":"NO_VERIFIED_LABELS_OR_PERMISSION",
                     "Numerical export paths":"; ".join(str(p) for p in numerical),
                     "Summary PDF paths":"; ".join(str(p) for p in summaries),
                     "Reviewed configuration paths":"; ".join(str(p) for p in configs),
                     "Original Directory":r["Original Directory"],
                     "Standard Directory":r["Standard Directory"]})
    with (REPORT/"STATE93_SCALEOUT_READINESS.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
    (REPORT/"STATE077_QROD_STATUS.md").write_text("""# STATE-077 QRod status

QRod 3.1 opened and its design-input screen was inspected. No native design was saved or reopened. The source PDF identifies a Lufkin C-640D-356-144 conventional unit, 144-in stroke, 4563-ft pump intake, three API D rod sections totaling 4502 ft, 1.75-in plunger, tubing dimensions and reported fluid properties. The 61-ft rod-to-pump-depth gap is unexplained. Pump intake pressure/working fluid level and QRod-specific design assumptions are not verified for the DYN test. A native design made now would be assumption-based, not matched. Status: BLOCKED_MISSING_VERIFIED_INPUTS.\n""",encoding="utf-8")
    print("scale-out states",len(rows))


if __name__ == "__main__":main()
