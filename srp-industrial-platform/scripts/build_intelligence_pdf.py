"""Produce the evidence-based SRP Data Intelligence Report from audited JSON."""
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'reports'
DATA=ROOT/'data'
catalog=json.loads((DATA/'dataset_registry.json').read_text())
profiles=json.loads((REPORTS/'SRP_COLUMN_PROFILING.json').read_text())
zipinfo=json.loads((DATA/'evaluation/onedrive_zip_inventory.json').read_text())
models=json.loads((REPORTS/'SRP_MODEL_FEASIBILITY_MATRIX.json').read_text())
features=json.loads((REPORTS/'SRP_FEATURE_ENGINEERING_CATALOG.json').read_text())
files=json.loads((REPORTS/'SRP_FILE_INVENTORY.json').read_text())

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleSRP',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=20,leading=25,textColor=colors.HexColor('#11354A'),spaceAfter=18))
styles.add(ParagraphStyle(name='BodySRP',parent=styles['BodyText'],fontSize=9,leading=12.5,spaceAfter=5))
styles.add(ParagraphStyle(name='SmallSRP',parent=styles['BodyText'],fontSize=7.3,leading=10))
styles.add(ParagraphStyle(name='SmallHeadSRP',parent=styles['BodyText'],fontSize=7.3,leading=10,textColor=colors.white,fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='HeadSRP',parent=styles['Heading2'],fontSize=12,leading=15,textColor=colors.HexColor('#117D72'),spaceBefore=9,spaceAfter=5))

