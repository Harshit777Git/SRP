import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../reports/PHASE3_1');
const names=['MQTT_STABILITY','FLEET_PHYSICS_VALIDATION','QROD_ENGINEERING_COMPARISON',
  'FAULT_OBSERVABILITY','DATASET_INVENTORY','ML_READINESS_MATRIX'];
function col(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
for(const name of names){
  const rows=JSON.parse(await fs.readFile(path.join(root,'tables',name+'.json'),'utf8'));
  const keys=[...new Set(rows.flatMap(row=>Object.keys(row)))];
  const wb=Workbook.create();const sheet=wb.worksheets.add(name.replaceAll('_',' ').slice(0,31));
  sheet.showGridLines=false;
  const matrix=[keys,...rows.map(row=>keys.map(key=>{
    const value=row[key];return value==null?'':typeof value==='object'?JSON.stringify(value):value;
  }))];
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).values=matrix;
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0,0,1,keys.length).format.fill='#143047';
  sheet.getRangeByIndexes(0,0,1,keys.length).format.font={name:'Aptos',size:11,bold:true,color:'#FFFFFF'};
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).format.rowHeight=22;
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).format.columnWidth=26;
  keys.forEach((key,i)=>sheet.getRangeByIndexes(0,i,matrix.length,1).format.columnWidth=
    /path|sha256|status|error|source|test|gate|decision|units/i.test(key)?43:26);
  sheet.tables.add(`A1:${col(keys.length)}${matrix.length}`,true,`Table${name.replace(/[^A-Za-z0-9]/g,'')}`);
  wb.recalculate();const artifact=await SpreadsheetFile.exportXlsx(wb);
  await artifact.save(path.join(root,name+'.xlsx'));
  console.log(name+'.xlsx',rows.length);
}
