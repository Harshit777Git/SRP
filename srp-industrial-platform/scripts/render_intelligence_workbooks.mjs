import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dir=path.join(root,'reports');
await fs.mkdir(path.join(dir,'_preview'),{recursive:true});
for(const name of ['SRP_MASTER_DATA_DICTIONARY.xlsx','SRP_DATASET_INVENTORY.xlsx','SRP_FAULT_LABEL_COVERAGE.xlsx','SRP_FEATURE_ENGINEERING_CATALOG.xlsx','SRP_MODEL_FEASIBILITY_MATRIX.xlsx']){
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(dir,name)));
  const sheet=wb.worksheets.getItemAt(0);
  const image=await wb.render({sheetName:sheet.name,range:'A1:E10',scale:1,format:'png'});
  await fs.writeFile(path.join(dir,'_preview',name+'.png'),new Uint8Array(await image.arrayBuffer()));
  console.log(name,sheet.name);
}
