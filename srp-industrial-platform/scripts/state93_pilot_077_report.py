"""Write the STATE-077 engineering benchmark report from saved evidence."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data" / "STATE93" / "pilot" / "Tagging Down Hard"
REPORT = ROOT / "reports" / "STATE93" / "STATE077_ENGINEERING_BENCHMARK.pdf"
m = json.loads((PILOT / "validation" / "numerical_comparison.json").read_text())
c = json.loads((PILOT / "normalized" / "engineering_config.json").read_text())
styles = getSampleStyleSheet()
story = [Paragraph("STATE-077 | Tagging Down Hard", styles["Title"]),
         Paragraph("Surface-to-downhole engineering benchmark", styles["Heading2"]), Spacer(1, 10)]
story.append(Paragraph("The supplied Echometer DYN and four-column text export contain 174 ordered surface points. Their surface positions and loads agree after converting the text load from k-lbf to lbf. The text also contains 174 TAM-calculated pump-card points. The original PDF, DYN and TXT files are preserved in the pilot/original/user_exports folder.", styles["BodyText"]))
story.append(Spacer(1, 12))
rows = [["Metric", "Result"],
        ["APM inverse solver", m["solver_version"]],
        ["Surface / TAM pump / APM pump points", "174 / 174 / 174"],
        ["Load RMSE, index aligned", f'{m["load_rmse_klbf_index_aligned"]:.3f} k-lbf'],
        ["Displacement RMSE, index aligned", f'{m["position_rmse_in_index_aligned"]:.3f} in'],
        ["Best circular shift (diagnostic)", f'{m["diagnostic_best_circular_shift_samples"]} samples'],
        ["APM vs TAM pump stroke", f'{m["apm_downhole_stroke_in"]:.3f} vs {m["tam_pump_stroke_in"]:.3f} in'],
        ["Stroke difference", f'{m["stroke_length_error_in"]:.3f} in'],
        ["APM vs TAM card area", f'{m["apm_card_area_klbf_in"]:.3f} vs {m["tam_card_area_klbf_in"]:.3f} k-lbf-in'],
        ["Card-area error", f'{m["card_area_error_percent"]:.2f}%']]
t = Table(rows, colWidths=[280, 220])
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183153")),
                       ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                       ("GRID", (0, 0), (-1, -1), .3, colors.grey),
                       ("TOPPADDING", (0, 0), (-1, -1), 6),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
story.extend([t, Spacer(1, 12), Paragraph("Inputs and assumptions", styles["Heading2"])])
story.append(Paragraph("Verified from the supplied summary: 144-in surface stroke; 4563-ft pump intake; rod sections 1552 ft x 1 in, 2750 ft x 0.875 in, and 200 ft x 1 in; 1.75-in plunger; Lufkin C-640D-356-144 unit. TAM's matching DYN summary reports 10.3843 SPM. The DYN filename's local time is treated as corresponding to that TAM UTC record, but this pairing was not confirmed inside the vendor GUI.", styles["BodyText"]))
story.append(Spacer(1, 7))
story.append(Paragraph("Assumptions: production-weighted liquid density from 60 BPD 29-API oil and 300 BPD SG 1.010 water; steel density 7850 kg/m3 and modulus 205 GPa from the APM model; APM viscous damping 0.6 s-1; uniform sample timing. The PDF lists 4502 ft of rods against a 4563-ft pump intake, leaving 61 ft unexplained. TAM's 0.1 damping factor was not treated as equivalent to the APM parameter. Per-point acquisition timestamps and the vendor downhole solver settings were not supplied.", styles["BodyText"]))
story.append(Spacer(1, 12))
story.append(Paragraph("Application status", styles["Heading2"]))
story.append(Paragraph("The APM DYN import adapter accepted one 174-point surface card, and the existing harmonic-transfer inverse solver generated an APM downhole card. This was an offline module execution; import into the running APM database and synchronized animation were not verified. QRod 3.1 opened, but no matching native design was saved because pump intake conditions, full rod length and design assumptions are unresolved. No ML training was performed.", styles["BodyText"]))
story.append(Spacer(1, 7))
story.append(Paragraph("The normalized surface CSV was reimported through the APM CSV adapter. It retained all 174 points; the largest SI value difference against the original DYN import was 0.027, consistent with the DYN file's 0.01-lbf printed load precision.", styles["BodyText"]))
REPORT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(REPORT), pagesize=letter).build(story)
print(REPORT)
