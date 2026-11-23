import csv
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

out = Path('srp-industrial-platform/outputs/01a1f1fd-6501-7a40-89e3-df4b424daa3b/field')
book_spec = json.loads((out / 'field_stage.json').read_text(encoding='utf-8'))
ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
rel = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def column_name(index):
    result = ''
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


count = 0
with zipfile.ZipFile(out / 'SRP_Real_Data_Master.xlsx') as z:
    assert z.testzip() is None
    shared_names = 'xl/sharedStrings.xml'
    shared = [''.join(t.text or '' for t in node.iter(ns + 't')) for node in ET.fromstring(z.read(shared_names))] if shared_names in z.namelist() else []
    book = ET.fromstring(z.read('xl/workbook.xml'))
    targets = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    actual_sheets = list(book.iter(ns + 'sheet'))
    assert [sh.attrib['name'] for sh in actual_sheets] == [x[0] for x in book_spec]
    assert len([s for s in book_spec if s[0].startswith('STATE-')]) == 96
    assert not any(s[0].startswith('DT') for s in book_spec)

    for tab, (tab_name, title, blocks) in zip(actual_sheets, book_spec, strict=True):
        target = targets[tab.attrib[rel + 'id']]
        source = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheet = ET.fromstring(z.read(source))
        cells = {c.attrib['r']: c for c in sheet.iter(ns + 'c')}

        def compare(address, wanted):
            global count
            cell = cells.get(address)
            if cell is None:
                assert wanted is None or wanted == '', (tab_name, address, str(wanted)[:120])
                return
            kind = cell.get('t')
            value = cell.findtext(ns + 'v')
            assert kind != 'e', (tab_name, address, value)
            if kind == 's':
                actual = shared[int(value)]
            elif kind == 'inlineStr':
                actual = ''.join(t.text or '' for t in cell.iter(ns + 't'))
            elif kind == 'b':
                actual = value == '1'
            elif kind == 'd':
                assert datetime.fromisoformat(value) == datetime.fromisoformat(wanted), (tab_name, address, value, wanted)
                count += 1
                return
            elif value is None:
                actual = None
            elif isinstance(wanted, (int, float)) and type(wanted) is not bool:
                assert math.isclose(float(value), wanted, abs_tol=1e-14, rel_tol=1e-14), (tab_name, address, value, wanted)
                count += 1
                return
            else:
                actual = value
            assert (actual == wanted and type(actual) is type(wanted)) or (actual is None and wanted == ''), (tab_name, address, str(actual)[:155], str(wanted)[:155])
            count += 1

        compare('A1', title)
        cursor = 3
        for label, headers, rows in blocks:
            if label:
                compare(f'A{cursor}', label)
                cursor += 1
            columns = [column_name(i) for i in range(1, len(headers) + 1)]
            for line, row in enumerate([headers, *rows], cursor):
                for col, expected in zip(columns, row, strict=True):
                    compare(f'{col}{line}', expected)
            cursor += len(rows) + 2

spec = {x[0]: x[2] for x in book_spec}
source_nk = Path('srp-industrial-platform/data/external_reference/nk_well_monitoring/wells_dataset.csv')
_, headers, observations = spec['NK hourly'][0]
matrix = {tuple(row[:3]): row[3:] for row in observations}
original_columns = {'SPM': 0, 'pump_fillage': 1, 'min_rod_weight': 2, 'max_rod_weight': 3, 'dynamometer_area': 4, 'tubing_pressure': 5, 'line_pressure': 6, 'casing_pressure': 7}
observations_checked = 0
with source_nk.open(encoding='utf-8-sig', newline='') as stream:
    for r in csv.DictReader(stream):
        k = tuple(r[x] for x in ('well_id', 'well_type', 'timestamp'))
        assert matrix[k][original_columns[r['parameter']]] == float(r['value'])
        observations_checked += 1
assert observations_checked == sum(v is not None for row in observations for v in row[3:]) == 186251
by_state = spec['Coverage'][0][2]
assert sum(r[3] for r in by_state) == 136
assert sum(r[5] for r in by_state) == 42
assert sum(r[6] for r in by_state) == 41
assert len(spec['Farha SCADA'][0][2]) == 59
assert len(spec['APM input'][0][2]) == 42
assert [r[1] for r in spec['Farha SCADA'][0][2][:3]] == ['2025-12-31T23:59:57'] * 3
print(f'Verified {len(actual_sheets)} tabs, {count:,} exported cells, and {observations_checked:,} NK observations against the original CSV.')
