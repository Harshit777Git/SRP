"""Create a compact, evidence-based State93 report from audit outputs."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

root = Path(__file__).resolve().parents[1]
folder = root / "reports" / "STATE93"
summary = json.loads((folder / "summary.json").read_text())
doc = SimpleDocTemplate(str(folder / "93_STATE_FINAL_REPORT.pdf"), pagesize=letter)
styles = getSampleStyleSheet()
story = [Paragraph("SRP 93-State Echometer Interoperability Audit", styles["Title"]), Spacer(1, 16)]
story.append(Paragraph("Source inventory", styles["Heading2"]))
data = [["Measure", "Verified count"], ["Named state folders", summary["states"]],
        ["TAM and TWM source files", summary["paired"]],
        ["TAM source only", summary["tam_only"]],
        ["TWM source only", summary["twm_only"]],
        ["Source file entries", summary["source_file_entries"]],
        ["Duplicate SHA-256 groups", summary["duplicate_hash_groups"]],
        ["Verified native application open tests", 0],
        ["Verified complete numerical cards", 0]]
table = Table(data, colWidths=[320, 120])
table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183153")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), .3, colors.grey),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 7)]))
story.extend([table, Spacer(1, 18), Paragraph("Current readiness", styles["Heading2"])])
for text in [
    "TAM analysis: 39 states have source containers; individual openability has not been verified. The per-well TAM_EXP archives were repackaged and require a TAM import/reopen check.",
    "TWM analysis: 74 states have source files; individual openability has not been verified.",
    "QRod predictive simulation: three original QROD designs exist as references; no matched per-state design is verified.",
    "AWP2000 well-performance analysis: no verified native project or complete input set was found.",
    "Surface Dynacard generation and downhole reconstruction: no complete point arrays have been extracted from these 93 native state records through a supported workflow.",
    "Future ML research: source permission and independently evidenced labels remain unverified. No ML training was performed.",
    "The standardized state folders contain manifests and metadata-only APM packages. Missing native projects and card points were not fabricated.",
]:
    story.extend([Paragraph(text, styles["BodyText"]), Spacer(1, 8)])
story.append(Paragraph("Official references", styles["Heading2"]))
for text in ["https://www.echometer.com/software",
             "https://www.echometer.com/online-training-resources",
             "https://www.echometer.com/software/qrod"]:
    story.append(Paragraph(text, styles["BodyText"]))
doc.build(story)
print(folder / "93_STATE_FINAL_REPORT.pdf")
