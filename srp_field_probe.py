import collections
import json
import pathlib
import zipfile
from pypdf import PdfReader
from openpyxl import load_workbook

root = pathlib.Path.cwd()
home = pathlib.Path.home()
downloads = home / 'Downloads'
desktop = root.parent
project = root / 'srp-industrial-platform'
for p in (desktop / 'TAM Data.TAM_EXP', *list((project / 'data/state93/STATE-006/01_TAM').glob('*'))):
    with zipfile.ZipFile(p) as z:
        print(p, collections.Counter(n.split('/')[0] for n in z.namelist()).most_common(8))
        wells = json.loads(z.read('TestResults.json')).get('Wells', [])
        print([(w.get('Name'), len(w.get('Tests', []))) for w in wells][:3]); print(z.namelist()[:17])
        for sample in [next((n for n in z.namelist() if x in n), None) for x in ('.{HEADER}', '/Versions/', '/Tests/DYN.')]:
            if sample: print(sample, repr(z.read(sample)[:210]))
        for name in z.namelist()[:12]:
            if name.lower().endswith('.json') and name != 'TestResults.json':
                obj = json.loads(z.read(name)); print(name, str([(k, str(v)[:110]) for k,v in obj.items()])[:950])
for p in [downloads / 'HTDS.xlsx', home / 'OneDrive - TAS/Hourly_Report_639046_2025_12_31T20_00_00_000.xlsx']:
    if p.exists():
        w = load_workbook(p, read_only=True, data_only=True)
        for s in w:
            print(p.name, s.title, s.max_row, s.max_column, [r for r in s.iter_rows(min_row=1, max_row=11, values_only=True) if any(x is not None for x in r)][:3])
            if p.name.startswith('Hourly'):
                for i,r in enumerate(s.values,1):
                    if any(v is not None for v in r): print(i, [v for v in r if v is not None][:17]);
for p in sorted(downloads.glob('*_Summary.pdf'))[:2]:
    print(p, (PdfReader(p).pages[1].extract_text() or '')[:4500])
