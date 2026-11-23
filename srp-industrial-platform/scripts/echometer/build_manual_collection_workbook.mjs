import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const dependencyRoot = process.argv[2];
const inventoryPath = process.argv[3];
const outputPath = process.argv[4];
if (!dependencyRoot || !inventoryPath || !outputPath) {
  throw new Error("Usage: node builder.mjs <dependency-node_modules> <inventory.json> <output.xlsx>");
}
const require = createRequire(path.join(dependencyRoot, "package.json"));
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");
const inventory = JSON.parse(await fs.readFile(inventoryPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const queue = workbook.worksheets.add("Manual Queue");
const checklist = workbook.worksheets.add("State Checklist");
const workflow = workbook.worksheets.add("Workflow");
const copied = workbook.worksheets.add("Collected Files");
const font = "Arial";
const colors = {
  dark: "#1F4E78", blue: "#D9EAF7", green: "#E2F0D9",
  red: "#FCE4D6", amber: "#FFF2CC", gray: "#E7E6E6",
};

function title(sheet, address, text) {
  sheet.getRange(address).merge();
  const cell = sheet.getRange(address.split(":")[0]);
  cell.values = [[text]];
  cell.format.font = { name: font, size: 15, bold: true, color: "#1F1F1F" };
}
function header(range) {
  range.format.fill = colors.dark;
  range.format.font = { name: font, size: 10, bold: true, color: "#FFFFFF" };
  range.format.horizontalAlignment = "center";
  range.format.verticalAlignment = "center";
  range.format.wrapText = true;
}
function body(range) {
  range.format.font = { name: font, size: 10, color: "#1F1F1F" };
  range.format.verticalAlignment = "center";
}
function statusFormatting(range) {
  range.conditionalFormats.add("containsText", { text: "COLLECTED", format: { fill: colors.green, font: { color: "#375623", bold: true } } });
  range.conditionalFormats.add("containsText", { text: "PARTIAL", format: { fill: colors.amber, font: { color: "#7F6000", bold: true } } });
  range.conditionalFormats.add("containsText", { text: "MISSING", format: { fill: colors.red, font: { color: "#9C0006", bold: true } } });
  range.conditionalFormats.add("containsText", { text: "NOT_ENUMERATED", format: { fill: colors.amber, font: { color: "#7F6000", bold: true } } });
  range.conditionalFormats.add("containsText", { text: "IDENTITY_UNVERIFIED", format: { fill: colors.gray, font: { color: "#595959", bold: true } } });
}

const identified = inventory.states.filter((state) => state.identity_status === "IDENTIFIED");
const statesWith = (key) => identified.filter((state) => state[key] > 0).length;
const verifiedPairs = identified.reduce((sum, state) => sum + state.verified_pair_count, 0);
const verifiedPoints = identified.reduce((sum, state) => sum + state.verified_point_count, 0);
const state006 = identified.find((state) => state.state_id === "STATE-006");

summary.showGridLines = false;
title(summary, "A2:G2", "Master Dataset manual collection summary");
summary.getRange("A3:D3").values = [["Snapshot date", "2026-11-19", "Decision", "DATA ACQUISITION INCOMPLETE"]];
summary.getRange("A3:D3").format.font = { name: font, size: 10, bold: true };
summary.getRange("D3").format.fill = colors.red;
summary.getRange("A5:B5").values = [["Metric", "Count"]];
header(summary.getRange("A5:B5"));
const totals = [
  ["Requested states", inventory.states_requested], ["Identified states", inventory.states_identified],
  ["Unverified identities", inventory.states_unverified], ["States with TAM_EXP", statesWith("tam_exp_count")],
  ["States with Field Summary PDF", statesWith("field_summary_count")],
  ["States with Test History PDF", statesWith("test_history_count")],
  ["States with at least one DYN", statesWith("dyn_count")], ["States with at least one TXT", statesWith("txt_count")],
  ["Verified DYN/TXT pairs", verifiedPairs], ["Surface/Pump points in verified pairs", verifiedPoints],
  ["Verified files consolidated", inventory.copy_results.length],
];
summary.getRange("A6:B16").values = totals;
body(summary.getRange("A6:B16"));
summary.getRange("B6:B16").format.numberFormat = "#,##0";
summary.getRange("D5:G5").values = [["No.", "Application", "Output", "States with output"]];
header(summary.getRange("D5:G5"));
summary.getRange("D6:G21").values = inventory.steps.map((step) => [
  step.number, step.application, step.output,
  identified.filter((state) => String(state.statuses[step.number]).startsWith("COLLECTED")).length,
]);
body(summary.getRange("D6:G21"));
summary.getRange("D24:G24").merge();
summary.getRange("D24").values = [["Current acquisition facts"]];
summary.getRange("D24:G24").format.fill = colors.blue;
summary.getRange("D24:G24").format.font = { name: font, size: 11, bold: true };
summary.getRange("D25:G29").values = [
  ["STATE-006 verified strokes", `${state006.verified_pair_count} of ${state006.expected_strokes}`, "", `${state006.expected_strokes - state006.verified_pair_count} remain`],
  ["STATE-006 18-stroke test", "18 verified", "", "Complete"],
  ["STATE-006 14-stroke test", "14 verified", "", "Complete"],
  ["TAM_EXP collection", `${statesWith("tam_exp_count")} states`, "", `${identified.length - statesWith("tam_exp_count")} identified states still missing TAM_EXP`],
  ["Test History coverage", `${statesWith("test_history_count")} state`, "", `${identified.length - statesWith("test_history_count")} identified states still missing`],
];
body(summary.getRange("D25:G29"));
summary.getRange("A:A").format.columnWidth = 34;
summary.getRange("B:B").format.columnWidth = 14;
summary.getRange("C:C").format.columnWidth = 11;
summary.getRange("D:D").format.columnWidth = 24;
summary.getRange("E:E").format.columnWidth = 15;
summary.getRange("F:F").format.columnWidth = 35;
summary.getRange("G:G").format.columnWidth = 34;

queue.showGridLines = false;
title(queue, "A2:K2", "Manual state-by-state collection queue");
queue.getRange("A3:K3").merge();
queue.getRange("A3").values = [["Work top to bottom. Do not mark a state complete until all historical tests and strokes are enumerated."]];
queue.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#595959" };
const queueHeaders = ["Order", "State ID", "State name", "Identity", "Next manual action", "TAM_EXP", "Summary PDF", "History PDF", "Verified pairs", "Expected strokes", "TWM native files"];
queue.getRange("A5:K5").values = [queueHeaders];
header(queue.getRange("A5:K5"));
const queueRows = inventory.states.map((state, index) => [
  index + 1, state.state_id, state.state_name, state.identity_status, state.next_manual_action,
  state.tam_exp_count, state.field_summary_count, state.test_history_count, state.verified_pair_count,
  state.expected_strokes ?? "UNKNOWN", state.twm_native_count,
]);
queue.getRangeByIndexes(5, 0, queueRows.length, queueHeaders.length).values = queueRows;
body(queue.getRangeByIndexes(5, 0, queueRows.length, queueHeaders.length));
queue.freezePanes.freezeRows(5);
queue.freezePanes.freezeColumns(3);
queue.getRange("A:A").format.columnWidth = 8;
queue.getRange("B:B").format.columnWidth = 13;
queue.getRange("C:C").format.columnWidth = 34;
queue.getRange("D:D").format.columnWidth = 24;
queue.getRange("E:E").format.columnWidth = 52;
queue.getRange("F:K").format.columnWidth = 16;
queue.getRangeByIndexes(5, 3, queueRows.length, 2).format.wrapText = true;
statusFormatting(queue.getRangeByIndexes(5, 3, queueRows.length, 2));

checklist.showGridLines = false;
title(checklist, "A2:W2", "State checklist for the 16 acquisition actions");
const checklistHeaders = ["State ID", "State name", "Identity", ...inventory.steps.map((step) => String(step.number).padStart(2, "0") + " " + step.output), "DYN files", "TXT files", "Verified pairs", "Next action"];
checklist.getRangeByIndexes(4, 0, 1, checklistHeaders.length).values = [checklistHeaders];
header(checklist.getRangeByIndexes(4, 0, 1, checklistHeaders.length));
const checklistRows = inventory.states.map((state) => [
  state.state_id, state.state_name, state.identity_status, ...inventory.steps.map((step) => state.statuses[step.number]),
  state.dyn_count, state.txt_count, state.verified_pair_count, state.next_manual_action,
]);
checklist.getRangeByIndexes(5, 0, checklistRows.length, checklistHeaders.length).values = checklistRows;
body(checklist.getRangeByIndexes(5, 0, checklistRows.length, checklistHeaders.length));
checklist.freezePanes.freezeRows(5);
checklist.freezePanes.freezeColumns(3);
checklist.getRange("A:A").format.columnWidth = 13;
checklist.getRange("B:B").format.columnWidth = 34;
checklist.getRange("C:C").format.columnWidth = 24;
checklist.getRange("D:S").format.columnWidth = 20;
checklist.getRange("T:V").format.columnWidth = 12;
checklist.getRange("W:W").format.columnWidth = 52;
checklist.getRangeByIndexes(5, 2, checklistRows.length, 17).format.wrapText = true;
checklist.getRange("W6:W101").format.wrapText = true;
statusFormatting(checklist.getRangeByIndexes(5, 2, checklistRows.length, 17));

workflow.showGridLines = false;
title(workflow, "A2:D2", "Echometer manual acquisition workflow");
workflow.getRange("A4:D4").values = [["No.", "Application", "Action", "Output"]];
header(workflow.getRange("A4:D4"));
workflow.getRange("A5:D20").values = inventory.steps.map((step) => [step.number, step.application, step.action, step.output]);
body(workflow.getRange("A5:D20"));
workflow.getRange("A:A").format.columnWidth = 8;
workflow.getRange("B:B").format.columnWidth = 15;
workflow.getRange("C:C").format.columnWidth = 55;
workflow.getRange("D:D").format.columnWidth = 36;
workflow.getRange("C5:D20").format.wrapText = true;

copied.showGridLines = false;
title(copied, "A2:I2", "Verified files consolidated into Master Dataset");
const fileHeaders = ["State ID", "State name", "Category", "Filename", "Bytes", "SHA-256", "Status", "Source", "Master Dataset destination"];
copied.getRange("A4:I4").values = [fileHeaders];
header(copied.getRange("A4:I4"));
const fileRows = inventory.copy_results.map((item) => [
  item.state_id, item.state_name, item.category, path.win32.basename(item.destination), item.bytes,
  item.sha256, item.status, item.source, item.destination,
]);
copied.getRangeByIndexes(4, 0, fileRows.length, fileHeaders.length).values = fileRows;
body(copied.getRangeByIndexes(4, 0, fileRows.length, fileHeaders.length));
copied.freezePanes.freezeRows(4);
copied.freezePanes.freezeColumns(2);
copied.getRange("A:A").format.columnWidth = 13;
copied.getRange("B:B").format.columnWidth = 34;
copied.getRange("C:C").format.columnWidth = 24;
copied.getRange("D:D").format.columnWidth = 48;
copied.getRange("E:E").format.columnWidth = 14;
copied.getRange("F:F").format.columnWidth = 68;
copied.getRange("G:G").format.columnWidth = 28;
copied.getRange("H:I").format.columnWidth = 70;
copied.getRangeByIndexes(4, 6, fileRows.length, 1).conditionalFormats.add("containsText", { text: "VERIFIED", format: { fill: colors.green, font: { color: "#375623", bold: true } } });

for (const sheet of [summary, queue, checklist, workflow, copied]) {
  const used = sheet.getUsedRange();
  used.format.verticalAlignment = "center";
}
workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
for (const sheetName of ["Summary", "Manual Queue", "State Checklist", "Workflow", "Collected Files"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 0.9, format: "png" });
  const previewPath = path.join(path.dirname(outputPath), sheetName.replaceAll(" ", "_") + ".png");
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
}
const summaryCheck = await workbook.inspect({ kind: "table", sheetId: "Summary", range: "A1:G29", include: "values,formulas", tableMaxRows: 30, tableMaxCols: 8 });
const errorCheck = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
console.log(JSON.stringify({ outputPath, sheets: 5, queueRows: queueRows.length, checklistRows: checklistRows.length, copiedRows: fileRows.length, summary: summaryCheck.ndjson, errors: errorCheck.ndjson }));
process.exitCode = 0;
