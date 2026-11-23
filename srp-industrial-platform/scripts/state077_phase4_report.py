"""Build the evidence based STATE-077 Phase 4 engineering report."""
import csv
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports" / "STATE93"
P = ROOT / "data" / "STATE93" / "pilot" / "STATE-077"
OUT = R / "STATE077_PHASE4_ENGINEERING_REPORT.pdf"


def main():
    imp = json.loads((R / "STATE077_IMPORT_VALIDATION.json").read_text())
    anim = json.loads((R / "STATE077_ANIMATION_ACCEPTANCE.json").read_text())
    manifest = json.loads((P / "source_manifest.json").read_text())
    sensitivity = list(csv.DictReader((R / "STATE077_PARAMETER_SENSITIVITY.csv").open(encoding="utf-8-sig")))
    scaleout = list(csv.DictReader((R / "STATE93_SCALEOUT_READINESS.csv").open(encoding="utf-8-sig")))
    m = imp["metrics"]
    styles = getSampleStyleSheet()
    story = []

    def para(s, style="Normal"):
        story.append(Paragraph(s, styles[style])); story.append(Spacer(1, 3*mm))

    def table(rows, widths=None):
        t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,0), colors.HexColor("#17324d")),
            ("TEXTCOLOR", (0,0),(-1,0), colors.white),
            ("GRID", (0,0),(-1,-1), .3, colors.HexColor("#c4ccd4")),
            ("VALIGN", (0,0),(-1,-1), "TOP"),
            ("FONTSIZE", (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("TOPPADDING", (0,0),(-1,-1), 5),
        ]))
        story.append(t); story.append(Spacer(1, 5*mm))

    para("STATE-077 Phase 4 Engineering Benchmark", "Title")
    para("Tagging Down Hard | historical Echometer reference | 18 November 2026", "Heading2")
    para("Decision: CONDITIONAL GO for the single-state historical reference and comparison workflow. NO-GO for a matched QRod design or 93-state scaleout until missing engineering inputs and vendor numerical exports are supplied.")
    para("Scope and provenance", "Heading2")
    para("Three vendor-original files were preserved byte-for-byte. Their paths, SHA-256 checksums and sizes are in the accompanying source_manifest.json. The DYN test timestamp is 13 March 2003 02:09:20 local; UTC correspondence is inferred. Surface and TAM pump cards each contain 174 ordered load-position samples in inches and lbf. Sample timing is estimated from 10.384282394 SPM; it was not measured per sample.")
    table([["Artifact", "Status"], ["APM historical reference", "Persisted and re-read in isolated state/state93/apm.db"], ["Reference version", imp["version"]], ["Idempotent reimport", "Passed; no duplicate version row"], ["Point counts", "174 surface / 174 TAM pump / 174 APM pump"], ["Original source checksums", f"{len(manifest['source_files'])} recorded"]], [60*mm, 118*mm])
    para("Inverse wave-equation comparison", "Heading2")
    para("The existing harmonic-transfer/1.0 inverse solver reconstructed the downhole card from the surface card and the recorded engineering configuration. TAM's exported Pump Card was used as an external reference, not as solver input. Arrays were compared at their original ordered sample indices; the diagnostic best circular shift was zero samples.")
    table([["Metric", "Baseline"], ["Load RMSE", f"{m['load_rmse_lbf']:.2f} lbf"], ["Load MAE", f"{m['load_mae_lbf']:.2f} lbf"], ["Displacement RMSE", f"{m['displacement_rmse_in']:.3f} in"], ["Stroke length difference", f"{m['stroke_length_error_in']:+.3f} in"], ["Signed card-area error", f"{m['card_area_error_percent']:+.2f}%"], ["Load correlation", f"{m['load_correlation']:.4f}"], ["Phase alignment", "0-sample diagnostic circular shift"]], [70*mm, 108*mm])
    para("Bounded parameter sensitivity", "Heading2")
    para("Twelve one-factor cases, including the baseline, solved. This is a sensitivity check, not parameter calibration: no candidate was adopted as a verified well configuration. The 61-ft rod-to-pump-depth gap remains unexplained. Several adjustments improve one metric while relying on unverified inputs.")
    rows = [["Case", "Load RMSE lbf", "Disp. RMSE in", "Area error %"]]
    for s in sensitivity:
        rows.append([s["variant"], f"{float(s['load_rmse_lbf']):.1f}", f"{float(s['displacement_rmse_in']):.3f}", f"{float(s['card_area_error_percent']):+.1f}"])
    table(rows, [55*mm, 37*mm, 40*mm, 38*mm])
    para("Application and UI acceptance", "Heading2")
    para("The live local APM API accepted and returned the stored reference. The browser reference view displayed the 174-point surface, APM downhole and vendor downhole cards. Scrubbing from sample 1 to sample 88 moved the plunger and both card markers to the same ordered index. Play advanced the shared cursor, and pause stopped it. The TAM overlay toggle changed the plot from two curves to one and restored two. Browser CSV export downloaded a header plus 174 samples. PNG/PDF export and screenshot evidence were not completed. Valve state and pump fillage are unavailable, and the UI labels timing as estimated.")
    table([["Check", "Result"], ["Reference readback", "PASS" if imp["readback_passed"] else "FAIL"], ["Shared scrub/playback", "PASS" if anim["scrub_test"]["plunger_position_changed"] and anim["play_test"]["cursor_advanced"] else "FAIL"], ["Overlay toggle / CSV export", "PASS: 2/1/2 curves; 174 data rows"], ["PNG / PDF UI export", "NOT IMPLEMENTED OR TESTED"], ["Native QRod 3.1 design", "BLOCKED: no saved/reopened design"]], [75*mm, 103*mm])
    para("QRod and 92-state scaleout", "Heading2")
    para("QRod 3.1's design screen was opened, but the 61-ft assembly discrepancy and unverified pump intake pressure/working fluid level prevent a defensible matched design. No QRod-native file was claimed. For the other 92 states, the dry-run inventory found no verified numerical vendor export ready for this adapter. Their status is NO_VERIFIED_EXPORT; source containers were not counted as strokes. The same import workflow can be rerun after each state's numerical export and engineering inputs are verified.")
    para(f"Scaleout rows: {len(scaleout)}. Import-ready now: STATE-077 only. Additional states import-ready from this audit: 0.")
    para("Work-package disposition", "Heading2")
    table([["Package", "Status"], ["Historical APM import / persistence", "COMPLETE for STATE-077"], ["Solver comparison and sensitivity", "COMPLETE as baseline benchmark; calibration remains open"], ["Synchronized historical UI", "PARTIAL: core playback verified; exports incomplete"], ["QRod matched design", "BLOCKED by missing verified inputs"], ["92-state scaleout", "PARTIAL: dry-run inventory, 0 additional ready"], ["ML training/deployment", "NOT RUN"]], [75*mm, 103*mm])
    para("Reproduction and limitations", "Heading2")
    para("Run scripts/import_state077_reference.py, scripts/state077_phase4_analysis.py, scripts/state077_phase4_status.py, scripts/export_state077_phase4_workbooks.mjs and scripts/state077_phase4_report.py from the repository. Preserve vendor originals. The import creates separate historical-reference records and does not treat them as live telemetry. This benchmark tests one historical stroke; it does not establish solver accuracy across other states or confirm vendor-native QRod compatibility.")
    SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm, title="STATE-077 Phase 4 Engineering Benchmark").build(story)
    print(OUT)


if __name__ == "__main__":
    main()
