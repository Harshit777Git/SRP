"""Build evidence-only Phase 3 PDF summaries."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
styles = getSampleStyleSheet()


def para(text):
    return Paragraph(text, styles["BodyText"])


def document(path, title, sections):
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for heading, content in sections:
        story += [Paragraph(heading, styles["Heading2"]), Spacer(1, 5)]
        if isinstance(content, list):
            table = Table(content, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#143047")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.grey),
                ("FONTSIZE", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
            story.append(table)
        else:
            story.append(para(content))
        story.append(Spacer(1, 12))
    SimpleDocTemplate(str(path), pagesize=(8.5*inch, 11*inch), leftMargin=.7*inch,
                      rightMargin=.7*inch, topMargin=.65*inch, bottomMargin=.65*inch).build(story)


def main():
    acceptance = json.loads((ROOT / "reports/PHASE3/PHASE3_ACCEPTANCE_RESULTS.json").read_text())
    cases = json.loads((ROOT / "data/evaluation/phase3/validation.json").read_text())["cases"]
    mqtt = json.loads((ROOT / "reports/PHASE3/MQTT_MULTIWELL_BENCHMARK.json").read_text())
    output = ROOT / "reports/PHASE3/PHASE3_EXECUTIVE_REPORT.pdf"
    document(output, "SRP Phase 3 | Engineering status", [
        ("Decision: NO-GO for ML experimentation", "Thirty synthetic wells completed one offline stroke each, but QRod numerical benchmarking was unavailable and the 30-well MQTT load gate failed. No fault model was trained, replaced or deployed."),
        ("Inventory and extraction", [["Evidence", "Count / status"], ["TWM native example files", "84"],
            ["TAM native DYN test files", "68"], ["ASCII numerical demo surface cards", "2 (132 + 216 points)"],
            ["QRod design files", "10; numerical predictions unavailable"]]),
        ("Synthetic fleet", f"{acceptance['sites']} organizational site groups, {acceptance['wells']} fictional wells, {acceptance['synthetic_validated_strokes']} complete synthetic strokes, {acceptance['surface_cards']} Surface cards, {acceptance['reconstructed_downhole_cards']} reconstructed Downhole cards and {acceptance['raw_sensor_samples']} sensor-equivalent samples. These are synthetic self-consistency counts, not field validation."),
        ("Inverse reconstruction", [["Metric across 30 wells", "Median", "Maximum"],
            ["Centered position RMSE (mm)", f"{sorted(x['centered_position_rmse_m'] for x in cases)[14]*1000:.2f}", f"{max(x['centered_position_rmse_m'] for x in cases)*1000:.2f}"],
            ["Load RMSE (N)", f"{sorted(x['load_rmse_n'] for x in cases)[14]:.1f}", f"{max(x['load_rmse_n'] for x in cases):.1f}"],
            ["Card area error (%)", f"{sorted(x['card_area_error_fraction'] for x in cases)[14]*100:.2f}", f"{max(x['card_area_error_fraction'] for x in cases)*100:.2f}"]]),
        ("MQTT load gate: FAIL", f"All 30 workers started. Over a 15-second window, the broker acknowledged {mqtt['published_delta']} messages ({mqtt['published_messages_per_s']:.1f}/s), versus the 1,500/s dynamometer target alone. Queued messages grew from {mqtt['before']['queued']} to {mqtt['after']['queued']}; dropped count was {mqtt['dropped_delta']}. No all-well APM receipt or complete live stroke test was demonstrated."),
        ("Fault physics", "Direct underfill no longer uses restricted inflow as an instantaneous chamber-void source. Matched one-well cards now differ, while traveling-valve leak/pump wear and standing-valve leak/healthy remain relatively close. This does not establish reliable fault identification."),
        ("Remaining gates", "User-authorized vendor export, equivalent QRod reference cases, 30-well MQTT throughput and APM routing, deterministic full-run validation, and engineering quality gates are still required. A configuration-isolated future split manifest exists, but only one healthy stroke per well was generated. The requested Parquet and full scenario dataset were not generated."),
    ])
    pairs = json.loads((ROOT / "reports/PHASE3/fault_observability.json").read_text())
    rows = [["Fault A", "Fault B", "Surface RMSE N", "Downhole RMSE N"]]
    for x in pairs:
        if x["first"] < x["second"]:
            rows.append([x["first"].replace("_", " "), x["second"].replace("_", " "),
                         f"{x['surface_load_rmse_n']:.1f}", f"{x['downhole_load_rmse_n']:.1f}"])
    document(ROOT / "reports/FAULT_SIGNATURE_COMPARISON.pdf", "Matched synthetic fault signatures", [
        ("Scope", "One fictional well, 0.8 severity, identical design and deterministic seed. Distances compare 200 phase-resampled load points. They are descriptive; no field ground truth or statistical class separation is claimed."),
        ("Pairwise load differences", rows),
        ("Interpretation", "Zero or small distances show poor card observability in this model. Different curves do not prove a future classifier will identify root cause across wells and severities. See reports/FAULT_OBSERVABILITY_MATRIX.csv for all 64 ordered pairs and displacement distances."),
    ])
    print(output)


if __name__ == "__main__":
    main()
