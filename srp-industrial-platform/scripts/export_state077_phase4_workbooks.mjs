import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const directory=path.resolve('reports/STATE93');
for(const name of ['STATE077_SOLVER_COMPARISON','STATE077_PARAMETER_SENSITIVITY','STATE93_SCALEOUT_READINESS']){
  const csv=await fs.readFile(path.join(directory,name+'.csv'),'utf8');
  const book=await Workbook.fromCSV(csv,{sheetName:'Evidence'});
  book.recalculate();
  const file=await SpreadsheetFile.exportXlsx(book);
  await file.save(path.join(directory,name+'.xlsx'));
  process.stdout.write(name+'.xlsx\n');
}
