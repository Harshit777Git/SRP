"""Preserve the obsolete pilot audit and publish a dated evidence reconciliation."""
import json
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "STATE93"
CURRENT = REPORT / "PILOT_INTEROPERABILITY_REPORT.pdf"
ARCHIVE = REPORT / "PILOT_INTEROPERABILITY_REPORT_HISTORICAL_PRE_EXPORT.pdf"


def main():
    if not ARCHIVE.exists():
        shutil.copy2(CURRENT, ARCHIVE)
    benchmark = json.loads((ROOT / "data" / "STATE93" / "pilot" / "Tagging Down Hard" / "validation" / "numerical_comparison.json").read_text())
    imported = json.loads((REPORT / "STATE077_IMPORT_VALIDATION.json").read_text())
    animation = json.loads((REPORT / "STATE077_ANIMATION_ACCEPTANCE.json").read_text())
    styles = getSampleStyleSheet()
    story = [Paragraph("STATE-077 Pilot Interoperability - Reconciled", styles["Title"]),
             Paragraph("18 November 2026 | Tagging Down Hard", styles["Heading2"]), Spacer(1, 5*mm)]
    story.append(Paragraph("This report supersedes the pre-export pilot audit, retained as PILOT_INTEROPERABILITY_REPORT_HISTORICAL_PRE_EXPORT.pdf. The earlier zero-point and blocked-import findings described the state of evidence before the user supplied numerical exports. They are not current findings.", styles["BodyText"]))
    story.append(Spacer(1, 5*mm))
    rows = [["Evidence stage", "Verified result"],
            ["Vendor extraction", "TAM example opened manually; 174 Surface Card and 174 TAM-calculated Pump Card points exported."],
            ["Source consistency", "DYN and four-column TXT surface arrays agree within DYN printed precision; 6-page Summary PDF supplies partial configuration."],
            ["Offline APM", f"Inverse solver completed; load RMSE {benchmark['load_rmse_klbf_index_aligned']:.3f} k-lbf, displacement RMSE {benchmark['position_rmse_in_index_aligned']:.3f} in, card-area error {benchmark['card_area_error_percent']:.2f}%."],
            ["Offline interchange", "DYN and normalized CSV adapters each retained one 174-point card; round-trip completed."],
            ["Database integration", f"Historical reference persisted and read back: 174 / 174 / 174 points; version {imported['version']}; duplicate-free reimport passed."],
            ["Browser integration", "Local APM reference view loaded; shared sample scrub and playback checked. TAM overlay switched off/on; 174-row comparison CSV downloaded."],
            ["QRod 3.1", "Input screen opened; no matched native design saved or reopened because required inputs remain unverified."],
            ["Remaining 92 states", "Dry-run inventory only; no verified four-column vendor exports in the project for those states."]]
    data = [[Paragraph(str(v), styles["BodyText"]) for v in row] for row in rows]
    table = Table(data, colWidths=[48*mm, 128*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#d9e7f0")),
                               ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#aeb9c5")),
                               ("VALIGN",(0,0),(-1,-1),"TOP"),
                               ("TOPPADDING",(0,0),(-1,-1),5),
                               ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.extend([table, Spacer(1, 5*mm)])
    story.append(Paragraph("Decision: STATE-077 historical APM analysis is ready with stated assumptions. A matched QRod design and 92-state scaleout are blocked pending verified inputs and exports. No ML training was performed. See STATE077_ENGINEERING_BENCHMARK.pdf and STATE077_PHASE4_ENGINEERING_REPORT.pdf for numerical and application evidence.", styles["BodyText"]))
    SimpleDocTemplate(str(CURRENT), pagesize=A4, leftMargin=16*mm, rightMargin=16*mm,
                      topMargin=15*mm, bottomMargin=15*mm,
                      title="STATE-077 Pilot Interoperability - Reconciled").build(story)
    print(CURRENT)
    print(ARCHIVE)


if __name__ == "__main__":
    main()
