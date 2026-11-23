import csv
import datetime as dt
import hashlib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path.cwd()
PROJECT = ROOT / 'srp-industrial-platform'
DATA = PROJECT / 'data'
REPORTS = PROJECT / 'reports'
EXTERNAL = DATA / 'external_reference'
DESKTOP = ROOT.parent
ONEDRIVE = DESKTOP.parent
DOWNLOADS = Path.home() / 'Downloads'
MASTER = DESKTOP / 'Master Dataset'
OUT = PROJECT / 'outputs/01a1f1fd-6501-7a40-89e3-df4b424daa3b/field'
OUT.mkdir(parents=True, exist_ok=True)


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def scalar(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        return value if isinstance(value, (int, float, bool)) else encoded(value)
    if re.fullmatch(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?', value):
        parsed = float(value)
        if math.isfinite(parsed):
            return parsed
    return value


def clean_key(value):
    return re.sub(r'[^a-z0-9]', '', (value or '').casefold())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


catalog_path = REPORTS / 'STATE96/96_STATE_ACQUISITION_MATRIX.csv'
catalog = {r['State ID']: r['State Name'] for r in csv_rows(catalog_path)}
name_map = {clean_key(v): k for k, v in catalog.items() if v}
label_audit = {r['state_id']: r for r in csv_rows(REPORTS / 'STATE93/PHASE5_1/DIAGNOSTIC_LABEL_AUDIT.csv')}


def state_for(name):
    for part in reversed(re.split(r'[/\\]', str(name))):
        explicit = re.match(r'(?i)^s?tate-(\d{3})(?:\D|$)', part)
        if explicit and (state := 'STATE-' + explicit[1]) in catalog:
            return state
        for key in (part, Path(part).stem, re.split(r'_DYN_|_test-|_Summary|_Test.History|_\{', part, flags=re.I)[0]):
            if state := name_map.get(clean_key(key)):
                return state
    return None


sources = {}
assets = defaultdict(list)
review = []
scope = []
first_hash = {}
known_native_extensions = {'.dyn', '.tam_exp', '.twm', '.qrd', '.pdf', '.txt'}


def scan(directory, label, recursive=True):
    count = 0
    if directory.is_dir():
        for path in sorted(directory.rglob('*') if recursive else directory.iterdir()):
            ext = path.suffix.lower()
            state = state_for(path)
            relevant = ext in {'.dyn', '.tam_exp', '.qrd', '.twm'} or (state and (ext.isdecimal() or re.fullmatch(r'\.\d+', ext) or ext in {'.pdf', '.txt'}))
            if relevant and path not in sources and path.is_file():
                try:
                    raw = path.read_bytes()
                    sha = digest(raw)
                    copy_of = first_hash.setdefault(sha, str(path))
                    row = [state, label, ext, len(raw), sha, str(path), copy_of if copy_of != str(path) else None]
                    sources[path] = row
                    if state:
                        assets[state].append(row[1:])
                    count += 1
                except OSError as exc:
                    review.append([str(path), 'Read error', str(exc)])
    scope.append([label, str(directory), count, 'Scanned' if directory.is_dir() else 'Unavailable'])


scan(DATA / 'state93', 'Project state library')
scan(MASTER / 'Examples', 'Master Dataset')
scan(DOWNLOADS, 'Downloads exports', False)
scan(DESKTOP, 'OneDrive desktop exports', False)
scan(EXTERNAL, 'Project external reference')
for folder in ('TAM_Individual_Wells', 'TWM_Examples_Missing'):
    scan(DESKTOP / folder, 'OneDrive ' + folder)
for folder in ('OneDrive_2026-11-16', 'OneDrive_1_16-11-2026'):
    scan(DOWNLOADS / folder, 'Downloads ' + folder)


well_rows = defaultdict(list)
test_rows = defaultdict(list)
parameters = defaultdict(list)
native_members = defaultdict(list)
test_versions = defaultdict(set)
observed_tests = set()
observed_wells = set()
seen_tam = set()
archive_wells = defaultdict(set)

TAM_FIELDS = {
    'spm': ('Strokes Per Minute',),
    'peak_polished_rod_load_tam': ('Peak Polished Rod Load',),
    'minimum_polished_rod_load_tam': ('Minimum Polished Rod Load',),
    'computed_stroke_length_tam': ('Computed Stroke Length',),
    'effective_plunger_travel_tam': ('Effective Plunger Travel',),
    'pump_displacement_tam': ('Pump Displacement',),
    'fillage_average_tam': ('Average Fillage',),
    'fillage_adjusted_tam': ('Adjusted Fillage',),
    'tubing_pressure_tam': ('DYN Tubing Pressure',),
    'casing_pressure_tam': ('DYN Casing Pressure', 'ACU Casing Pressure'),
    'pump_intake_pressure_dyn_tam': ('PIP DYN',),
    'pump_intake_pressure_acoustic_tam': ('PIP LL',),
    'pump_discharge_pressure_tam': ('Pump Discharge Pressure',),
    'distance_to_liquid_tam': ('Distance to Liquid',),
    'oil_production_tam': ('Oil Production',),
    'water_production_tam': ('Water Production',),
    'gas_production_tam': ('Gas Production',),
    'polished_rod_power_tam': ('Polished Rod Power',),
    'pump_hp_tam': ('Pump HP',),
    'gearbox_torque_rms_tam': ('Existing RMS Gearbox Torque',),
    'beam_loading_tam': ('Beam Loading',),
    'rod_loading_goodman_pct_tam': ('Maximum Rod Loading % Goodman',),
    'volumetric_efficiency_tam': ('Volumetric Efficiency',),
    'rated_current_tam': ('Rated Current',),
    'acquisition_rate_tam': ('Acquisition Rate',),
    'reported_strokes_tam': ('Number of Strokes',),
    'load_cell_serial_tam': ('DYN Load Cell Serial Number',),
    'well_state_tam': ('Well State',),
}


def source_metric(values, aliases):
    for name in aliases:
        value = values.get(name)
        if value is not None and value != '' and (not isinstance(value, (float, int)) or math.isfinite(value) and abs(value) < 1e30):
            return value
    return None


for path, asset in sources.items():
    if asset[2] != '.tam_exp' or asset[4] in seen_tam:
        continue
    seen_tam.add(asset[4])
    try:
        with zipfile.ZipFile(path) as archive:
            metadata = json.loads(archive.read('metadata.json'))
            wells = json.loads(archive.read('TestResults.json')).get('Wells', [])
            for well in wells:
                name, wid = well.get('Name'), well.get('ID')
                state = state_for(name or '') or asset[0] or 'Unmapped'
                archive_wells[state].add(str(path))
                for member in archive.infolist():
                    if not wid or wid.casefold() not in member.filename.casefold() or member.is_dir():
                        continue
                    kind = 'Native test' if '/Tests/' in member.filename else 'Native well configuration'
                    native_members[state].append([wid, kind, member.filename, member.file_size, f'{member.CRC:08x}', str(path)])
                info = {k: v for k, v in well.items() if k != 'Tests'}
                identity = (state, wid, encoded(info))
                if identity not in observed_wells:
                    observed_wells.add(identity)
                    well_rows[state].append([wid, name, well.get('Company'), well.get('MajorGroup'), well.get('MinorGroup'), well.get('GPSBlock'), well.get('Description'), well.get('SavedAppVersion'), encoded(info), str(path)])
                for ordinal, test in enumerate(well.get('Tests') or [], 1):
                    timestamp = test.get('DateTime')
                    kind = test.get('Type')
                    nums, strs = test.get('NumValues') or {}, test.get('StrValues') or {}
                    identity = (state, wid, timestamp, kind)
                    fingerprint = digest(encoded([nums, strs]).encode())
                    test_versions[identity].add(fingerprint)
                    if (*identity, fingerprint) in observed_tests:
                        continue
                    observed_tests.add((*identity, fingerprint))
                    test_key = f'TAM-{digest(encoded([*identity, fingerprint]).encode())[:16]}'
                    combined = nums | strs
                    test_rows[state].append([test_key, wid, name, kind, timestamp, test.get('LastModified'), ordinal, metadata.get('SourceVersion'), len(nums), len(strs), str(path), *[source_metric(combined, a) for a in TAM_FIELDS]])
                    for value_kind, entries in [('numeric', nums), ('text', strs)]:
                        for parameter, value in entries.items():
                            if isinstance(value, float) and not math.isfinite(value):
                                value = str(value)
                            parameters[state].append([test_key, parameter, value_kind, value, 'Source units unverified', str(path)])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        review.append([str(path), 'TAM archive', str(exc)])

for (state, well, timestamp, kind), versions in test_versions.items():
    if len(versions) > 1:
        review.append([state, 'TAM result revisions retained', f'{well} {kind} {timestamp} has {len(versions)} result variants'])


verified = list(csv_rows(REPORTS / 'STATE93/PHASE5_1/UNIQUE_STROKE_INVENTORY.csv'))
verified_by_hash = {r['txt_sha256']: r for r in verified if r['txt_sha256']}
verified_by_dyn = {r['dyn_sha256']: r for r in verified if r['dyn_sha256']}
archive_identity = {}
for state, wells in well_rows.items():
    ids = {w[0] for w in wells if w[0]}
    if len(ids) == 1:
        archive_identity[state] = next(iter(ids))


def read_paired(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if not lines or not lines[0].startswith('#Surface Card Position') or 'Pump Card Load' not in lines[0]:
        return None
    points = [tuple(map(float, l.split())) for l in lines[1:] if l.strip() and not l.startswith('#')]
    if not 32 <= len(points) <= 15000 or any(len(p) != 4 or not all(map(math.isfinite, p)) for p in points):
        raise ValueError('Four-column export failed shape or finiteness check')
    return [(x, y * 1000, u, v * 1000) for x, y, u, v in points]


def read_dyn(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    n = int(lines[0].strip())
    values = [tuple(map(float, x.split(','))) for x in lines[1:n + 1]]
    if not (32 <= n <= 15000 and len(values) == n) or any(len(p) != 2 or not all(map(math.isfinite, p)) for p in values):
        raise ValueError('Counted surface block failed shape or finiteness check')
    return values


def card_labels(path, verification):
    if verification:
        stroke = re.match(r'\d+', verification['stroke_id'])
        return verification['test_id'], int(stroke[0]) if stroke else None
    match = re.search(r'_test-(\d{4}-\d{2}-\d{2}_\d{6})_stroke-(\d+)', path.name, re.I)
    if match:
        return match[1], int(match[2])
    match = re.search(r'_DYN_\d+_(\d{2})-(\d{2})-(\d{4})_(\d{2})-(\d{2})-(\d{2})', path.name, re.I)
    if match:
        m, d, y, h, mm, s = match.groups()
        return f'{y}-{m}-{d}_{h}{mm}{s}', None
    return path.stem, None


stroke_meta = defaultdict(list)
point_rows = defaultdict(list)
indexed_dyn = defaultdict(list)
seen_export = set()
used_dyn = set()
curve_sources = defaultdict(dict)

for path, row in sources.items():
    if row[2] == '.dyn':
        indexed_dyn[(row[0], path.stem.casefold())].append(path)


def add_capture(path, state, values, dyn=None, verification=None, reason=None):
    paired = len(values[0]) == 4
    test, stroke = card_labels(path, verification)
    normalized_fingerprint = digest(encoded([[round(v, 5) for v in p] for p in values]).encode())
    prior = curve_sources[state].get(normalized_fingerprint)
    if prior and (prior[1] == test and prior[2] == stroke or state == 'STATE-077'):
        return
    capture = f'{state}-CARD-{len(stroke_meta[state]) + 1:03d}'
    curve_sources[state].setdefault(normalized_fingerprint, (capture, test, stroke))
    dx = dy = None
    if dyn and paired:
        try:
            surface = read_dyn(dyn)
            if len(surface) != len(values):
                raise ValueError('Different sample counts')
            dx = max(abs(a[0] - b[0]) for a, b in zip(surface, values))
            dy = max(abs(a[1] - b[1]) for a, b in zip(surface, values))
            if dx > 1e-5 or dy > .05:
                raise ValueError(f'Max difference {dx:.6g} in, {dy:.6g} lbf')
            used_dyn.add(sources[dyn][4])
            reason = 'TXT surface agrees with DYN'
        except (ValueError, OSError, IndexError) as exc:
            review.append([str(path), 'TXT/DYN comparison', str(exc)])
            reason = 'TXT pair, DYN comparison failed'
    stroke_meta[state].append([capture, archive_identity.get(state), test, stroke, len(values), len(values) if paired else 0, reason, dx, dy, prior[0] if prior else None, normalized_fingerprint, str(path), str(dyn) if dyn else None])
    for n, values_at_point in enumerate(values):
        point_rows[state].append([capture, n, *values_at_point, *([None, None] if not paired else [])])


for path, row in sorted(sources.items(), key=lambda item: (item[1][4] not in verified_by_hash, str(item[0]))):
    state, _, extension, _, sha, *_ = row
    if extension != '.txt' or not state or (state, sha) in seen_export:
        continue
    seen_export.add((state, sha))
    try:
        vals = read_paired(path)
        if vals is None:
            continue
        check = verified_by_hash.get(sha)
        alternate = indexed_dyn.get((state, path.stem.casefold()), [])
        known_dyn = Path(check['dyn_path']) if check and check['dyn_path'] else None
        if not alternate and state == 'STATE-077':
            alternate = [p for (s, _), paths in indexed_dyn.items() if s == state for p in paths]
        dyn = known_dyn if known_dyn in sources else next(iter(alternate), None)
        if not check and dyn:
            check = verified_by_dyn.get(sources[dyn][4])
        add_capture(path, state, vals, dyn, check, 'Four-column TXT export; DYN unavailable')
    except (ValueError, OSError, UnicodeError) as exc:
        review.append([str(path), 'Card TXT parse', str(exc)])

for (state, _), paths in indexed_dyn.items():
    for path in paths:
        sha = sources[path][4]
        if not state or sha in used_dyn or (state, sha) in seen_export:
            continue
        seen_export.add((state, sha))
        try:
            add_capture(path, state, read_dyn(path), verification=verified_by_dyn.get(sha), reason='Counted DYN surface export')
        except (ValueError, OSError, IndexError, UnicodeError) as exc:
            review.append([str(path), 'DYN surface export', str(exc)])


pdf_text = defaultdict(list)
equipment = defaultdict(list)
rod_sections = defaultdict(list)
pdf_hashes = set()
equipment_labels = {
    'Manufacturer': ('pumping_unit_manufacturer', None), 'Class': ('pumping_unit_class', None), 'API': ('pumping_unit_api', None),
    'Stroke Length': ('surface_stroke_in', 'in'), 'Polished Rod Diameter': ('polished_rod_diameter_in', 'in'),
    'Pump Intake Depth': ('pump_intake_depth_ft', 'ft'), 'Plunger Diameter': ('plunger_diameter_in', 'in'),
    'Pump Diameter': ('pump_diameter_in', 'in'), 'Pump Type': ('pump_type', None), 'Motor Type': ('motor_type', None),
    'Motor Rating': ('motor_rating_hp', 'HP'), 'Run Time': ('run_time_hr_day', 'hr/day'), 'Rotation': ('surface_unit_rotation', None),
    'Full Load Amps': ('motor_full_load_current_nameplate', None), 'Rated RPM': ('motor_rated_rpm_nameplate', None),
    'Synchronous RPM': ('motor_sync_rpm_nameplate', None), 'Voltage': ('motor_voltage_nameplate', None),
    'Frequency': ('motor_frequency_hz_nameplate', 'Hz'), 'Phase': ('motor_phase_count', None),
}


def extract_equipment(state, page_no, page, path):
    lines = (page.extract_text(extraction_mode='layout') or '').splitlines()
    if not any('Rod String and Pump' in line for line in lines):
        return
    lengths = diameters = []
    for line in lines:
        cells = re.split(r'\s{2,}', line.strip())
        for i, label in enumerate(cells[:-1]):
            if label not in equipment_labels:
                continue
            field, unit = equipment_labels[label]
            reported = cells[i + 1]
            if unit:
                matched = re.fullmatch(r'([+-]?[\d.,]+)\s*' + re.escape(unit), reported, re.I)
                if not matched:
                    continue
                value = float(matched[1].replace(',', ''))
            else:
                value = scalar(reported)
            equipment[state].append([field, value, unit, label, reported, page_no, str(path)])
        if cells[0] in {'Length (ft)', 'Diameter (in)'}:
            vals = [scalar(v) for v in cells[1:]]
            if all(isinstance(v, (int, float)) for v in vals):
                if cells[0] == 'Length (ft)':
                    lengths = vals
                else:
                    diameters = vals
    if diameters and len(lengths) == len(diameters) + 1 and math.isclose(sum(lengths[:-1]), lengths[-1], abs_tol=.1):
        lengths = lengths[:-1]
    if lengths and len(lengths) == len(diameters):
        rod_sections[state].extend([i, length, diameter, page_no, str(path)] for i, (length, diameter) in enumerate(zip(lengths, diameters), 1))


for path, row in sources.items():
    state, _, ext, _, sha, *_ = row
    if ext != '.pdf' or not state or sha in pdf_hashes:
        continue
    pdf_hashes.add(sha)
    try:
        for page_no, page in enumerate(PdfReader(path).pages, 1):
            content = (page.extract_text() or '').strip()
            if not content:
                review.append([str(path), 'PDF has no extractable text', f'Page {page_no}'])
            for line_no, line in enumerate(content.splitlines(), 1):
                if line.strip():
                    pdf_text[state].append([page_no, line_no, line, str(path)])
            if 'Rod String and Pump' in content:
                extract_equipment(state, page_no, page, path)
    except (ValueError, OSError) as exc:
        review.append([str(path), 'PDF extraction', str(exc)])


nk = EXTERNAL / 'nk_well_monitoring/wells_dataset.csv'
nk_units = defaultdict(set)
nk_samples = {}
nk_count = 0
nk_fields = ['SPM', 'pump_fillage', 'min_rod_weight', 'max_rod_weight', 'dynamometer_area', 'tubing_pressure', 'line_pressure', 'casing_pressure']
for row in csv_rows(nk):
    key = (row['well_id'], row['well_type'], row['timestamp'])
    values = nk_samples.setdefault(key, {})
    parameter = row['parameter']
    assert parameter in nk_fields and parameter not in values
    values[parameter] = scalar(row['value'])
    nk_units[parameter].add(row['unit'])
    nk_count += 1
assert nk_count == sum(map(len, nk_samples.values()))
nk_rows = [[*k, *(v.get(p) for p in nk_fields)] for k, v in sorted(nk_samples.items())]


def dated(value):
    return value.isoformat() if isinstance(value, (dt.datetime, dt.date, dt.time)) else value


farha = next(ONEDRIVE.glob('Hourly_Report_*.xlsx'), None)
farha_groups = []
if farha:
    wb = load_workbook(farha, data_only=True, read_only=True)
    for ws in wb:
        rows = list(ws.values)
        tags = next(((i, r) for i, r in enumerate(rows) if 'Wells' in r), None)
        if tags:
            header_index, header = tags
            selected = [i for i, v in enumerate(header) if v is not None]
            well_col = header.index('Wells')
            time_row = next((r for r in rows[:header_index] if 'Time' in r), ())
            date_value = next((v.date() if isinstance(v, dt.datetime) else v for v in time_row if isinstance(v, dt.date)), None)
            time_value = next((v for v in time_row if isinstance(v, dt.time)), None)
            timestamp = dt.datetime.combine(date_value, time_value).isoformat() if date_value and time_value else None
            report_rows = [[i + 1, timestamp, *(dated(r[j]) for j in selected)] for i, r in enumerate(rows[header_index + 1:], header_index + 1) if isinstance(r[well_col], str) and re.match(r'^FS[- ]', r[well_col], re.I)]
            farha_groups.append([f'{ws.title} · local snapshot time as reported · {farha}', ['Source Excel row', 'Source timestamp', *[str(header[j]) for j in selected]], report_rows])
    wb.close()


plos_root = EXTERNAL / 'plos_0326973_s001/normalized_csv'
surface_reference = []
for path in sorted(plos_root.glob('DC*.csv')):
    for index, row in enumerate(csv_rows(path)):
        surface_reference.append([path.stem, index, *[scalar(v) for v in row.values()], 'UNVERIFIED', str(path)])


twm_path = EXTERNAL / 'twm_export_20261117.csv'
with twm_path.open(encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    twm_headers = next(reader)[:-1]
    twm_rows = [[i, r[0], r[1], *(scalar(v) for v in r[2:8])] for i, r in enumerate(reader, 2) if len(r) >= 8 and r[0]]


scada_columns = {
    'site_id': 'SCADA site or field identifier', 'asset_id': 'Plant well or controller asset key', 'tag_id': 'PLC or historian tag address',
    'timestamp_utc': 'Offset-aware historian timestamp', 'quality': 'Historian or sensor quality code', 'operating_state': 'Observed run, stop or trip status',
    'control_mode': 'Local, remote, manual or automatic mode', 'commanded_spm': 'Controller stroke rate setpoint', 'actual_spm': 'Measured stroke rate',
    'vfd_frequency_hz': 'Drive output frequency', 'motor_rpm': 'Measured motor speed', 'voltage_a_v_rms': 'Phase A RMS voltage',
    'voltage_b_v_rms': 'Phase B RMS voltage', 'voltage_c_v_rms': 'Phase C RMS voltage', 'current_a_a_rms': 'Phase A RMS current',
    'current_b_a_rms': 'Phase B RMS current', 'current_c_a_rms': 'Phase C RMS current', 'power_kw': 'Measured motor or VFD active power',
    'power_factor': 'Measured power factor', 'energy_import_kwh': 'Cumulative energy import', 'motor_temperature_c': 'Motor temperature',
    'gearbox_torque_nm': 'Measured gearbox torque', 'vibration_g_rms': 'Vibration RMS and axis per tag definition',
    'tubing_pressure_kpa_g': 'Tubing head gauge pressure', 'casing_pressure_kpa_g': 'Casing head gauge pressure', 'line_pressure_kpa_g': 'Flowline gauge pressure',
    'intake_pressure_kpa_abs': 'Pump intake absolute pressure', 'discharge_pressure_kpa_abs': 'Discharge absolute pressure',
    'liquid_rate_m3_d': 'Measured liquid production rate', 'oil_rate_m3_d': 'Measured oil production rate', 'water_rate_m3_d': 'Measured water production rate',
    'gas_rate_std_m3_d': 'Gas rate at documented standard conditions', 'fluid_level_m': 'Validated distance to liquid', 'alarm_code': 'PLC or SCADA alarm event code',
    'alarm_severity': 'Plant alarm priority', 'alarm_active': 'Current alarm state', 'alarm_acknowledged_utc': 'Alarm acknowledgement time',
}
dyn_columns = {
    'schema_version': 'APM Sample schema version', 'asset_id': 'Registered well asset key', 'site_id': 'Optional site key', 'source': 'Field acquisition source',
    'timestamp': 'Offset-aware time at each sample', 'run_id': 'Stable acquisition session key', 'physics_model_version': 'Optional physics model version; leave empty for field acquisition', 'sequence': 'Monotonic acquisition sequence',
    'stroke_id': 'Source stroke identity', 'sample_index': 'Ordered point within the stroke', 'polished_rod_position_in': 'Calibrated surface position in inches',
    'polished_rod_load_lbf': 'Calibrated surface load in pounds-force', 'crank_angle_deg': 'Phase-registered crank angle in degrees',
    'spm': 'Stroke rate of this acquisition', 'quality': 'GOOD, DEGRADED or BAD per ingest contract', 'sensor_id': 'Installed sensor identity',
    'calibration_id': 'Calibration record identifier', 'calibration_date': 'Calibration completion timestamp', 'load_uncertainty_lbf': 'Load uncertainty',
    'position_uncertainty_in': 'Position uncertainty', 'acquisition_method': 'Device and capture method', 'units': 'Unit declaration per sample contract',
}
apm_columns = {
    'asset_id': 'Registered well asset key', 'run_id': 'Matched acquisition session', 'stroke_id': 'Matched stroke', 'test_id': 'Historical test cross-reference',
    'card_timestamp_utc': 'Verified card capture time', 'surface_card_id': 'Ordered surface card source', 'pump_card_id': 'Ordered pump card source',
    'pump_card_origin': 'Measured, vendor-derived or APM reconstructed', 'solver_version': 'APM solver build', 'solver_status': 'Reconstruction status',
    'fillage_pct': 'Verified or explicitly estimated pump fillage', 'peak_load_lbf': 'Peak surface polished rod load', 'min_load_lbf': 'Minimum surface polished rod load',
    'surface_stroke_in': 'Surface travel', 'pump_stroke_in': 'Downhole plunger travel', 'pump_intake_pressure_kpa_abs': 'Pump intake absolute pressure',
    'pump_displacement_m3_d': 'Pump displacement per day', 'gearbox_torque_nm': 'Gearbox torque', 'rod_loading_pct_goodman': 'Rod loading against Goodman limit',
    'fault_code': 'Adjudicated condition or separately sourced prediction', 'fault_status': 'Source and verification of condition', 'confidence': 'Prediction confidence',
    'alarm_code': 'Related alarm or event', 'maintenance_event_id': 'Matched inspection or repair ID', 'confirmed_by': 'Field reviewer identity',
    'pump_depth_m': 'Verified pump depth', 'plunger_diameter_m': 'Verified plunger diameter', 'pump_unit_model': 'Installed pumping unit model',
    'rod_taper': 'Ordered rod sections and dimensions', 'tubing_anchor_status': 'Confirmed installation state', 'fluid_density_kg_m3': 'Verified fluid density',
    'damping_s': 'Calibrated APM damping parameter', 'crank_m': 'Verified crank geometry', 'rocker_m': 'Verified rocker geometry',
    'pitman_m': 'Verified pitman geometry', 'pivot_x_m': 'Verified pivot x', 'pivot_y_m': 'Verified pivot y',
}


def section(label, headers, rows):
    return [label, list(headers), list(rows)]


def sheet(name, subtitle, sections):
    return [name, subtitle, sections]


well_header = ['TAM well ID', 'Well name', 'Company', 'Major group', 'Minor group', 'GPS block', 'Description', 'Saved app version', 'Original well metadata (JSON)', 'Source TAM archive']
test_header = ['TAM test key', 'TAM well ID', 'Well name', 'Test type', 'Test timestamp as exported', 'Modified timestamp', 'Archive ordinal', 'TAM version', 'Numeric fields', 'Text fields', 'Source TAM archive', *TAM_FIELDS]
parameter_header = ['TAM test key', 'Vendor parameter', 'Value type', 'Source value', 'Unit status', 'Source TAM archive']
meta_header = ['Capture ID', 'TAM well ID candidate', 'Test token as exported', 'Stroke ID', 'Surface points', 'Pump points', 'Card evidence', 'Surface position delta (in)', 'Surface load delta (lbf)', 'Duplicate curve reference', 'Curve digest', 'TXT or DYN source', 'Companion DYN source']
point_header = ['Capture ID', 'sample_index', 'polished_rod_position_in', 'polished_rod_load_lbf', 'vendor_pump_position_in', 'vendor_pump_load_lbf']
member_header = ['TAM well ID', 'Member type', 'Member path', 'Bytes', 'CRC-32', 'Source TAM archive']
pdf_header = ['PDF page', 'Extracted line', 'Report text', 'Source PDF']
asset_header = ['Collection', 'Extension', 'Bytes', 'SHA-256', 'Source path', 'Identical file already listed at']

sheets = []
coverage = []
for state in [*catalog, *(['Unmapped'] if test_rows['Unmapped'] else [])]:
    state_name = catalog.get(state) or 'Source identity unresolved'
    paired_count = sum(bool(r[5]) for r in stroke_meta[state])
    audit = label_audit.get(state, {})
    coverage.append([state, state_name, len(well_rows[state]), len(test_rows[state]), len(parameters[state]), len(stroke_meta[state]), paired_count, len(point_rows[state]), len(pdf_text[state]), len(native_members[state]), audit.get('field_confirmed_diagnosis', 'Unverified')])
    blocks = [section('Coverage and label evidence', ['Field', 'Value'], [
        ['Original example name', state_name], ['TAM test records', len(test_rows[state])], ['Card captures', len(stroke_meta[state])], ['Surface and pump pairs', paired_count],
        ['Provider comment', audit.get('provider_comment')], ['Field-confirmed diagnosis', audit.get('field_confirmed_diagnosis', 'Unverified')], ['Training permission', audit.get('training_permission', 'Unverified')],
    ])]
    for title, headings, payload in [
        ('TAM well metadata', well_header, well_rows[state]), ('TAM test-level SCADA and APM fields · vendor units', test_header, test_rows[state]),
        ('All original TAM test parameters', parameter_header, parameters[state]), ('Card captures and raw source links', meta_header, stroke_meta[state]),
        ('Ordered vendor dynacard samples', point_header, point_rows[state]),
        ('Equipment values reported in Echometer PDF', ['Field', 'Source value', 'Explicit unit', 'Original report label', 'Report text value', 'PDF page', 'Source PDF'], equipment[state]),
        ('Rod string sections from Echometer PDF', ['Section', 'Length (ft)', 'Diameter (in)', 'PDF page', 'Source PDF'], rod_sections[state]),
        ('Echometer report text with original units', pdf_header, pdf_text[state]),
        ('Native TAM members · numerical samples need supported vendor export', member_header, native_members[state]), ('Original file references', asset_header, assets[state]),
    ]:
        if payload:
            blocks.append(section(title, headings, payload))
    if state == 'STATE-077':
        config = json.loads((DATA / 'state93/pilot/Tagging Down Hard/normalized/engineering_config.json').read_text())['verified_pdf']
        src = next((r[5] for p, r in sources.items() if r[0] == state and 'summary.pdf' in p.name.lower()), None)
        blocks.append(section('Reviewed equipment values from field summary', ['pump_intake_depth_ft', 'surface_unit', 'stroke_in', 'plunger_diameter_in', 'Rod sections (length ft and diameter in)', 'Source PDF'], [[config['pump_intake_depth_ft'], config['surface_unit'], config['stroke_in'], config['plunger_diameter_in'], encoded(config['rod_sections_ft_diameter_in']), src]]))
    sheets.append(sheet(state, state_name, blocks))


schema = [[group, f, meaning] for group, cols in [('SCADA telemetry and alarms', scada_columns), ('Dynacard creation', dyn_columns), ('APM asset and diagnostic', apm_columns)] for f, meaning in cols.items()]
mapping_rows = [[name, 'TAM test results', ' / '.join(aliases), 'Historical test-level value. Vendor unit or pressure basis unverified unless stated.'] for name, aliases in TAM_FIELDS.items()]
mapping_rows += [
    ['polished_rod_position_in / polished_rod_load_lbf', 'TAM TXT / DYN', 'Surface card position and load', 'TXT klbf × 1000; DYN observed in lbf. Ordered sample values.'],
    ['vendor_pump_position_in / vendor_pump_load_lbf', 'TAM TXT', 'Pump Card Position / Pump Card Load', 'Vendor-derived pump card. TXT klbf × 1000.'],
    ['timestamp / crank_angle_deg / quality', 'TAM TXT / DYN', None, 'No point-level timing, synchronized crank angle or historian quality exported.'],
    ['asset_id / run_id / stroke_id', 'SCADA ↔ dynacards ↔ APM', None, 'Assign from the site source. Keep historical card capture IDs separate until the site verifies the crosswalk.'],
    ['fault_code / confidence', 'TAM example labels and comments', None, 'Example names and comments are reference context. No independent diagnosis or model outputs were imported.'],
    ['motor_temperature_c', 'Farha hourly report', 'Motor temp', 'Temperature unit indicated by source header. Preserve exact sentinel values in the source sheet.'],
    ['vfd_frequency_hz / vfd_run_status', 'Farha hourly report', 'Frequency / VFD STS', 'Frequency scaling and VFD status semantics require the site tag dictionary.'],
    ['intake_pressure_kpa_abs / discharge_pressure_kpa_abs', 'Farha hourly report', 'Inp bar/psi / Disch pr. Bar/psi', 'Mixed source units and pressure basis unresolved. Original values remain in Farha SCADA.'],
    ['tubing_pressure / line_pressure / casing_pressure', 'NK hourly', 'Same source column names', 'Source atmospheres and pressure basis retained. Pressure data is from fountain wells in this collection.'],
]

apm_reference = []
for state, captures in stroke_meta.items():
    by_capture = defaultdict(list)
    for p in point_rows[state]:
        by_capture[p[0]].append(p)
    for cap in captures:
        cid, source_well, test, stroke, _, pumps, evidence = cap[:7]
        samples = by_capture[cid]
        x, y = [p[2] for p in samples], [p[3] for p in samples]
        u = [p[4] for p in samples] if pumps else []
        record = {
            'stroke_id': stroke, 'test_id': test, 'surface_card_id': cid,
            'pump_card_id': cid if pumps else None, 'pump_card_origin': 'Vendor calculated' if pumps else None,
            'peak_load_lbf': max(y), 'min_load_lbf': min(y), 'surface_stroke_in': max(x) - min(x),
            'pump_stroke_in': max(u) - min(u) if u else None, 'fault_status': 'Field diagnosis unconfirmed',
        }
        apm_reference.append([state, source_well, evidence, *(record.get(k) for k in apm_columns)])

sheets[0:0] = [
    sheet('Coverage', 'SRP field and vendor master dataset', [
        section('Coverage by operating example', ['Worksheet', 'Example name', 'Well records', 'TAM tests', 'TAM parameters', 'Card captures', 'Paired captures', 'Ordered points', 'PDF text lines', 'Native archive members', 'Field diagnosis confirmed'], coverage),
        section('Source boundaries', ['Source', 'Use'], [
            ['TAM and TWM', 'Vendor examples and reports. Preserve source values and timestamps. Card acquisition history and test summaries remain separate where their time bases or IDs differ.'],
            ['Farha SCADA', 'Real site report snapshot. The tags are preserved with original placeholders and mixed unit labels. Lift type and crosswalk to SRP cards are unverified.'],
            ['NK hourly data', 'Provider claims field origin. Useful as hourly reference. Timezone and year are unverified. Fills and rod weights are provider summary fields.'],
            ['PLOS surface cards', 'Four research surface cards described as measured. Units, well IDs and test times are unknown. Electrical companion files have unresolved measured/generated origin.'],
            ['LA-0024', 'Restricted reference. Surface numerical files remain linked at their local paths. Downhole arrays failed source review.'],
            ['TAM pump card', 'Vendor-calculated from surface measurements. Pump values are kept under their own column names.'],
            ['Live ingestion', 'Schema tabs contain the data contract for future field collection. Existing sources lack a full synchronized SCADA → dynacard → APM acquisition.'],
        ]),
    ]),
    sheet('Field schema', 'SCADA, dynacard and APM dashboard input fields', [section('Canonical field names and meanings', ['Consumer', 'Column', 'Meaning'], schema), section('Collected-source mapping', ['Target or vendor field', 'Source', 'Original field', 'Handling'], mapping_rows)]),
    sheet('SCADA input', 'Site historian and live operations input', [section(None, scada_columns, [])]),
    sheet('Dynacard input', 'Ordered surface acquisition input for the APM Sample contract', [section(None, dyn_columns, [])]),
    sheet('APM input', 'Historical card inputs · asset mapping and site validation pending', [section(None, ['catalog_state_id', 'vendor_well_id_candidate', 'evidence', *apm_columns], apm_reference)]),
]

if farha_groups:
    sheets.append(sheet('Farha SCADA', 'Farha historical site snapshot · equipment and units as reported', farha_groups))
sheets += [
    sheet('NK hourly', 'NK monitoring · field measurement claim unverified', [section(None, ['well_id', 'well_type', 'source_timestamp', *[f'{p} ({" / ".join(sorted(nk_units[p]))})' for p in nk_fields]], nk_rows)]),
    sheet('TWM test summaries', 'Historical TWM summary export · header and scale under review', [section(None, ['Source CSV row', *twm_headers], twm_rows)]),
    sheet('PLOS surface reference', 'PLOS S1 surface dynamometer data · source units unverified', [section(None, ['Card file', 'sample_index', 'Position as reported', 'Load as reported', 'Unit status', 'Source CSV'], surface_reference)]),
]

reference_docs = [
    ['Farha site snapshot', str(farha) if farha else None, 'Source workbook. Sentinel values and status cells retained.'],
    ['NK source CSV', str(nk), f'{nk_count} parameter observations pivoted to {len(nk_rows)} well-hour rows. Source unit retained by column.'],
    ['TWM vendor CSV', str(twm_path), 'Source header and values preserved because scale/field alignment is under review.'],
    ['PLOS S1 attribution', str(EXTERNAL / 'plos_0326973_s001/ATTRIBUTION.md'), 'Li X, Liu Z, Yuan C, Liao Z. PLOS ONE 2025. doi:10.1371/journal.pone.0326973. CC BY 4.0.'],
    ['LA-0024 raw data and provenance', str(EXTERNAL / 'production_optimization/PROVENANCE.json'), 'Restricted local reference. 76 source-claimed surface cards, 10,119 trace points. Unit status unverified.'],
    ['CUPBJJB examples', str(EXTERNAL / 'cupbjj_dynamometer_card/PROVENANCE.json'), 'Origin and unit claims unverified. Source paths retained for review.'],
    ['Everitt example', str(EXTERNAL / 'chuymtz_dynacard_source/PROVENANCE.json'), 'Surface trace origin unresolved. Source path retained for review.'],
    ['Downloads telemetry', str(DOWNLOADS / 'srp-telemetry.csv'), 'Simulator exports excluded.'],
    ['Disputed-origin electrical references', str(plos_root), 'ED1–ED4 excluded because measured/generated origin is unresolved.'],
    ['Catalog', str(catalog_path), 'State identity reference.'],
    ['APM Sample and Well contract', str(PROJECT / 'shared/contracts.py'), 'Reference for column names, data types and engineering inputs.'],
]
sheets += [
    sheet('Source index', 'Collected source assets and reference boundaries', [section('Source notes', ['Item', 'Source path', 'Use'], reference_docs), section('Scanned directories', ['Collection', 'Directory', 'Files indexed', 'Status'], scope), section('Native source files', ['State', *asset_header], sources.values())]),
    sheet('Import review', 'Extraction and source quality review', [section(None, ['Source or state', 'Issue', 'Evidence'], review)]),
]

for name, title, blocks in sheets:
    for label, headers, rows in blocks:
        for row in rows:
            if len(row) != len(headers):
                raise ValueError(f'Column mismatch in {name} / {label}: {len(row)} vs {len(headers)}')
            if any(isinstance(v, str) and len(v) > 32767 for v in row):
                raise ValueError(f'Excel cell limit in {name} / {label}')

stats = {
    'sheets': len(sheets), 'tam_states': sum(bool(v) for v in test_rows.values()), 'tam_tests': sum(map(len, test_rows.values())),
    'tam_parameters': sum(map(len, parameters.values())), 'card_states': sum(bool(v) for v in stroke_meta.values()),
    'card_captures': sum(map(len, stroke_meta.values())), 'paired': sum(sum(bool(r[5]) for r in v) for v in stroke_meta.values()),
    'verified_pairs': sum(sum(r[6] == 'TXT surface agrees with DYN' for r in v) for v in stroke_meta.values()),
    'point_rows': sum(map(len, point_rows.values())), 'pdf_lines': sum(map(len, pdf_text.values())),
    'equipment_fields': sum(map(len, equipment.values())), 'rod_sections': sum(map(len, rod_sections.values())),
    'farha': sum(len(row[2]) for row in farha_groups), 'nk_observations': nk_count, 'nk_well_hours': len(nk_rows), 'plos_points': len(surface_reference),
    'twm_summary_rows': len(twm_rows), 'sources': len(sources), 'review': len(review),
}
print(stats)
print('Review examples', review[:8])
(OUT / 'field_stage.json').write_text(json.dumps(sheets, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
