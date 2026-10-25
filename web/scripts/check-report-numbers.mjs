// Checks that the Korean report prose has exactly the same numbers as the English (ROADMAP 2.7b).
// Every digit sequence (14.1, 2,410, 2019) found in a translated field must also appear in the English field, the same number of times.
// Model for the real check in ROADMAP 3.11. Run: node scripts/check-report-numbers.mjs
import { readFileSync } from "node:fs";

const read = (name) => JSON.parse(readFileSync(new URL(`../mocks/${name}.json`, import.meta.url), "utf8")).records;
const digits = (text) => (String(text).match(/\d+(?:[.,]\d+)*/g) ?? []).sort();

const mismatches = [];
let checked = 0;

function compare(where, en, ko) {
  if (ko === undefined) return;
  checked += 1;
  const a = digits(en).join(" ");
  const b = digits(ko).join(" ");
  if (a !== b) mismatches.push(`${where}\n    en: ${en}\n    ko: ${ko}\n    numbers en [${a}] vs ko [${b}]`);
}

function compareTable(where, en, ko) {
  if (!ko) return;
  compare(`${where}.table`, JSON.stringify([en?.headers, en?.rows]), JSON.stringify([ko.headers, ko.rows]));
}

for (const report of read("reports")) {
  const ko = report.translations?.ko;
  if (!ko) continue;
  const en = report.summary_json;
  const t = ko.summary_json;
  const where = report.id;
  compare(`${where}.title`, report.title, ko.title);
  compare(`${where}.answer`, en.answer, t.answer);
  compare(`${where}.meaning`, en.meaning, t.meaning);
  en.top_rows?.forEach((row, i) => {
    compare(`${where}.top_rows[${i}].label`, row.label, t.top_rows?.[i]?.label);
    compare(`${where}.top_rows[${i}].value`, row.value, t.top_rows?.[i]?.value);
  });
  en.in_short?.forEach((item, i) => compare(`${where}.in_short[${i}]`, item.text, t.in_short?.[i]?.text));
  en.next_steps?.forEach((step, i) => compare(`${where}.next_steps[${i}]`, step, t.next_steps?.[i]));
}

for (const claim of read("claims")) compare(`${claim.id}.text`, claim.text, claim.ko?.text);

for (const item of read("evidence")) {
  const ko = item.payload.ko;
  if (!ko) continue;
  const en = item.payload;
  const where = `${item.id} (${item.ref})`;
  compare(`${where}.title`, en.title, ko.title);
  compare(`${where}.body`, en.body, ko.body);
  compareTable(where, en.table, ko.table);
  if (ko.chart) {
    compare(`${where}.chart.title`, en.chart.title, ko.chart.title);
    en.chart.series.forEach((bar, i) => compare(`${where}.chart.series[${i}].label`, bar.label, ko.chart.series?.[i]?.label));
  }
}

if (mismatches.length > 0) {
  console.log(`${mismatches.length} mismatch(es) in ${checked} translated fields:\n`);
  console.log(mismatches.join("\n\n"));
  process.exit(1);
}
console.log(`OK: ${checked} translated fields, every number matches the English.`);
