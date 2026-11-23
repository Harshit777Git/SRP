"""Normalize permitted NK hourly observations without inventing card samples."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/external_reference/nk_well_monitoring/wells_dataset.csv'
TARGET=ROOT/'data/normalized/nk_well_monitoring.csv'
META=ROOT/'data/normalized/nk_well_monitoring.schema.json'
PRESSURE={'tubing_pressure','casing_pressure','line_pressure'}

def main():
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    fields=['record_id','source_dataset_id','source_row','well_id','well_type','source_timestamp',
            'timezone_status','parameter','original_value','original_unit','normalized_value',
            'normalized_unit','origin','quality']
    count=0; suspect=0
    with SOURCE.open(newline='',encoding='utf8') as source,TARGET.open('w',newline='',encoding='utf8') as output:
        reader=csv.DictReader(source)
        writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
        for n,row in enumerate(reader,1):
            value=float(row['value'])
            name=row['parameter'];unit=row['unit']
            if name in PRESSURE and unit=='atm':
                normalized=value*101325;normal_unit='Pa'
            else:
                normalized=value;normal_unit=unit
            quality='SUSPECT_NEGATIVE_AREA' if name=='dynamometer_area' and value<0 else 'UNVERIFIED_SOURCE'
            suspect+=quality=='SUSPECT_NEGATIVE_AREA'
            record_id=hashlib.sha256(f"nk-hourly-2026|{row['well_id']}|{row['timestamp']}|{name}".encode()).hexdigest()[:24]
            writer.writerow(dict(record_id=record_id,source_dataset_id='nk-hourly-2026',source_row=n,
                well_id=row['well_id'],well_type=row['well_type'],source_timestamp=row['timestamp'],
                timezone_status='UNVERIFIED',parameter=name,original_value=row['value'],original_unit=unit,
                normalized_value=f'{normalized:.10g}',normalized_unit=normal_unit,
                origin='MEASURED_CLAIM_UNVERIFIED',quality=quality))
            count+=1
    META.write_text(json.dumps(dict(schema='srp-normalized-hourly/1',source=str(SOURCE.relative_to(ROOT)),
        destination=str(TARGET.relative_to(ROOT)),rows=count,suspect_negative_area=suspect,
        conversions={'atm_to_Pa':101325},notes='Original fields preserved; timestamp year and timezone unverified. No card points or fault labels.'),indent=2),encoding='utf8')
    print(count,suspect)

if __name__=='__main__':main()
