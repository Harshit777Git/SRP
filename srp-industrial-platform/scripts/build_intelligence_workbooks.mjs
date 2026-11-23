import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const reports=path.join(root,'reports');
const outputs=[
  ['SRP_MASTER_DATA_DICTIONARY.xlsx','SRP_COLUMN_PROFILING.json','Column Dictionary'],
  ['SRP_DATASET_INVENTORY.xlsx','SRP_DATASET_INVENTORY.json','Dataset Inventory'],
  ['SRP_FAULT_LABEL_COVERAGE.xlsx','SRP_FAULT_LABEL_COVERAGE.json','Fault Labels'],
  ['SRP_FEATURE_ENGINEERING_CATALOG.xlsx','SRP_FEATURE_ENGINEERING_CATALOG.json','Feature Catalog'],
  ['SRP_MODEL_FEASIBILITY_MATRIX.xlsx','SRP_MODEL_FEASIBILITY_MATRIX.json','Model Feasibility'],
];
for(const [name,input,tab] of outputs){
  const rows=JSON.parse(await fs.readFile(path.join(reports,input),'utf8'));
  const excluded=new Set(['value_counts','histogram']);
  const keys=[...new Set(rows.flatMap(row=>Object.keys(row).filter(k=>!excluded.has(k))))];
  const wb=Workbook.create();
  const sheet=wb.worksheets.add(tab);
  sheet.showGridLines=false;
  const matrix=[keys,...rows.map(row=>keys.map(k=>{
    const v=row[k];return v===undefined||v===null?'':typeof v==='object'?JSON.stringify(v):v;
  }))];
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).values=matrix;
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0,0,1,keys.length).format.fill='#143047';
  sheet.getRangeByIndexes(0,0,1,keys.length).format.font={name:'Aptos',size:11,bold:true,color:'#FFFFFF'};
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).format.rowHeight=22;
  sheet.getRangeByIndexes(0,0,matrix.length,keys.length).format.columnWidth=23;
  keys.forEach((key,index)=>{
    const width=/path|reason|meaning|description|formula|required|notes|blocker|validation|source_url/i.test(key)?49
      :/origin|permission|status|dataset_id|original_column_name|candidate_faults/i.test(key)?35
      :/source|fault_name|feature_id|model_id/i.test(key)?31:23;
    sheet.getRangeByIndexes(0,index,matrix.length,1).format.columnWidth=width;
  });
  sheet.tables.add(`A1:${columnName(keys.length)}${matrix.length}`,true,`Table${tab.replace(/\W/g,'')}`);
  wb.recalculate();
  const file=await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(reports,name));
  console.log(`${name}: ${rows.length} rows, ${keys.length} columns`);
}

function columnName(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