story=[]
def p(text,style='BodySRP'):story.append(Paragraph(text,styles[style]))
def h(text):p(text,'HeadSRP')
def table(headers,rows,widths=None):
    data=[[Paragraph(str(x),styles['SmallHeadSRP']) for x in headers]]+[[Paragraph(str(x),styles['SmallSRP']) for x in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#143047')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F0F6F6')]),
        ('GRID',(0,0),(-1,-1),.25,colors.HexColor('#C4D4D8')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(t);story.append(Spacer(1,8))

p('SRP Complete Data Intelligence Report','TitleSRP')
p('Evidence cutoff: 17 November 2026. Scope: existing SRP platform, installed Echometer examples, and the user-supplied OneDrive ZIP. Counts distinguish verified numerical records from native vendor files whose contents remain opaque.')
h('1. Executive summary')
p('Nine source-level catalog entries were registered. The verified new measured-origin claim is the NK monitoring CSV: 186,251 hourly parameter observations across ten wells, including 153,093 observations from seven SRP wells. It contains no full dynamometer point sequences or confirmed fault events. Two standalone Echometer Session 20 surface traces contain 348 numerical point pairs; their measurement origin and diagnoses are unverified. The platform preserves 800 primary synthetic training runs. No independently verified real fault labels were acquired, and no production model was retrained or promoted.')
h('2. Dataset inventory and provenance')
table(['ID / source','Origin','Records / cards','Permission','Decision'],[(d['dataset_id'],d['origin'],f"{d.get('records') if d.get('records') is not None else 'unverified'} / {d.get('surface_cards') if d.get('surface_cards') is not None else 'unverified'}",d['permission'],'Training' if d['training_eligible'] else 'No supervised training') for d in catalog],[100,93,84,91,95])
p('The 64-run V2-small and 36-card baseline archives are additional synthetic artifacts; overlap with the 800-run archive was not established, so they are not added to an independent-run total. Repeated CSV exports and vendor copies are not counted as new physical wells.')
h('3. QRod 3.1')
p('Located at C:/Program Files (x86)/Echometer/QRod 3. The installation folder contains the application executable and no separate .qrd, .dyn, CSV or TXT examples. Three .qrd project files in the OneDrive TWM teaching archive were preserved, and Session 20 contains seven more .qrd designs. Their binary settings have not been exported through QRod, so pump geometry, rods, fluid properties and predicted card arrays remain unverified. No equivalent forward simulator case or agreement metric can be claimed from these files yet.')
h('4. Total Well Management')
p('Located at C:/TWM/Examples: 84 files, comprising 39 .bwf files and 45 numbered native records. The supplied ZIP contains additional TWM teaching examples. Their descriptive filenames are instructional context, not adjudicated fault labels. Native records begin with a binary signature and lack a verified open export mapping for load, displacement, timestamps or units; no numerical stroke/card total is asserted. Four XLS sheets collections were readable, but are engineering forms and calculators rather than card point tables.')
h('5. Total Asset Monitor')
p('Located at C:/Program Files (x86)/Echometer/TAM. Its installed Wells tree has 39 folders and 68 native DYN test files. Session 9 has a TAM_EXP container with 23 DYN test members; Session 20 has four. These are test-member counts, not extracted or independent stroke counts. Valve timing, fillage and animations were not treated as ground truth. The only verified numerical Echometer surface point blocks are the two standalone Session 20 ASCII DYN files.')
h('6. OneDrive ZIP safety and extraction')
p(f"Exact source: {zipinfo['source']}. Outer size {zipinfo['bytes']:,} bytes, SHA-256 {zipinfo['sha256']}. One nested ZIP contains {zipinfo['inner_entry_count']} entries. CRC check passed; no encrypted members, unsafe paths or symlinks were found. Three same-content duplicate groups were identified. The 115 non-executable engineering/document entries retained under data/external_reference/onedrive_2026-11-16_2 total 90,389,013 bytes. Eight AVI videos and two configuration/back-up files were left in the original archive. The original archive was not modified.")
h('7. Existing project data and count boundaries')
p('The repository profiler examined 12 CSV files (including one normalized derivative) and 147 source or parameter-specific column profiles; 11 sheets from four XLS workbooks were inspected as forms. The full archive v2_full_runs.npz has arrays series (800,4,200), feature (800,54), label (800). These are 800 independent simulator runs across 100 virtual configurations and eight classes. Source and normalized NK rows are the same observations and are counted once. Source CSV rows from repeated exports are not distinct physical strokes without deduplication by run/stroke ID. Measured field surface cards: zero independently proven; numerical demo surface cards: two; independently measured downhole cards: zero; reconstructed synthetic card arrays: 800 in the primary archive. Unknown native vendor-card counts stay unknown.')
h('8. NK field monitoring: columns and units')
nk=[x for x in profiles if x['original_column_name'].startswith('value [parameter=')]
table(['Parameter','Rows','Unit','Min','Max'],[(x['normalized_name'],f"{x['sample_count']:,}",x['original_unit'],f"{x['minimum']:,.2f}",f"{x['maximum']:,.2f}") for x in nk],[136,68,88,85,85])
p('The six original CSV columns are well_id, well_type, timestamp, parameter, value and unit. Full field definitions, types, cardinalities, missing counts, means, standard deviations and categorical counts are in the data dictionary. The publisher says timestamps lacked an explicit source year and were assigned 2026. Dynamometer area includes negative values and must be reviewed before engineering use. Units and sensor/calculation methods were not checked against original SCADA files.')
p('A normalized derivative in data/normalized/nk_well_monitoring.csv preserves original values and units, adds stable source-row identities and converts only pressure readings from atm to Pa. Its 186,251 rows are not additional measurements. Source key duplicate count is zero, and all six original fields are populated. There are 665 negative dynamometer-area values and 1,328 zero-SPM values; these are quality flags, not confirmed sensor failures.')
p('Across 43 observed well-parameter channels, the median within-channel interval is one hour. The per-channel first-to-last hourly grids contain 19,273 absent slots in total, which can include stopped or unavailable channels. The largest observed interval is 504 hours for NK-86 fillage and area. No within-channel duplicate timestamp was found. Detailed gaps are in SRP_SAMPLING_INTERVALS.csv.')
p('Available platform simulation signals include polished-rod position/load, pump position/load, crank angle, stroke rate, motor RPM, voltage, current, power, gearbox torque, tubing/casing/intake/chamber pressure, net delivered volume and simulation time. Configuration fields include pumping-unit geometry, rod segment length/diameter/modulus/density, pump depth/diameter, fluid density/viscosity, pressure boundaries, damping and sensor rates. These are simulated, not added field measurements. CSV exports expose sample and stroke IDs, timestamps, position/load, direction, solver status, quality, reconstructed card work and equipment configuration where recorded.')
h('9. Data quality and fault labels')
p('For the primary synthetic archive, each class has 100 labeled simulation runs; these are scenario codes, not independent field diagnoses. Real independently verified fault-labeled count is zero. Incomplete real event labels, unknown vendor metadata, unverified timebases and duplicate vendor teaching files block supervised field training. Do not infer labels from condition filenames, card appearance or predicted downhole curves.')
h('10. Simulation and wave-equation readiness')
p('The two ASCII vendor traces can check surface-card import, point ordering and unit conversion under documented format assumptions. A stored card lacks the rod string, depth, geometry, fluid and boundary conditions needed for an equivalent forward QRod/TWM/TAM simulation. The platform inverse solver has one clean synthetic healthy check with load RMSE 128 N (2.31% of reference load range); that is not independent field reconstruction accuracy. A provider downhole calculation would be a comparator, not measured pump truth.')
h('11. Feature engineering')
p(f'{len(features)} candidate features are cataloged with formulas, required columns, units, calculability, missing prerequisites and leakage notes. Surface load extrema and card work are available for synthetic traces and the two vendor demos; time harmonics need verified sample timing. NK supports aggregate SPM, fillage and rod-weight trend features only. Electrical and rod-mechanics features currently rely on synthetic telemetry/configurations. See SRP_FEATURE_ENGINEERING_CATALOG.xlsx.')
h('12. Model feasibility and readiness')
table(['Status','Model count','Examples'],[(status,sum(m['status']==status for m in models),', '.join(m['model_id'] for m in models if m['status']==status)[:125]) for status in sorted(set(m['status'] for m in models))],[125,75,263])
p('NK can support research-only unsupervised anomaly exploration and provider-fillage estimation, with held-out wells and time blocks. Surface, downhole and dual-card fault classifiers need independently adjudicated field labels and numerical cards. Motor, production, efficiency and RUL models require missing measurements and failure/censoring histories. None is ready for operational deployment.')
p('An isolated ridge baseline for provider-reported fillage used 27,874 complete quality-filtered SRP hourly rows across seven wells, with leave-one-whole-well-out evaluation. Mean MAE was 25.80 percentage points versus 32.88 for the training-mean baseline; R-squared was negative for every held-out well. Provider fillage may itself be calculated from correlated channels, so target lineage must be checked. This is not field fault classification or a deployable fillage model. Full per-well results: SRP_NK_FILLAGE_BASELINE.json.')
h('13. Synthetic fault-class confusion')
p('Historical V2 LightGBM grouped test macro F1 is 0.570. The archive is balanced (100 per class), split by 60 train, 20 calibration and 20 test configurations. Training/calibration/test F1 was 0.869/0.637/0.570. Ten of 20 standing-valve leak cases were predicted healthy, eight of 20 traveling-valve leaks were predicted pump wear, and eight of 20 restricted-inflow cases were predicted incomplete fillage. 75% traveling-valve leakage and 50% pump wear produced identical cards in one controlled comparison. The remediated physics baseline scored 0.667 historical and 0.498 on 96 fresh synthetic runs. These are synthetic-only results.')
h('14. Instrumentation and next phase')
p('Priority: secure original numerical card exports with units/timebase and well configuration; secure data-owner retention and training terms; tie each card to valve tests, fluid levels, workovers and production response; obtain real independent wells for held-out evaluation. Then test physical normalization and merged symptom labels on unseen simulation configurations before field validation. Keep the production abstention gate until predefined field performance is met.')
story.append(PageBreak())
h('15. Evidence and limitations')
p('Primary local evidence: data/evaluation/onedrive_zip_inventory.json, data/evaluation/real_acquisition_audit.json, data/training/v2_full_runs.npz, data/evaluation/v2_full_ml.json, data/evaluation/wave.json, reports/SRP_COLUMN_PROFILING.json, reports/SRP_XLS_FORM_INVENTORY.json, data/dataset_registry.json. External NK source: https://huggingface.co/datasets/Arailym-tleubayeva/NK-Oil-Well-Sensor-Monitoring. Native vendor files were preserved but not decoded; source permissions and measured status require provider confirmation. Null in the catalog means unverified, not zero.')
h('16. Vendor GUI export boundary')
p('QRod 3.1 exposed its design input screen and File menu. TWM opened at a license and operating-conditions dialog that covered the workspace. The dialog was not accepted on the user or employer behalf. TAM launched but no usable export menu was visible in its accessible window. Therefore no provider-supported export, equivalent QRod simulation, TWM historical APM import or TAM timing comparison was claimed. A normal authorized vendor application session is required to export point arrays and accompanying equipment data. This is a precise access boundary, not a zero-card finding.')
h('17. Reproducibility and operational controls')
p('The audit scripts under scripts/inspect_onedrive_zip.py, build_data_intelligence.py, normalize_nk_monitoring.py and evaluate_nk_fillage.py regenerate inventories, profiling, normalized hourly records and the research fillage experiment. The original OneDrive ZIP and installed application directories were not modified. The ZIP duplicate groups are based on full member SHA-256 hashes. Data/external_reference holds originals; data/normalized holds a documented derivative; data/training/real_labeled remains empty. Dataset Intelligence in the APM reads the catalog and profile files and displays two numerical vendor demonstrations without labels. The endpoint returned nine datasets, 147 profiles, eight original NK preview rows and two demo card plots in a local smoke test.')
h('18. Decision gates')
p('Do not promote a new fault classifier until rights to the training data, independent event labels, complete ordered cards, measurement units, well groups and a preregistered held-out field evaluation are available. Re-run synthetic results after any simulator physics change. Preserve a FAULT_TYPE_UNDETERMINED result when physical causes are observationally indistinguishable or confidence is insufficient. The NK fillage baseline is exploratory and must not be interpreted as fault-classifier validation.')

def footer(canvas,doc):
    canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#557078'))
    canvas.drawString(42,30,'SRP Industrial Platform | Data Intelligence | 17 Nov 2026')
    canvas.drawRightString(A4[0]-42,30,f'Page {doc.page}')
    canvas.restoreState()

target=REPORTS/'SRP_COMPLETE_DATA_INTELLIGENCE_REPORT.pdf'
SimpleDocTemplate(str(target),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=45,bottomMargin=50,
                  title='SRP Complete Data Intelligence Report',author='SRP Industrial Platform Audit').build(story,onFirstPage=footer,onLaterPages=footer)
print(target)
