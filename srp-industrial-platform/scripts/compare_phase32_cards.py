"""Compare reconstructed pump cards only against matched simulator forward states."""
import json,math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/generated/fault_training_candidate_3129_each'
REPORT=ROOT/'reports/PHASE3_2'
def load(name):return [json.loads(line) for line in (DATA/name).open(encoding='utf8')]
def area(x,y):return abs(float(np.sum((np.asarray(y)+np.roll(y,-1))/2*(np.roll(x,-1)-x))))
def main():
 truth=defaultdict(list)
 for row in load('simulation_truth_labels.jsonl'):truth[(row['run_id'],row['stroke_id'])].append(row)
 results=[]
 for card in load('surface_downhole_cards.jsonl'):
  if card['quality']!='GOOD' or card['downhole']['status']!='SOLVED':continue
  rows=[r for r in truth[(card['run_id'],card['stroke_id'])] if card['raw_sequence'][0]<=r['sequence']<=card['raw_sequence'][1]]
  if len(rows)<32:continue
  t0=datetime.fromisoformat(rows[0]['timestamp']); phase=np.array([(datetime.fromisoformat(r['timestamp'])-t0).total_seconds()/card['period_s'] for r in rows])
  grid=np.arange(len(card['downhole']['position_m']))/len(card['downhole']['position_m'])
  tx=np.interp(grid,phase,[r['true_pump_position_m'] for r in rows],period=1)
  tf=np.interp(grid,phase,[r['true_pump_load_n'] for r in rows],period=1)
  x=np.asarray(card['downhole']['position_m']);f=np.asarray(card['downhole']['load_n'])
  load_rmse=float(np.sqrt(np.mean((f-tf)**2)));offset=x-tx
  true_area=area(tx,tf); reconstructed_area=area(x,f)
  area_difference=abs(reconstructed_area-true_area)
  # A nearly collapsed reference card can amplify relative area errors.
  # Retain absolute work and envelope-normalized error alongside that ratio.
  envelope=float(np.ptp(tx)*np.ptp(tf))
  phase_deg=float(np.angle(np.fft.rfft(x)[1]/np.fft.rfft(tx)[1],deg=True))
  results.append(dict(run_id=card['run_id'],asset_id=card['asset_id'],stroke_id=card['stroke_id'],mechanism=card['synthetic_fault_mechanism'],severity=card['synthetic_severity'],
   samples=len(rows),load_rmse_n=load_rmse,load_rmse_fraction_of_truth_range=load_rmse/max(1.,float(np.ptp(tf))),
   displacement_centered_rmse_m=float(np.std(offset)),displacement_offset_m=float(np.mean(offset)),
   truth_card_area_j=true_area,reconstructed_card_area_j=reconstructed_area,
   absolute_card_area_error_j=area_difference,
   card_area_error_fraction=area_difference/max(1.,true_area),
   card_area_error_fraction_of_envelope=area_difference/envelope if envelope>0 else None,
   position_phase_error_deg=phase_deg,
   production_error='UNAVAILABLE_NO_INDEPENDENT_MEASURED_PRODUCTION'))
 REPORT.mkdir(parents=True,exist_ok=True)
 (REPORT/'MATCHED_SYNTHETIC_CARD_COMPARISON.json').write_text(json.dumps(results,indent=2))
 def summ(k):
  values=np.asarray([r[k] for r in results]);return dict(median=float(np.median(values)),p95=float(np.percentile(values,95)),max=float(np.max(values))) if len(values) else None
 summary=dict(origin='MATCHED_SIMULATOR_FORWARD_TRUTH_NOT_INDEPENDENT_FIELD_REFERENCE',matched_cards=len(results),
  load_rmse_fraction=summ('load_rmse_fraction_of_truth_range'),displacement_centered_rmse_m=summ('displacement_centered_rmse_m'),
  card_area_error_fraction=summ('card_area_error_fraction'),absolute_phase_error_deg=dict(median=float(np.median(np.abs([r['position_phase_error_deg'] for r in results])))) if results else None,
  measured_or_vendor_matched_cases=0,production_error='UNAVAILABLE_NO_INDEPENDENT_MEASURED_PRODUCTION')
 (REPORT/'MATCHED_SYNTHETIC_CARD_COMPARISON_SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
