"""Read-only audit of independently labeled measured SRP strokes."""
import csv, json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/training/real_labeled/field_strokes.csv'
OUT=ROOT/'reports/PHASE3_2/FIELD_TRAINING_READINESS.json'
REQUIRED=('well_id','run_id','stroke_id','source_file_sha256','measured_origin','surface_load_unit',
          'surface_position_unit','sample_count','label','label_evidence','evidence_date',
          'reviewer','training_permission','equipment_configuration_id')
ALLOWED={'VERIFIED_TRAINING_ALLOWED'}

def main():
 result=dict(source=str(SOURCE.relative_to(ROOT)),ready=False,eligible_strokes=0,eligible_wells=0,
             class_counts={},rejected=[],required_columns=list(REQUIRED),reason=None)
 if not SOURCE.exists():
  result['reason']='No measured, independently labeled field stroke manifest is present.'
 else:
  with SOURCE.open(newline='',encoding='utf8-sig') as f:
   reader=csv.DictReader(f); missing=[c for c in REQUIRED if c not in (reader.fieldnames or [])]
   if missing:result['reason']='Missing required columns: '+', '.join(missing)
   else:
    seen=set();eligible=[]
    for line,row in enumerate(reader,2):
     key=(row['well_id'],row['run_id'],row['stroke_id'])
     why=[]
     if key in seen:why.append('duplicate well/run/stroke')
     seen.add(key)
     if any(not row[c].strip() for c in REQUIRED):why.append('blank required field')
     if row['measured_origin']!='FIELD_MEASURED':why.append('not field measured')
     if row['training_permission'] not in ALLOWED:why.append('training permission unverified')
     if row['label_evidence'].strip().upper() in {'MODEL_PREDICTION','FILENAME','CURVE_APPEARANCE','SIMULATOR'}:why.append('label not independently confirmed')
     try:
      if int(row['sample_count'])<32:why.append('incomplete stroke')
     except ValueError:why.append('invalid sample count')
     if why:result['rejected'].append(dict(line=line,key=key,reasons=why))
     else:eligible.append(row)
    counts=Counter(r['label'] for r in eligible);wells={r['well_id'] for r in eligible}
    result.update(eligible_strokes=len(eligible),eligible_wells=len(wells),class_counts=dict(counts))
    result['ready']=len(wells)>=10 and bool(counts) and min(counts.values())>=100 and not result['rejected']
    result['reason']='Meets preliminary volume gate; independent held-out evaluation still required.' if result['ready'] else 'Insufficient verified field coverage or rejected records.'
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
