import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const [packages, directory, previewOnly] = process.argv.slice(2);
const require = createRequire(path.join(packages, 'package.json'));
const { Workbook, SpreadsheetFile } = require('@oai/artifact-tool');
const fullSpecification = JSON.parse(await fs.readFile(path.join(directory, 'field_stage.json'), 'utf8'));
const specification = previewOnly ? fullSpecification.filter(([name]) => ['Field schema', 'NK hourly', 'APM input'].includes(name)).map(([name, title, blocks]) => [name, title, blocks.map(([label, headers, rows]) => [label, headers, rows.slice(0, 20)])]) : fullSpecification;
const workbook = Workbook.create();

for (const [name, title, blocks] of specification) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const titleRange = sheet.getRange('A1:E1');
  titleRange.merge();
  sheet.getRange('A1').values = [[title]];
  titleRange.format.fill = '#172F40';
  titleRange.format.font = { color: '#FFFFFF', size: 15, bold: true };
  titleRange.format.rowHeight = 28;
  const isState = /^STATE-/.test(name);
  sheet.freezePanes.freezeRows(isState || name === 'Coverage' ? 1 : blocks[0][0] ? 4 : 3);

  let line = 2;
  let columnCount = 0;
  for (const [section, headers, rows] of blocks) {
    columnCount = Math.max(columnCount, headers.length);
    if (section) {
      const sectionRange = sheet.getRangeByIndexes(line, 0, 1, Math.min(6, Math.max(headers.length, 2)));
      sectionRange.merge();
      sheet.getRangeByIndexes(line, 0, 1, 1).values = [[section]];
      sectionRange.format.fill = '#DFEEF0';
      sectionRange.format.font = { color: '#172F40', bold: true };
      sectionRange.format.rowHeight = 22;
      line += 1;
    }
    const header = sheet.getRangeByIndexes(line, 0, 1, headers.length);
    header.values = [headers];
    header.format.fill = '#265A65';
    header.format.font = { color: '#FFFFFF', bold: true, size: 10 };
    header.format.wrapText = true;
    header.format.rowHeight = 36;
    line += 1;
    if (rows.length) {
      headers.forEach((label, column) => {
        if (/timestamp|utc$|source value|metadata \(JSON\)|test token|report text|report label|CRC-32/i.test(label)) {
          sheet.getRangeByIndexes(line, column, rows.length, 1).setNumberFormat('@');
        }
      });
      for (let i = 0; i < rows.length; i += 600) {
        const batch = rows.slice(i, i + 600);
        sheet.getRangeByIndexes(line + i, 0, batch.length, headers.length).values = batch;
      }
    }
    line += rows.length + 1;
  }
  for (let column = 0; column < columnCount; column++) {
    let width = isState ? ([31, 37, 35, 28, 35, 33, 39, 31, 31, 31, 50, 55, 55][column] ?? 24) : 25;
    if (name === 'NK hourly') width = [15, 24, 26, 22, 22, 22, 22, 24, 22, 22, 22][column];
    if (name === 'Coverage') width = [22, 43, 18, 18, 18, 18, 18, 19, 20, 21, 28][column];
    if (name === 'Field schema') width = [33, 43, 70, 58][column];
    if (name === 'Source index') width = [33, 56, 65, 20, 47, 65, 65][column];
    if (name === 'Farha SCADA') width = [19, 34, 17][column] ?? 19;
    if (name === 'Import review') width = [39, 42, 75][column];
    sheet.getRangeByIndexes(0, column, 1, 1).format.columnWidth = width;
  }
}

workbook.recalculate();
if (!previewOnly) {
  const check = await workbook.inspect({ kind: 'table', range: 'Coverage!A3:K13', include: 'values', tableMaxRows: 11, tableMaxCols: 11 });
  console.log(check.ndjson);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  const finalPath = path.join(directory, 'SRP_Real_Data_Master.xlsx');
  await output.save(finalPath);
  console.log(`Workbook saved to ${finalPath}`);
}
const ranges = [['Coverage', 'A1:K11'], ['Field schema', 'A1:E12'], ['STATE-006', 'A1:F12'], ['STATE-077', 'A1:F12'], ['Farha SCADA', 'A1:G10'], ['NK hourly', 'A1:K10'], ['APM input', 'A1:K10']];
for (const [name, range] of ranges.filter(([name]) => specification.some(([sheet]) => sheet === name))) {
  try {
    const preview = await workbook.render({ sheetName: name, range, scale: .85 });
    await fs.writeFile(path.join(directory, `preview-${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  } catch (error) {
    console.log(`Preview ${name}: ${error.message}`);
  }
}
