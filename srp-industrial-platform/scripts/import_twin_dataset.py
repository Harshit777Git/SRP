"""Import measured configuration columns without inferring missing equipment geometry."""
import csv
import json
import math
from pathlib import Path
from collections import Counter
from context import ROOT

source = ROOT.parent / 'DIGITAL_TWIN_DATASET'
wells = []
for row in csv.DictReader((source/'MASTER_120_WELLS_CONFIGURATION.csv').open(encoding='utf-8-sig')):
    lengths = [float(x)*.3048 for x in row['rod_section_length_ft'].split(';')]
    diameters = [float(x)*.0254 for x in row['rod_section_diameter_in'].split(';')]
    oil_sg = 141.5/(float(row['oil_api_gravity'])+131.5)
    water = float(row['water_cut_pct'])/100
    density = 1000*((1-water)*oil_sg+water*float(row['water_specific_gravity']))
    depth = sum(lengths)
    well = dict(asset_id=row['well_id'],rods=[dict(length_m=l,diameter_m=d,
        density=float(row['rod_material_density_kg_m3']),modulus=float(row['rod_youngs_modulus_psi'])*6894.757293) for l,d in zip(lengths,diameters,strict=True)],
        stroke_m=float(row['surface_stroke_length_in'])*.0254,spm=float(row['spm']),
        plunger_m=float(row['pump_plunger_diameter_in'])*.0254,
        plunger_radial_clearance_m=float(row['pump_clearance_in'])*.0254/2,
        fluid_kg_m3=density,viscosity_pa_s=float(row['fluid_viscosity_cp'])/1000,
        intake_head_m=depth-float(row['dynamic_fluid_level_ft'])*.3048,
        tubing_pa=float(row['tubing_pressure_psi'])*6894.757293,
        casing_pa=float(row['casing_pressure_psi'])*6894.757293,
        voltage_v=float(row['motor_rated_voltage_v']),damping_s=float(row['model_damping_coefficient']),
        dynamometer_hz=20,electrical_hz=5,pressure_hz=1)
    wells.append(dict(site_id=row['well_id'].split('-')[0].title(),well=well,
        provenance=dict(source='synthetic dataset',state_id=row['state_id'],fault=row['fault_mechanism'],
            clearance_assumption='input treated as diametral fit; radial clearance is half',
            geometry='four-bar dimensions absent; existing defaults retained')))
counts=Counter();nonfinite=0;power_residual=[]
with (source/'MASTER_120_WELLS_TELEMETRY.csv').open(encoding='utf-8-sig') as stream:
    for row in csv.DictReader(stream):
        counts[row['well_id']]+=1
        for key,value in row.items():
            try: nonfinite+=not math.isfinite(float(value))
            except ValueError: pass
        p=float(row['motor_active_power_kw'])*1000
        apparent=math.sqrt(3)*float(row['motor_voltage_v'])*float(row['motor_current_a'])
        power_residual.append(p/apparent if apparent else None)
output=ROOT/'config/fleet/dataset_120_wells.json'
output.write_text(json.dumps(dict(wells=wells),indent=2))
report=dict(wells=len(wells),rows=sum(counts.values()),rows_per_well=dict(counts),nonfinite=nonfinite,
    inferred_power_factor_range=[min(x for x in power_residual if x is not None),max(x for x in power_residual if x is not None)],
    source='synthetic; independent onsite validation unavailable',calibration_status='configuration import; parameter fitting pending')
(ROOT/'reports/DATASET_120_AUDIT.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='rows_per_well'},indent=2))
