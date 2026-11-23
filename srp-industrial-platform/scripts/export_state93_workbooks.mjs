import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const report = path.resolve('reports/STATE93');
const names = [
  '93_STATE_COMPATIBILITY_MATRIX',
  '93_STATE_NUMERICAL_INVENTORY',
  '93_STATE_ENGINEERING_INPUT_GAPS',
  '93_STATE_DYNACARD_VALIDATION',
  '93_STATE_CONVERSION_LOG',
];
for (const name of names) {
  const csv = await fs.readFile(path.join(report, `${name}.csv`), 'utf8');
  const book = await Workbook.fromCSV(csv, { sheetName: 'State93' });
  book.recalculate();
  const xlsx = await SpreadsheetFile.exportXlsx(book);
  await xlsx.save(path.join(report, `${name}.xlsx`));
  process.stdout.write(`${name}.xlsx\n`);
}
