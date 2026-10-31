import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DEMO_LIMITS, MAX_CSV_ROWS, MAX_FILE_BYTES, MAX_FILE_NAME_CHARS, MAX_PDF_CHARS, MAX_PDF_PAGES, MAX_QUESTION_CHARS, RUNS_PER_DAY, SESSION_MAX_SECONDS } from "./limits";

// Top-level `key = integer` lines only (the [files_per_slot] table starts after them and is not read).
function readServerLimits(): Record<string, number> {
  const text = readFileSync(resolve(import.meta.dirname, "../../api/config/limits.toml"), "utf8");
  const values: Record<string, number> = {};
  for (const line of text.split("\n")) {
    if (line.startsWith("[")) break;
    const match = /^([a-z_]+)\s*=\s*(\d+)\s*(#.*)?$/.exec(line);
    if (match) values[match[1]] = Number(match[2]);
  }
  return values;
}

describe("the session length matches api/app/core/config.py", () => {
  it("session_max_seconds default is SESSION_MAX_SECONDS", () => {
    const text = readFileSync(resolve(import.meta.dirname, "../../api/app/core/config.py"), "utf8");
    const match = /^\s*session_max_seconds:\s*\w+\s*=\s*(\d+)/m.exec(text);
    expect(match, "session_max_seconds default not found in config.py").not.toBeNull();
    expect(SESSION_MAX_SECONDS).toBe(Number(match![1]));
  });
});

describe("web limits match api/config/limits.toml", () => {
  const server = readServerLimits();

  it.each([
    ["max_file_bytes", MAX_FILE_BYTES],
    ["max_rows", MAX_CSV_ROWS],
    ["max_pdf_pages", MAX_PDF_PAGES],
    ["max_pdf_chars", MAX_PDF_CHARS],
    ["max_question_chars", MAX_QUESTION_CHARS],
    ["max_filename_chars", MAX_FILE_NAME_CHARS],
    ["daily_runs_per_user", RUNS_PER_DAY],
  ])("%s", (key, web) => {
    expect(server[key], `${key} missing from limits.toml`).toBeDefined();
    expect(web).toBe(server[key]);
  });

  it("the Plans screen set is built from the same constants", () => {
    expect(DEMO_LIMITS).toEqual({ max_file_mb: server.max_file_bytes / (1024 * 1024), csv_rows: server.max_rows, pdf_pages: server.max_pdf_pages, runs_per_day: server.daily_runs_per_user });
  });
});
