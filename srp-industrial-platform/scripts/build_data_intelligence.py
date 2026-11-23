"""Reproducible, read-only source profiling and conservative dataset catalog."""
import csv
import hashlib
import json
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import sys

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
OUT=ROOT/'reports'
OUT.mkdir(exist_ok=True)

MEANING={
 'well_id':('Well identifier','identifier','UNIT_UNVERIFIED'),
 'well_type':('Operating lift category','category','UNIT_UNVERIFIED'),
 'timestamp':('Source observation time','timestamp','timezone_unverified'),
 'parameter':('Name of measured or calculated channel','category','UNIT_UNVERIFIED'),
 'value':('Reading for the parameter named in the same row','conditional_numeric','see unit column'),
 'unit':('Original engineering unit of value','unit','source-defined'),
 'position_in':('Surface polished-rod displacement','measurement','in'),
 'load_lbf':('Surface polished-rod load','measurement','lbf'),
 'plunger_position_in':('Reconstructed plunger displacement','reconstruction','in'),
 'pump_load_lbf':('Reconstructed pump load','reconstruction','lbf'),
 'sample_index':('Order of sample within stroke','index','count'),
 'stroke_id':('Stroke identifier','identifier','UNIT_UNVERIFIED'),
 'spm':('Stroke rate','measurement','strokes/min'),
 'quality':('Producer quality flag','category','UNIT_UNVERIFIED'),
 'source':('Provenance or telemetry source','category','UNIT_UNVERIFIED'),
 'record_id':('Stable hash of source well, time and parameter','identifier','UNIT_UNVERIFIED'),
 'source_dataset_id':('Identifier of original dataset','identifier','UNIT_UNVERIFIED'),
 'source_row':('One-based original CSV row number','index','count'),
 'source_timestamp':('Original timestamp without verified timezone','timestamp','timezone_unverified'),
 'timezone_status':('Timezone verification flag','category','UNIT_UNVERIFIED'),
 'original_value':('Exact source value string parsed as numeric','measurement_or_calculation','see original_unit'),
 'original_unit':('Unit in the source CSV','unit','source-defined'),
 'normalized_value':('Original value converted for pressure channels only','measurement_or_calculation','see normalized_unit'),
 'normalized_unit':('Unit after documented conversion','unit','source-defined'),
 'origin':('Source measurement classification and verification status','category','UNIT_UNVERIFIED'),
}

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def profile(path):
    rel=path.relative_to(ROOT).as_posix()
    frame=pd.read_csv(path,low_memory=False)
    result=[]
    for col in frame.columns:
        s=frame[col]
        numeric=pd.to_numeric(s,errors='coerce')
        nonblank=s.notna() & s.astype(str).str.strip().ne('')
        numeric_type=pd.api.types.is_numeric_dtype(s) or (nonblank.sum()>0 and numeric.notna().sum()/nonblank.sum()>.99 and col not in ('well_id','stroke_id','sample_index'))
        missing=int((~nonblank).sum())
        invalid=int((nonblank & numeric.isna()).sum()) if numeric_type else 0
        meaning,kind,unit=MEANING.get(col,('Source field; engineering meaning not independently verified','unknown','UNIT_UNVERIFIED'))
        if ('nk_well_monitoring' in rel) and col in ('value','original_value','normalized_value'):
            numeric_type=False # Long-format mixed-unit numeric column; do not aggregate incompatible units.
        p=dict(dataset_id=rel,original_column_name=col,normalized_name=col.lower(),engineering_meaning=meaning,
               original_unit=unit,normalized_unit=unit,data_type=str(s.dtype),sample_count=len(s),missing_count=missing,
               missing_percentage=round(100*missing/max(1,len(s)),4),invalid_numeric_count=invalid,
               unique_values=int(s.nunique(dropna=True)),source_type=kind,
               sampling_interval='hourly claimed' if 'nk_well_monitoring' in rel else 'unverified',
               quality='review_required',ml_suitability='conditional',simulation_suitability='conditional',
               leakage_risk='target_or_label' if col in ('fault','label','severity','predicted_class') else 'review',
               notes='')
        if numeric_type:
            v=numeric.dropna()
            p.update(minimum=float(v.min()) if len(v) else None,maximum=float(v.max()) if len(v) else None,
                     mean=float(v.mean()) if len(v) else None,std_dev=float(v.std()) if len(v)>1 else None)
            if len(v) and v.min()!=v.max():
                counts,edges=np.histogram(v,bins=10)
                p['histogram']={'edges':edges.tolist(),'counts':counts.tolist()}
        elif col in ('timestamp','source_timestamp'):
            dates=pd.to_datetime(s,errors='coerce',utc=False)
            p.update(minimum=str(dates.min()),maximum=str(dates.max()),mean=None,std_dev=None)
            p['notes']='Timezone not given; duplicates must be interpreted by well and parameter.'
        else:
            p.update(minimum=None,maximum=None,mean=None,std_dev=None)
            p['value_counts']=s.astype(str).value_counts(dropna=False).head(20).to_dict()
        result.append(p)
    if path.name in ('wells_dataset.csv','nk_well_monitoring.csv') and 'parameter' in frame.columns:
        descriptions={
          'SPM':'Stroke rate','pump_fillage':'Estimated pump fillage',
          'min_rod_weight':'Minimum rod weight reading',
          'max_rod_weight':'Maximum rod weight reading',
          'dynamometer_area':'Reported card-area scalar; no point trace',
          'tubing_pressure':'Tubing pressure','casing_pressure':'Casing pressure',
          'line_pressure':'Flow-line pressure'}
        for parameter,g in frame.groupby('parameter'):
            value_col='normalized_value' if path.name=='nk_well_monitoring.csv' else 'value'
            unit_col='normalized_unit' if path.name=='nk_well_monitoring.csv' else 'unit'
            v=pd.to_numeric(g[value_col],errors='coerce')
            units=g[unit_col].dropna().astype(str).value_counts().to_dict()
            observed=sorted(units)
            p=dict(dataset_id=rel,original_column_name=f'{value_col} [parameter={parameter}]',
                   normalized_name=parameter,engineering_meaning=descriptions.get(parameter,'Source parameter'),
                   original_unit=observed[0] if len(observed)==1 else 'UNIT_INCONSISTENT',
                   normalized_unit=observed[0] if len(observed)==1 else 'UNIT_UNVERIFIED',
                   data_type='float64',sample_count=len(g),missing_count=int(v.isna().sum()),
                   missing_percentage=round(100*v.isna().sum()/len(g),4),invalid_numeric_count=int(v.isna().sum()),
                   unique_values=int(v.nunique()),source_type='sensor_or_provider_calculation_unverified',
                   sampling_interval='hourly claimed; gaps to be checked per well',quality='review_required',
                   ml_suitability='conditional_unsupervised_or_forecasting',simulation_suitability='conditional_range_check',
                   leakage_risk='target_if_estimating_this_parameter',notes=f'unit_counts={units}; mixed long-format value isolated by parameter',
                   minimum=float(v.min()),maximum=float(v.max()),mean=float(v.mean()),std_dev=float(v.std()))
            if v.notna().sum() and v.min()!=v.max():
                counts,edges=np.histogram(v.dropna(),bins=10)
                p['histogram']={'edges':edges.tolist(),'counts':counts.tolist()}
            if parameter=='dynamometer_area':
                p['quality']='SUSPECT_NEGATIVE_VALUES'
                p['notes']+=f'; negative_values={int((v<0).sum())}'
            if parameter=='SPM':
                p['notes']+=f'; zero_values={int((v==0).sum())}'
            result.append(p)
    return result,len(frame)

