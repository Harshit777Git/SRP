"""Evidence-backed Phase 3.1 executive report."""
import json
import statistics
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports/PHASE3_1"
styles=getSampleStyleSheet()


def p(text):return Paragraph(text,styles["BodyText"])


def table(rows,widths=None):
    result=Table(rows,colWidths=widths,repeatRows=1,hAlign="LEFT")
    result.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#143047")),
       ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.grey),
       ("FONTSIZE",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),5),
       ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    return result


def add(story,title,content):
    story.extend([Paragraph(title,styles["Heading2"]),Spacer(1,5)])
    story.append(table(content) if isinstance(content,list) else p(content))
    story.append(Spacer(1,12))


def main():
    a=json.loads((REPORT/"ACCEPTANCE_RESULTS.json").read_text())
    mqtt=json.loads((REPORT/"staged_30wells.json").read_text())
    recovery=json.loads((REPORT/"recovery_5wells.json").read_text())
    apm=json.loads((REPORT/"apm_only.json").read_text())
    broker=json.loads((REPORT/"broker_only.json").read_text())
    physics=json.loads((REPORT/"tables/FLEET_PHYSICS_VALIDATION.json").read_text())
    final=mqtt["stages"][-1]
    story=[Paragraph("SRP Phase 3.1 | Engineering acceptance",styles["Title"]),Spacer(1,12)]
    add(story,"Decision: NO-GO", "The 30-well live MQTT-to-APM stack did not sustain the 50 Hz per-well target. The 30-minute stability run was not started because a 30-second run showed rapid durable-queue growth. No QRod numerical prediction was exported, and no ML model was trained or deployed.")
    add(story,"Verified work",[["Item","Measured result"],
        ["Synthetic fleet","30 wells across 6 organizational site groups"],
        ["Offline completed strokes","90; all passed synthetic self-consistency checks"],
        ["Raw export","42,150 dynamometer, 8,439 electrical, 856 pressure rows"],
        ["Fault sensitivity","600 matched cases; 10 mechanisms, 2 severities, 30 wells"],
        ["QRod comparisons","0 independently matched numerical cases"]])
    add(story,"Separate MQTT component capacity",f"The local broker received all {broker['messages']:,} test messages at {broker['receive_rate_per_s']:,.0f}/s. An isolated APM replay persisted all {apm['persisted']:,} samples across 30 wells and assembled {apm['cards']} cards at {apm['ingest_rate_per_s']:,.0f}/s. These isolated capacities do not establish simultaneous live throughput.")
    stage_rows=[["Wells","Broker ack/s","APM persisted/s","Queue start to end"]]
    for x in mqtt["stages"]:
        stage_rows.append([str(x["active_wells"]),f"{x['broker_ack_rate_per_s']:,.0f}",
                           f"{x['apm_persist_rate_per_s']:,.0f}",
                           f"{x['queued_before']:,} to {x['queued_after']:,}"])
    add(story,"Combined live load",stage_rows)
    add(story,"Five-well broker restart",f"The outbox rose to {recovery['recovery']['during']} during the interruption and drained to {recovery['recovery']['final_queued']} after restart and pause. APM persisted {recovery['persisted_samples']:,} samples, produced {recovery['completed_cards']} cards, and the drained stream had {recovery['observed_sequence_gaps']} observed sequence gaps. No drops were reported. This does not prove 30-well restart recovery.")
    add(story,"Physics checks",f"Three consecutive offline strokes per well yielded 90 Surface cards and 90 reconstructed Downhole cards. Across those strokes, maximum load RMSE against isolated simulator truth was {max(x['max_load_rmse_n'] for x in physics):.1f} N; maximum centered plunger-position RMSE was {max(x['max_centered_position_rmse_m'] for x in physics)*1000:.2f} mm; maximum card-area error was {max(x['max_card_area_error_fraction'] for x in physics)*100:.2f}%. A 30-well one-stroke time-step comparison found at most {max(x['step_0067_vs_002_load_rmse_range_fraction'] for x in physics)*100:.3f}% load-range RMSE for 0.0067 s versus 0.002 s. These checks do not establish a 30-minute energy balance or independent engineering accuracy.")
    add(story,"Fault observability", "Matched runs changed physics or measurement channels without arbitrary card deformation. Low-severity standing-valve leakage, restricted inflow and traveling-valve leakage often produced small Surface-load changes. Pump wear and traveling-valve leakage still share an effective leakage pathway. The 600 rows in FAULT_OBSERVABILITY.xlsx are sensitivity data, not fault-classifier accuracy. Field labels remain unavailable.")
    add(story,"APM and data exports", "The APM registers all 30 fictional wells and exposes site, sample sequence and stroke counts. A native gateway smoke test started the Midland site and APM received telemetry and one card per well. All-30 browser interaction was not completed. The healthy synthetic export has CSV and Parquet telemetry, JSON cards and validation, SHA-256 file hashes, and a separate simulation_truth directory for labels and true downhole state. Fault-case raw traces were not exported as a complete training-candidate dataset.")
    add(story,"Unmet acceptance gates",[["Gate","Status"],
        ["30-minute combined stable streaming","Not run; 30-second queue growth failed"],
        ["30-well APM throughput","Failed: "+f"{final['apm_persist_rate_per_s']:,.0f}/s"],
        ["Independent QRod numerical agreement","No supported export / comparison"],
        ["Continuous long-run physics","Three strokes per well only"],
        ["Full fault scenario exports","Not complete"],
        ["Browser E2E for all wells","Not completed"],
        ["ML model boundary","Passed: no model training or deployment"]])
    add(story,"Next engineering actions", "Profile combined scheduling and APM receipt on a quiet host, then retest 30 wells until broker and APM rates exceed the expected 1,500 dynamometer samples/s plus auxiliary traffic with bounded queues. Only then run the 30-minute stability test. Obtain an authorized QRod numerical export with complete matching inputs. Extend multi-stroke physics and fault-case exports before considering synthetic ML experiments.")
    if isinstance(story[-1],Spacer):story.pop()
    target=REPORT/"EXECUTIVE_REPORT.pdf"
    SimpleDocTemplate(str(target),pagesize=(8.5*inch,11*inch),leftMargin=.7*inch,
                      rightMargin=.7*inch,topMargin=.65*inch,bottomMargin=.65*inch).build(story)
    print(target)


if __name__=="__main__":main()
