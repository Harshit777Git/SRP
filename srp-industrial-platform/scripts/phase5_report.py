"""Build the Phase 5 evidence report from the checkpoint and numerical inventory."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports"/"STATE93"/"PHASE5"
OUT=REPORT/"MASTER_93_STATE_REPORT.pdf"


def main():
    counts=json.loads((REPORT/"PHASE5_COUNTS.json").read_text())
    checkpoint=json.loads((REPORT/"PROCESSING_CHECKPOINT.json").read_text())
    styles=getSampleStyleSheet(); story=[]
    def para(value,style="BodyText"):
        story.append(Paragraph(value,styles[style]));story.append(Spacer(1,3*mm))
    def table(rows,widths):
        data=[[Paragraph(str(v),styles["BodyText"]) for v in row] for row in rows]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#d9e7f0")),
                               ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#b9c5cf")),
                               ("VALIGN",(0,0),(-1,-1),"TOP"),
                               ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(t);story.append(Spacer(1,5*mm))
    para("Phase 5 - 93-State Engineering Library", "Title")
    para("Checkpointed acquisition report | 18 November 2026", "Heading2")
    para("This is a progress report from original vendor exports. It does not claim that all historical tests or strokes are acquired. STATE-077 remains the only APM reconstructed and benchmarked stroke. No ML training or deployment was run.")
    table([["Measure","Verified total"],
           ["Named states inventoried",counts["states"]],
           ["States opened in TAM",counts["tam_open_verified"]],
           ["States with paired Surface/Pump arrays",counts["states_numerical_exported"]],
           ["Unique strokes exported and matched",counts["exported_unique_strokes"]],
           ["Surface points / TAM Pump points",f"{counts['surface_points']} / {counts['vendor_pump_points']}"],
           ["APM reconstructed points",counts["apm_pump_points"]],
           ["Other strokes in inspected tests, not yet exported",counts["reported_strokes_not_yet_exported"]],
           ["QRod / AWP2000 native projects created and reopened","0 / 0"]],[90*mm,86*mm])
    para("First five TAM examples", "Heading2")
    rows=[["State","Inspected test strokes","Exported stroke","Point pairs","Summary PDF"]]
    for i in range(1,6):
        s=checkpoint["states"][f"STATE-{i:03d}"]
        rows.append([s["state_name"],s["reported_test_strokes"],s["exported_unique_strokes"],s["sample_count"],"Collected"])
    table(rows,[51*mm,30*mm,30*mm,30*mm,35*mm])
    para("Evidence and numerical fidelity", "Heading2")
    para("For each of STATES 001-005, TAM's Field graph supplied one four-column TXT and one counted surface DYN from the selected completed stroke. Each DYN agrees with its TXT surface positions exactly at printed precision; the largest paired load difference is 0.005 lbf. The TXT includes TAM-calculated Pump Card columns. Each state also has its TAM-generated six-page Summary PDF. Original export files are preserved, with SHA-256 hashes and individual state manifests. Separate normalized Surface and vendor Pump Card CSV and Parquet files were generated.")
    para("The selected tests visibly reported 4, 99, 5, 7 and 5 strokes. These reported totals are not treated as exported examples. STATE-077's selected test reports 32 strokes; one numerical stroke is benchmarked. The current inspected-test remainder is 146 strokes. Other historical tests may exist and have not been fully enumerated.")
    para("Engineering and diagnostic limits", "Heading2")
    para("The newly collected Summary PDFs contain equipment information but have not been reconciled into solver-ready configuration versions. No APM downhole reconstruction was run for STATES 001-005. Their vendor comments are retained as source comments, not field-confirmed fault labels. STATE-005's displayed test is after tail-bearing repair, so its state name must not be assigned to every stroke. STATE-002 also has a later zero-stroke valve test; it is not counted as a Dynacard.")
    para("Unique physical well count, complete historical test count, source training permissions, and independent field diagnoses are unverified. The six numerical exports are candidates for research review, not an approved training set.")
    para("Available numerical columns are Surface position (in), Surface load (lbf), vendor Pump position (in), and vendor Pump load (lbf), with one row per matched sample. STATE-077 additionally has a 174-point APM reconstruction. Sample-level timestamps, reviewed configuration versions for STATES 001-005, and pressure/fillage/production columns have not yet been extracted. Duplicate strokes across historical tests have not been assessed; reruns of the same six exports are excluded by source hashes and checkpoint identity.")
    para("The only solver comparison distribution currently has one member: STATE-077. Its load RMSE is 0.627 k-lbf, displacement RMSE 1.422 in, card-area error 5.44%, and stroke difference -0.143 in. No cross-state error distribution can be inferred. Future model candidates include card-shape anomaly detection and supervised state classification after stroke-level diagnoses, independence checks, and source-rights review; no model was trained.")
    para("Scaleout and blockers", "Heading2")
    para("The remaining 33 TAM-available named states and 54 TWM-only states still need supported application opening, test/stroke enumeration, and numerical export. The TWM-to-TAM path has not been verified for the 54 TWM-only states. Native containers are not counted as strokes. QRod and AWP2000 projects require individually reviewed inputs and application save/reopen tests.")
    para("A rerunnable processor updates PROCESSING_CHECKPOINT.json after each state and regenerates the evidence matrices without changing vendor originals. GUI export itself was validated manually for the first five states; unattended TAM automation and full-stroke enumeration remain open work.")
    SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=16*mm,bottomMargin=16*mm,
                      title="Phase 5 93-State Engineering Library").build(story)
    print(OUT)

if __name__=="__main__":main()