def main():
    profiles=[]; files=[]
    for path in sorted(DATA.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(ROOT).as_posix()
        item=dict(path=rel,bytes=path.stat().st_size,sha256=sha(path),format=path.suffix.lower())
        if path.suffix.lower()=='.csv':
            try:
                p,n=profile(path); profiles.extend(p);item['rows']=n;item['columns']=[x['original_column_name'] for x in p]
            except Exception as exc:item['read_error']=str(exc)
        elif path.suffix.lower()=='.jsonl':
            with path.open(encoding='utf8') as f:
                item['rows']=sum(1 for line in f if line.strip())
        elif path.suffix.lower()=='.npz':
            try:
                with np.load(path,allow_pickle=False) as n:
                    item['arrays']={k:list(n[k].shape) for k in n.files}
            except Exception as exc:item['read_error']=str(exc)
        files.append(item)
    (OUT/'SRP_COLUMN_PROFILING.json').write_text(json.dumps(profiles,indent=2,ensure_ascii=False),encoding='utf8')
    fields=[k for p in profiles for k in p if k not in ('value_counts','histogram')]
    fields=list(dict.fromkeys(fields))
    with (OUT/'SRP_COLUMN_PROFILING.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:v for k,v in p.items() if k in fields} for p in profiles)
    (OUT/'SRP_FILE_INVENTORY.json').write_text(json.dumps(files,indent=2),encoding='utf8')
    sys.path.insert(0,str(ROOT/'.audit_deps'))
    try:
        import xlrd
        forms=[]
        for path in sorted((DATA/'external_reference/onedrive_2026-11-16_2').rglob('*.xls')):
            book=xlrd.open_workbook(path)
            for sheet in book.sheets():
                forms.append(dict(path=path.relative_to(ROOT).as_posix(),sheet=sheet.name,
                                  rows=sheet.nrows,columns=sheet.ncols,
                                  populated_cells=sum(cell.ctype not in (0,6) for row in sheet.get_rows() for cell in row),
                                  first_row=sheet.row_values(0) if sheet.nrows else [],
                                  classification='engineering form or calculator; not a rectangular card dataset'))
        (OUT/'SRP_XLS_FORM_INVENTORY.json').write_text(json.dumps(forms,indent=2,ensure_ascii=False),encoding='utf8')
    except ImportError:
        forms=[]
    zip_audit=json.loads((DATA/'evaluation/onedrive_zip_inventory.json').read_text())
    nk=pd.read_csv(DATA/'external_reference/nk_well_monitoring/wells_dataset.csv')
    nk['parsed_time']=pd.to_datetime(nk['timestamp'],errors='coerce')
    sampling=[]
    for (well,param),g in nk.groupby(['well_id','parameter']):
        ordered=g.sort_values('parsed_time')['parsed_time'].dropna()
        diff=ordered.diff().dropna().dt.total_seconds()/3600
        expected=int((ordered.iloc[-1]-ordered.iloc[0]).total_seconds()/3600)+1 if len(ordered) else 0
        sampling.append(dict(well_id=well,parameter=param,observations=len(g),first=str(ordered.iloc[0]) if len(ordered) else None,
            last=str(ordered.iloc[-1]) if len(ordered) else None,median_interval_hours=float(diff.median()) if len(diff) else None,
            max_gap_hours=float(diff.max()) if len(diff) else None,missing_hour_slots=max(0,expected-len(ordered)),
            duplicate_timestamp_rows=int(g.duplicated('timestamp').sum())))
    (OUT/'SRP_SAMPLING_INTERVALS.json').write_text(json.dumps(sampling,indent=2),encoding='utf8')
    with (OUT/'SRP_SAMPLING_INTERVALS.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(sampling[0]));writer.writeheader();writer.writerows(sampling)
    classes=['gas_interference','healthy','incomplete_fillage','pump_wear','restricted_inflow',
             'rod_friction','standing_valve_leak','traveling_valve_leak']
    catalog=[
      dict(dataset_id='nk-hourly-2026',source='Hugging Face NK monitoring',origin='MEASURED_CLAIM_UNVERIFIED',
           path='data/external_reference/nk_well_monitoring/wells_dataset.csv',records=186251,
           wells=10,strokes=0,surface_cards=0,downhole_cards=0,raw_samples=186251,labeled_records=0,
           permission='INTERNAL_EVALUATION_ONLY',training_eligible=False,
           reason='Apache-2.0 card with owner caveat; no full cards or verified fault labels'),
      dict(dataset_id='synthetic-v2-full',source='SRP simulator',origin='SYNTHETIC',
           path='data/training/v2_full_runs.npz',records=800,wells=None,virtual_configurations=100,strokes=None,
           surface_cards=800,downhole_cards=800,raw_samples=None,labeled_records=800,
           permission='VERIFIED_TRAINING_ALLOWED',training_eligible=True,
           reason='Simulation-only labels; downhole is reconstruction, not independent measurement'),
      dict(dataset_id='synthetic-v2-small',source='SRP simulator',origin='SYNTHETIC',
           path='data/training/v2_runs.npz',records=64,wells=None,strokes=None,
           surface_cards=64,downhole_cards=64,raw_samples=None,labeled_records=64,
           permission='VERIFIED_TRAINING_ALLOWED',training_eligible=True,
           reason='Potential overlap with full archive unverified; do not add to independent totals'),
      dict(dataset_id='synthetic-baseline',source='SRP simulator',origin='SYNTHETIC',
           path='data/training/simulated_cards.npz',records=36,wells=3,strokes=None,
           surface_cards=36,downhole_cards=36,raw_samples=None,labeled_records=36,
           permission='VERIFIED_TRAINING_ALLOWED',training_eligible=True,
           reason='Separate baseline generator; independence from v2 archive not verified'),
      dict(dataset_id='echometer-session20',source='Echometer demonstration ZIP',origin='DEMONSTRATION_UNKNOWN_ORIGIN',
           path='state/vendor/echometer-session20.zip',records=2,wells=None,strokes=2,
           surface_cards=2,downhole_cards=0,raw_samples=348,labeled_records=0,
           permission='BENCHMARK_ONLY',training_eligible=False,
           reason='Two ASCII DYN point blocks; aliases and filename conditions are not verified field labels'),
      dict(dataset_id='echometer-session09',source='Echometer demonstration ZIP',origin='DEMONSTRATION_UNKNOWN_ORIGIN',
           path='state/vendor/echometer-session09.zip',records=None,wells=None,strokes=None,
           surface_cards=None,downhole_cards=None,raw_samples=None,labeled_records=0,
           permission='PERMISSION_UNVERIFIED',training_eligible=False,
           reason='Nested TAM_EXP with 23 native DYN test members; numerical strokes not decoded'),
      dict(dataset_id='onedrive-twm-examples',source='User-supplied OneDrive ZIP',origin='DEMONSTRATION_UNKNOWN_ORIGIN',
           path=zip_audit['source'],records=zip_audit['inner_entry_count'],wells=None,strokes=None,
           surface_cards=None,downhole_cards=None,raw_samples=None,labeled_records=0,
           permission='INTERNAL_EVALUATION_ONLY',training_eligible=False,
           reason='125 inner entries, proprietary numbered TWM files; three duplicate-content pairs; no validated card export'),
      dict(dataset_id='installed-twm-examples',source='Installed TWM',origin='DEMONSTRATION_UNKNOWN_ORIGIN',
           path='C:/TWM/Examples',records=84,wells=None,strokes=None,surface_cards=None,downhole_cards=None,
           raw_samples=None,labeled_records=0,permission='BENCHMARK_ONLY',training_eligible=False,
           reason='39 BWF and 45 numbered native records; overlap with ZIP possible'),
      dict(dataset_id='installed-tam-examples',source='Installed TAM',origin='DEMONSTRATION_UNKNOWN_ORIGIN',
           path='C:/Program Files (x86)/Echometer/TAM/Documents/Echometer/TAM/Wells',records=68,
           wells=None,strokes=None,surface_cards=None,downhole_cards=None,raw_samples=None,labeled_records=0,
           permission='BENCHMARK_ONLY',training_eligible=False,
           reason='68 native DYN test files in 39 folders; no verified numerical export or ground truth')]
    for item in catalog:
        path=Path(item['path'])
        if not path.is_absolute():path=ROOT/path
        item.update(source_application=item['source'],source_url=(
            'https://huggingface.co/datasets/Arailym-tleubayeva/NK-Oil-Well-Sensor-Monitoring'
            if item['dataset_id']=='nk-hourly-2026' else None),
            original_filename=path.name,import_timestamp='2026-11-17' if item['dataset_id'] in ('nk-hourly-2026','onedrive-twm-examples') else None,
            source_date=None,sha256=sha(path) if path.is_file() else None,
            measured_reconstructed_synthetic_unknown=item['origin'],
            labeled_records=item['labeled_records'],unlabeled_records=(item['records']-item['labeled_records']
                if isinstance(item['records'],int) and isinstance(item['labeled_records'],int) else None),
            fault_classes=(classes if item['dataset_id'] in ('synthetic-v2-full','synthetic-v2-small')
                else ['healthy','gas_interference','traveling_valve_leak'] if item['dataset_id']=='synthetic-baseline' else []),
            engineering_units=('Source unit column; mixed long format' if item['dataset_id']=='nk-hourly-2026'
                else 'Fixed normalized card scales and SI features' if item['origin']=='SYNTHETIC' else 'UNIT_UNVERIFIED'),
            sampling_rate='hourly claimed' if item['dataset_id']=='nk-hourly-2026' else None,
            quality_findings=item['reason'],intended_use='Research benchmarking' if not item['training_eligible'] else 'Synthetic-only model development',
            import_status='RETAINED' if path.is_file() else 'IN_PLACE_OR_REFERENCED',
            training_eligibility_reason=item['reason'])
    (DATA/'dataset_registry.json').write_text(json.dumps(catalog,indent=2),encoding='utf8')
    (OUT/'SRP_DATASET_INVENTORY.json').write_text(json.dumps(catalog,indent=2),encoding='utf8')
    classes=['gas_interference','healthy','incomplete_fillage','pump_wear','restricted_inflow',
             'rod_friction','standing_valve_leak','traveling_valve_leak']
    labels=[dict(fault_code=name,fault_name=name.replace('_',' '),dataset_id='synthetic-v2-full',
                 independent_runs=100,virtual_configurations=100,cards=100,verified_field_wells=0,
                 label_origin='simulation scenario',label_reliability='synthetic mechanism only',
                 training_eligible='synthetic development only') for name in classes]
    (OUT/'SRP_FAULT_LABEL_COVERAGE.json').write_text(json.dumps(labels,indent=2),encoding='utf8')
    specs=[
      ('surface_max_load','max(load_n)','surface load_n','N','Peak polished-rod load','mechanical, fluid loading','YES_SYNTHETIC_AND_DEMO'),
      ('surface_min_load','min(load_n)','surface load_n','N','Minimum polished-rod load','valve, fillage','YES_SYNTHETIC_AND_DEMO'),
      ('surface_load_range','max(load_n)-min(load_n)','surface load_n','N','Dynamic load span','fluid loading, friction','YES_SYNTHETIC_AND_DEMO'),
      ('surface_stroke','max(position_m)-min(position_m)','surface position_m','m','Polished-rod travel','position sensor, unit setup','YES_SYNTHETIC_AND_DEMO'),
      ('surface_card_area','absolute closed-loop integral load_n d(position_m)','ordered surface position_m, load_n','J','Stroke work proxy','fillage, valve, friction','YES_SYNTHETIC_AND_DEMO'),
      ('up_down_load_delta','mean load upstroke minus mean load downstroke','ordered surface samples, phase','N','Load asymmetry','fillage, friction, valves','SYNTHETIC_ONLY_PHASE_UNVERIFIED_IN_DEMO'),
      ('load_gradient','d(load_n)/d(position_m)','ordered surface samples','N/m','Abrupt load transition','fluid pound, valve effects','CONDITIONAL_NOISE_SENSITIVE'),
      ('load_harmonics','FFT(load_n) after uniform time resampling','timestamped ordered surface samples','N','Periodic loading structure','friction, sensor faults','SYNTHETIC_ONLY_TIMEBASE_MISSING_IN_DEMO'),
      ('pump_stroke','max(plunger_position_m)-min(plunger_position_m)','reconstructed downhole position_m','m','Effective plunger travel','rod stretch, travel loss','RECONSTRUCTED_SYNTHETIC_ONLY'),
      ('pump_load_range','max(pump_load_n)-min(pump_load_n)','reconstructed downhole load_n','N','Pump loading span','fillage, valve effects','RECONSTRUCTED_SYNTHETIC_ONLY'),
      ('downhole_work','closed-loop integral pump_load_n d(plunger_position_m)','ordered reconstructed downhole card','J','Pump stroke work','hydraulic anomalies','RECONSTRUCTED_SYNTHETIC_ONLY'),
      ('pump_fillage','source reported fillage percentage','NK pump_fillage','%','Provider-estimated chamber fillage','incomplete fillage','NK_HOURLY_ONLY_METHOD_UNVERIFIED'),
      ('motor_current_rms','sqrt(mean(current_a squared))','timestamped current_a','A','Electrical loading','motor anomaly, friction','SYNTHETIC_TELEMETRY_ONLY'),
      ('motor_power_mean','mean(power_w)','timestamped power_w','W','Average electrical demand','efficiency, friction','SYNTHETIC_TELEMETRY_ONLY'),
      ('torque_span','max(torque_nm)-min(torque_nm)','timestamped torque_nm','N m','Gearbox cyclic loading','balance, mechanical anomaly','SYNTHETIC_TELEMETRY_ONLY'),
      ('pressure_delta','tubing_pa-casing_pa','synchronized tubing_pa, casing_pa','Pa','Surface pressure differential','hydraulic state','SYNTHETIC_ONLY_NK_PRESSURES_FOUNTAIN'),
      ('rod_stiffness','sum segment EA/L in mechanical model','rod length, diameter, modulus','N/m','Elastic response scale','rod mechanical anomalies','SYNTHETIC_CONFIG_ONLY'),
      ('stroke_change','current feature minus rolling healthy baseline','time-ordered strokes and stable well ID','feature unit','Departure from well baseline','all observable changes','SYNTHETIC_ONLY_DEMO_NO_TIMEBASE')]
    features=[dict(feature_id=a,formula=b,required_columns=c,units=d,physical_meaning=e,
                   candidate_faults=f,calculability=g,missing_prerequisites='field timebase, equipment and verified labels' if 'SYNTHETIC' in g else 'source-specific verification',
                   leakage_risk='Use only lagged baselines and exclude provider diagnosis targets',
                   validation='Compare against held-out well and controlled physical intervention',
                   reliability='engineering candidate, no independent field validation')
              for a,b,c,d,e,f,g in specs]
    (OUT/'SRP_FEATURE_ENGINEERING_CATALOG.json').write_text(json.dumps(features,indent=2),encoding='utf8')
    model_specs=[
      ('surface_card_fault_classification','verified fault cause','surface card','REQUIRES_LABELS'),
      ('downhole_card_fault_classification','verified fault cause','independent downhole card and field labels','REQUIRES_LABELS'),
      ('dual_card_fault_classification','verified fault cause','aligned surface and downhole card','REQUIRES_LABELS'),
      ('healthy_vs_abnormal','adjudicated operating anomaly','longitudinal cards or monitoring baselines','REQUIRES_LABELS'),
      ('unsupervised_anomaly','deviation score','NK hourly well parameters','READY_FOR_EXPERIMENT'),
      ('pump_fillage_estimation','provider pump_fillage','NK hourly SPM, load extrema, area','READY_FOR_EXPERIMENT'),
      ('fluid_pound_detection','verified fluid-pound event','time-resolved full cards','REQUIRES_LABELS'),
      ('gas_interference_detection','verified gas interference','full cards and pressure/gas evidence','REQUIRES_LABELS'),
      ('valve_leakage_diagnosis','verified valve test or inspection','cards, valve test, pressure','REQUIRES_LABELS'),
      ('rod_anomaly_detection','verified rod inspection','cards, rod configuration, inspection','REQUIRES_LABELS'),
      ('motor_anomaly_detection','verified motor fault','electrical telemetry and failure events','REQUIRES_MORE_DATA'),
      ('pump_efficiency_estimation','measured produced volume and input work','production rate, cards, power','REQUIRES_MORE_DATA'),
      ('production_forecasting','measured production rate','time-series production and context','REQUIRES_MORE_DATA'),
      ('remaining_useful_life','time to failure with censoring','failure, repair and censoring history','NOT_CURRENTLY_FEASIBLE')]
    models=[dict(model_id=a,target=b,required_inputs=c,status=d,
                 usable_independent_field_labels=0,
                 candidate_data='NK hourly monitoring' if d=='READY_FOR_EXPERIMENT' else 'synthetic demonstrations only',
                 suggested_method='grouped-well baseline, then tree model' if d=='READY_FOR_EXPERIMENT' else 'defer supervised model',
                 validation='hold out whole wells and time blocks; no synthetic-to-field accuracy claim',
                 deployment='NOT_READY',blocker='No independent labels or required measurements' if d!='READY_FOR_EXPERIMENT' else 'Research only; source year and owner terms need verification')
            for a,b,c,d in model_specs]
    (OUT/'SRP_MODEL_FEASIBILITY_MATRIX.json').write_text(json.dumps(models,indent=2),encoding='utf8')
    print(json.dumps(dict(files=len(files),csv_files=sum(f['format']=='.csv' for f in files),
                          profiled_columns=len(profiles),xls_sheets=len(forms),catalog_datasets=len(catalog),csv_rows={f['path']:f.get('rows') for f in files if f['format']=='.csv'},
                          npz=[f for f in files if f['format']=='.npz']),indent=2))

if __name__=='__main__':main()
