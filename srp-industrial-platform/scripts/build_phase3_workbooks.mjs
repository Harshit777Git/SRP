import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const dir=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../reports/PHASE3');
const files=[
  ['ECHOMETER_EXTRACTION_INVENTORY','Echometer Sources'],
  ['QROD_BENCHMARK_RESULTS','QRod Benchmark'],
  ['SRP_30_WELL_CONFIGURATION','Thirty Wells'],
  ['SIMULATION_PHYSICS_VALIDATION','Physics Validation'],
  ['FAULT_SIGNATURE_SEPARABILITY','Fault Distances'],
  ['WAVE_EQUATION_VALIDATION','Wave Validation'],
  ['MQTT_MULTIWELL_BENCHMARK_TABLE','MQTT Benchmark'],
  ['SIMULATION_DATASET_CATALOG','Dataset Catalog'],
  ['ML_INPUT_READINESS','ML Readiness'],
];
function col(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
for(const [base,title] of files){
  const rows=JSON.parse(await fs.readFile(path.join(dir,base+'.json'),'utf8'));
  const keys=[...new Set(rows.flatMap(row=>Object.keys(row)))];
  const wb=Workbook.create();
  const sheet=wb.worksheets.add(title);
  sheet.showGridLines=false;
  const values=[keys,...rows.map(row=>keys.map(key=>{
    const value=row[key];return value==null?'':typeof value==='object'?JSON.stringify(value):value;
  }))];
  sheet.getRangeByIndexes(0,0,values.length,keys.length).values=values;
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0,0,1,keys.length).format.fill='#143047';
  sheet.getRangeByIndexes(0,0,1,keys.length).format.font={name:'Aptos',size:11,bold:true,color:'#FFFFFF'};
  sheet.getRangeByIndexes(0,0,values.length,keys.length).format.rowHeight=22;
  sheet.getRangeByIndexes(0,0,values.length,keys.length).format.columnWidth=25;
  keys.forEach((key,i)=>sheet.getRangeByIndexes(0,i,values.length,1).format.columnWidth=
    /path|sha256|status|reason|error|rods|source|member/i.test(key)?45:25);
  sheet.tables.add(`A1:${col(keys.length)}${values.length}`,true,`Table${base.replace(/[^A-Za-z0-9]/g,'')}`);
  wb.recalculate();
  const out=await SpreadsheetFile.exportXlsx(wb);
  const target=path.join(dir,base.replace('_TABLE','')+'.xlsx');
  await out.save(target);
  console.log(path.basename(target),rows.length);
}
