// The one place the web app writes down product limits. Source of truth: api/config/limits.toml; the Vitest test
// lib/limits.test.ts reads that file and fails if a number here drifts from it. The browser only checks type, size and
// name; rows, pages and characters are counted by the server, which answers with a code, so those three are copy only.

export const MAX_FILE_BYTES = 5 * 1024 * 1024; // max_file_bytes
export const MAX_CSV_ROWS = 20000; // max_rows
export const MAX_PDF_PAGES = 30; // max_pdf_pages
export const MAX_PDF_CHARS = 150000; // max_pdf_chars
export const MAX_QUESTION_CHARS = 1000; // max_question_chars
export const MAX_FILE_NAME_CHARS = 255; // max_filename_chars
export const RUNS_PER_DAY = 10; // daily_runs_per_user

// Not in limits.toml: the API's login lifetime (api/app/core/config.py, session_max_seconds). Used for the "6 hours" notice.
export const SESSION_MAX_SECONDS = 21600;

export const MAX_FILE_MB = MAX_FILE_BYTES / (1024 * 1024);

// The set of limits shown on the Plans screen (one set for everyone in the demo).
export const DEMO_LIMITS = { max_file_mb: MAX_FILE_MB, csv_rows: MAX_CSV_ROWS, pdf_pages: MAX_PDF_PAGES, runs_per_day: RUNS_PER_DAY };
