# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-31

## Status in one line
Indesk is **live** at https://indesk.76-13-198-17.sslip.io (deployed 2026-10-27 at HEAD 12a069a) and the live site is **untouched since**: everything after 12a069a is committed but not deployed, and stays that way until the one deploy (see "Next" and the deploy checklist). Done in the repo: screens 2.1 to 2.7b, the backend P1 to P10c, the Ask flow with Owl, Beaver and Cat, the real caps, P11, the regenerated example, P12, P13, **P14a and P14b** (PDF Ask: parser service, embeddings, Hound, the PDF writer, Cat's quote checks, quantity-word check, chunk guard; tested live on real Gemini, see "What is live and what was only rehearsed"), the **PDF web part** (4.5A to 4.5C), the web honesty pass 4.7A to 4.7E, the **not answerable** explanation (API and web, including `csv_missing_column`), the **6-hour absolute session** (migration 0006), **My page** (API list and delete, purge job, web page, notices) and the small API gaps (`server_now`, semicolon and tab CSV, `Retry-After`, production start guard). A real CSV or PDF Ask run ends with a report the web shows. Check, Compare and Vision (Chameleon) are **not built** and are shown as "Not available yet"; they come after the deploy. HEAD 93cbc38. Nov 1 is a soft target (Nov 1 to 3).

## Commits (docs batch 15 recorded everything up to 45e371c; batch 16 records 94820fa to 93cbc38; older history: `git log`)
| Step | Commit | What |
|---|---|---|
| P1 (3.1) | bc1cc5e | Compose stack, health/ready, config, RQ worker, CI |
| P2 (3.2, 3.4) | dd680e1 | State contract, DB models, first migration |
| P3 (3.5) | fb57432 | Auth: sign up, log in, refresh rotation, log out, me |
| P4 (3.6) | b91b346 | CSV uploads, storage, limits, expiry sweep |
| P5 (3.7) | 13bca05 | Sandbox service, upload rate limit, max columns, scheduler healthcheck |
| P6 (gateway) | ed12345 | Gemini gateway, model chain, daily call caps, usage records |
| P7 (run job, SSE; 3.3 absorbed) | debdb7b | Run state machine, `execute_run` job, SSE, `POST /runs`, reaper, Redis test guard |
| 4.1 + 4.2 | a5461cd | Real auth in the web, single-flight refresh, Log out, disabled Check/Compare |
| 4.3 | b2a13b2 | Ask on the real API, live trace over SSE, failure cards, CSV-only copy |
| P8a (3.9, agent half) | 09e5340 | Ask flow: Owl and Beaver on two model chains, `AskFlow`, fake-gateway tests |
| P8b (3.9, live half) | 7897561 | First real Gemini calls, `thinking_level`, trailing empty CSV cells, sandbox `index_col=False` fix |
| Demo data | 86fe0b2 | `docs/demo-data/seoul_subway_2026-09.csv` (4,079 rows, KOGL Type 1) |
| P9 (3.10, 3.11) | fae02e5 | Cat as code, report with claims and evidence, `GET /api/reports/{id}` |
| Test fix | 5c12875 | `models.toml` header test checks what was called live (fixes CI after batch 10) |
| Docs batch 11 | c20bccf | Records P9, fixes the stale `models.toml` comment |
| 4.4 | 294f9da | Real report screen on `GET /api/reports/{id}`, live trace verify step, plain-text safety |
| P9 follow-up | 1fe735a | Report quality, `add_metrics` sums, unique labels, number grouping, plain column words |
| Korean least fix | e6103d0 | Korean least wording is checked against the column minimum |
| Docs batch 12 | efc6f00 | Records web 4.4, P9 follow-up and the Korean least fix |
| P10a | 7eb642a | Run gates, free quota, daily run caps, `GET /api/usage`, failure kind |
| P10b | c73fc54 | `GET /api/example` from a static export, `lang` on the report |
| P10c | be59343 | DB roles, migrate service, compose split, run and upload API gaps |
| Ask = one CSV | 43dd394 | `TOO_MANY_FILES` (P10c follow-up) |
| Docs batch 13 | 1f2dcfa | Records P10a to P10c and Ask = one CSV |
| Real caps | f4b40b2 | `limits.toml`: 150 runs and 600 calls a day for the site (#261) |
| P11 batch A | 108a974 | Example from `GET /api/example`, `lang`, P10 error messages, `RUN_ACTIVE` Watch link, usage tags, one CSV slot |
| P11 B1 | 9a82146 | Copy honesty on Home, auth, Plans, nav; `built` flag; 404 for mock reports, `/people`, `/my` |
| P12 | 3e9746b | Production compose, web image, host nginx conf, backups, runbook |
| Example | 4fa7f61 | Cached example regenerated from a real Seoul weekday run; sidecar meta file |
| P11 B2 | 1516cbb | Workspace and report copy, Seoul chips, sample CSV, example banner, favicon |
| P13 | 12a069a | Seoul sample pre-attached in Ask, uploaded only on Run |
| Docs batch 14 | dd73d07 | Records the caps, P11, the example, P12 and P13 (#261 to #273) |
| P14a part 1 | 545495d | PDF parsing in an isolated parser service, PDF upload codes, migration 0005 (`document_pages`, `chunks`) |
| Test fix | befb65d | Drops the test database owned by `indesk_migrator` so CI can drop the role |
| Row limit | 5c7471e | CSV row limit 5,000 to 20,000; `TOO_MANY_ROWS` names the count and the limit (api and web) |
| P14a part 2 | 2973536 | Embeddings, hybrid retrieval, Hound, PDF writer, Cat quote checks, `parser` CI job |
| Web fix | d170dce | Sample dismissal is read after hydration (no mismatch or theme loss) |
| Demo PDFs | 22ae66c | Generated demo PDFs (en, ko) from the Seoul CSV with a ground-truth file |
| P14a fix | eaefadf | PDF writer says `found=false` instead of off-topic claims; cosines in the trace; `smoke_live --reset-quota` |
| P14a fix | 773257a | Cat number rule: restated question context and spelled small numbers; reset-quota also clears own daily counters |
| Test fix | 75705de | Lighter slow-parse fixture so the parser busy test fits a CI runner |
| Test fix | 45e371c | Line length in the parser busy test |
| Docs batch 15 | 94820fa | Records P11 to P14a, the caps, 20,000 rows (#274 to #287) |
| P14b | 6647c10 | Quantity-word check, chunk guard, embedding token estimate, `pages_without_text` |
| Test fix | 4194943 | Refusal tests assert no model call and no `ai_calls` row |
| P14b | e520298, 89e3a4e | Embedding budget 100,000 to 250,000 tokens; stale comment fixed |
| Smoke | 6f31e59 | Smoke script prints Cat verdicts and no-report outcomes |
| Web 4.5A to 4.5C | 702beec, 7988fc5, 6e0e81a | PDF in the dropzone and upload errors; Hound trace, quotes and pages in the report; team strip per file type, Beaver not used in PDF runs |
| Auth | e7e5f62 | Absolute 6-hour session, migration 0006, `SESSION_MAX_SECONDS` |
| Web 4.7A, 4.7B, 4.7C | 9e3f813, 38a1b05, 15f7a61 | `/s/[token]` gated and root 404; Plans and outcome copy match the real limits; one wording for unbuilt things, neutral chip, "Did not start" |
| CI | 706539f, dd452fc | Import order and format drift fixed; `ruff format --check` added to CI |
| Not answerable | fe9f9e2, fd46719 | API reason code, facts and suggestions; web card with reason, file facts and chips, per-outcome run mark |
| Web 4.7D, 4.7E | 3a7fbb3, 0d5986e | Plan cards with real limits, honest demo checkout; one source for limits with a drift test, dead copy removed |
| Missing column | cd061b4, e54235f | `csv_missing_column` ends as not answerable; any unmatched name ends it |
| My page API | 0ce729b | `GET /reports`, `DELETE /reports/{id}`, `GET /uploads` limit and `include_deleted` |
| My page web | 1c4db61, f5db74a, c096fc7, 423b837 | Lists and delete flows; header, usage and account cards, navbar name link; login, logout and session-ended notices, file row grid; wording polish |
| My page API | 9776cab, 7e98d2f | Daily purge job; read and delete rate limits |
| API small gaps | 2c651d1, 42fb1b1 | `server_now`, non-comma CSV, `Retry-After` on streams, production start guard; import order fix |
| Web | 93cbc38 | Run time tile uses the server clock offset |
Decisions for all of these: DECISIONS #99 to #321. This docs batch (16) is not committed yet.

## What exists
### `web/`
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`, `/workspace` (Ask and run tabs), `/reports/[id]` (`/reports/example` is the public example from `GET /api/example`). `/my` is built (My page, see below); `/people` is a `RoutePlaceholder` that answers 404 while its `built` flag in `nav-items.ts` is false; `/s/[token]` answers 404 (gated, no sharing yet) and the root has its own 404 page (#318); mock `rep_*` reports answer 404 in production (#263). Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/`, `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, RequireAuth), `plans/`, `report/`, workspace and run components.
- Limits: one source, `web/lib/limits.ts`, with a drift test against `api/config/limits.toml` (#301); `SESSION_MAX_SECONDS` has its own drift test (#292).
- Real API code: `lib/api/` (client, errors, single-flight refresh), `lib/auth/` (api, hint, bootstrap, safe-next), `lib/run/live/` (submit, SSE watch, reducer, trace keys, storage). `lib/run/mock-run.ts` still drives the example run.
- Mocks: `web/mocks/*.json` with `index.ts`; types in `lib/types.ts`. The mock session helper and `dev_session` are gone (#179).
- Tests: Vitest (`npm test`). i18n: en and ko, locale from the `NEXT_LOCALE` cookie.
- Shell and screen deviations from the boards: DECISIONS #69 to #77, #79 to #98, #174 to #197, #265.
### PDF in the web (built in 4.5A to 4.5C)
Built in the repo (4.5A to 4.5C); not deployed (#300).
- The Ask dropzone takes one CSV or one PDF, 5 MB. The six PDF error codes (`PDF_ENCRYPTED`, `PDF_NO_TEXT`, `PDF_TOO_MANY_PAGES`, `PDF_TOO_MUCH_TEXT`, `PDF_UNREADABLE`) and `PARSER_BUSY` have en and ko messages. `pages_without_text` is read from the PDF upload response (additive).
- The run tab shows Hound's real status and its trace lines (`search`, `bestPassage`, `keywordOnlySize`, `chunksSkipped`). The team strip depends on the file type (CSV: Owl, Beaver, Cat; PDF: Owl, Hound, Cat); Beaver shows "Not used" in PDF runs; an agent that never began shows "Did not start".
- The report shows quotes and page chips for PDF claims (the quote only in the evidence panel).
- Unbuilt things (Check a document, Compare, Chameleon/Vision) all say "Not available yet" (#303). The Plans page carries the real limits only (5 MB, 20,000 CSV rows, 30 PDF pages, 10 runs a day, 3 free runs in total) and the demo checkout is honest that the account stays Free (#301). The dead Check and Compare copy was removed; restore it from git history when those modes ship.
### My page and notices (built, not deployed)
- `/my`: header, usage card, account card, reports list and files list, with delete flows and a file row grid (#302). The navbar name links to `/my`. Share, Undo, the Pro toggle, the settings toggles and Delete account are not built there (#308).
- Login, logout and session-ended notices (`NoticeHost`, one-shot via sessionStorage); the "6 hours" wording shows only when the stored login age is at least 6 hours (#302). The run time tile uses the `server_now` offset (#299).
- Free runs are a one-time total allowance of 3, not monthly; deleting a report does not give one back (#295).
### `api/` (FastAPI, Python 3.12 in Docker)
- Routes (all under `/api`): `GET /health`, `GET /ready`; `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /me`; `GET /usage`; `GET /example`; `POST /uploads` (CSV and, since P14a, PDF), `GET /uploads`, `GET /uploads/{id}`, `DELETE /uploads/{id}`; `POST /runs` (202, optional `Idempotency-Key`), `GET /runs/active`, `GET /runs/{id}`, `GET /runs/{id}/events` (SSE); `GET /reports` (owner only, newest first), `GET /reports/{id}` (owner only), `DELETE /reports/{id}` (owner only). `GET /uploads` takes `limit` and `include_deleted`. `GET /runs/{id}` and `/runs/active` carry `server_now`. Check the code before relying on this list.
- Services in `compose.yaml`: api, worker, scheduler, sandbox, **parser** (P14a), db (pgvector), redis, and a one-shot `migrate` (runs as the migrator role). Dev mounts are in `compose.override.yaml`. `compose.prod.yaml` is the standalone production stack (P12, #268; it also has `parser`, #287); `deploy/` holds `RUNBOOK.md`, `backup.sh`, `nginx/indesk.conf`, `env.prod.example` and `compose.rehearsal.yaml`. **Migrations 0001 to 0006** (0001 initial schema, 0002 one active run per user, 0003 quota and failure kind, 0004 app role grants, 0005 `document_pages` and `chunks` with pgvector, 0006 `refresh_tokens.session_started_at`).
- Gateway (`app/ai/`, with an embedding call since P14a), sandbox service (`api/sandbox/`, also the image of the parser), run machine and executor (`app/runs/`), Owl and Beaver with `AskFlow` (P8a, #198 to #210), Cat and the report (P9, #219 to #229). PDF Ask (P14a, #274 to #283; P14b, #289 to #291): Owl in code, Hound (hybrid retrieval in `app/services/retrieval.py`), Cat's writer and quote checks (`cat_pdf*.py`). The PDF path ran on real Gemini once (13 of 14 calls, #288).
- Not answerable (#293, #294): closed reason codes and facts computed in code, `RunView.not_answerable`. Auth: absolute 6-hour session (#292). My page API and the purge job (`purge_expired`, daily, in the scheduler, #295 to #298). Small gaps (#299): `server_now`, semicolon and tab CSV rewritten to commas, `Retry-After` 5 on `TOO_MANY_STREAMS`, a production start guard.
- `api/config/models.toml` holds two chains (light and main, 3 entries each, #198) and one embedding entry (`gemini-embedding-2`, 768 dimensions, #279; used live in the PDF test, #288). Per-entry `thinking_level` or `thinking_budget` (#214).
- Caps in `api/config/limits.toml` (set 2026-10-27, #261): per user 10 runs and 50 model calls a day; whole site 150 runs and 600 model calls a day; 3 free runs per account in total; 20 run requests per hour per user; 30 uploads per hour per user. Upload limits: 5 MB, 20,000 rows, 200 columns; PDF: 30 pages, 150,000 characters. Run limits: 12 steps, 60,000 tokens (stands in for the $0.05 cap), 250,000 embedding tokens per run (PDF, raised from 100,000 in P14b, #291). `chunk_chars` must be at most 3,000 (startup check). Session limit `SESSION_MAX_SECONDS` 21600 (env, `Settings.session_max_seconds`, #292); `column_match_similarity` is in `limits.toml` (#294). Per-run cost: the token cap (60,000) is the real control; the per-run dollar caps of AGENTS.md and SPEC are not implemented as dollars.
- Tests: `api/tests/` (pytest against real Postgres and Redis database 15, and a fake model client). CI jobs: `api`, `sandbox`, `parser`, `web`.
  - **Test counts from the last run (owner-reported, not re-run in docs batch 16):** api 1450 passed with 43 tests deselected (the `sandbox` and `parser` markers, which need those services), web 513, sandbox 21. The earlier measured figure was `1240 passed, 36 deselected` at HEAD 45e371c (2026-10-30, through Docker, ruff and mypy clean). I did not run anything in this batch.

## What is live and what was only rehearsed
- **Live in production** (deployed 2026-10-27 at HEAD 12a069a, checks reported by the owner, #271): P1 to P13: sign-up and log-in, CSV Ask with Owl, Beaver and Cat, the report, the cached example, the real caps, split DB roles, backups, the proxy chain and SSE through nginx. **The live site has not been touched since.**
- **Committed after the deploy, not deployed:** everything from 545495d to 93cbc38 (the parser service, migrations 0005 and 0006, embeddings, Hound and the PDF writer, P14b, the PDF web part, the 4.7 honesty pass, not answerable, the 6-hour session, My page, the purge job, the small API gaps). They go out in the one deploy. The existing database volume needs `CREATE EXTENSION vector;` run by a superuser first, because only a fresh volume runs `db-init` (migration 0005 docstring, #276); `deploy/RUNBOOK.md` "Update" has no step for it (#287). See the deploy checklist below.
- **Run against real Gemini by hand (PDF live test, P14b, #288):** 13 of 14 calls, no code fixes needed. Embeddings `gemini-embedding-2` at 768 dimensions came back as unit vectors; the token count is read from `usageMetadata.promptTokenCount`. Three of five runs (A, B, D) answered with the right figures and pages; two (C, E) ended `not_answerable` with no report and were not counted. The 0.5 floor separates nothing (#289). Run D was tested only through the API plus the web walk-through.
- **Only rehearsed:** the P12 local rehearsal (production web image with scripted runs through `compose.rehearsal.yaml`); its results are not recorded in git.
- **Never run anywhere:** Check, Compare, Chameleon (images), exports, sharing.

## In progress
- Nothing. Docs batch 16 (this one) is waiting for the owner's review and commit.

## Next
1. **The one deploy** of everything since 12a069a. The live site stays untouched until then. Work through the deploy checklist below first (nothing in it is done yet).
2. **After the deploy, in this order** (decided, #320): README and demo video (5.7), then Check a document, then Compare, then Vision (Chameleon), then account delete, then exports.
3. **Switch to indesk.uz** when the domain is active (RUNBOOK "Switch to indesk.uz").
- Check a document, Compare and Vision (Chameleon) stay unbuilt and say "Not available yet" until then (#303).
- PLANNED, not built (#98): "Translate to <other language>" for real reports (not in API or web yet; 4.4 shows only a language note, #236).
- ROADMAP 2.16 holds the open polish and accessibility items collected so far; BACKLOG holds the post-deploy items and the open items of batch 16.

## Later
### API gaps
- No retry endpoint for a failed agent (DATA.md lists `POST /runs/{id}/steps/{step}/retry`).
### Deploy checklist
First deploy, done on 2026-10-27: `TRUSTED_PROXIES` is the pinned edge subnet; `ALLOWED_ORIGINS` is the public origin; Secure cookies, the proxy chain and SSE through nginx were checked on the live server (SECURITY.md section 7a); split DB roles (#255); `compose.prod.yaml` (#268); the real caps (#261).
**For the one deploy of everything since 12a069a (#321). None of these is done:**
- [ ] `CREATE EXTENSION vector;` by a superuser on the existing production volume, BEFORE the migrations (deploy risk #287; `deploy/RUNBOOK.md` "Update" has no step for it, and this batch does not edit `deploy/`).
- [ ] Run migrations 0005 and 0006 (0006 backfills `session_started_at`; logins older than 6 hours end after it, #292).
- [ ] Verify the live `ALLOWED_ORIGINS`, `TRUSTED_PROXIES` and Secure cookies against the new production start guard (it refuses to start with localhost or 127.0.0.1 in `ALLOWED_ORIGINS`, an empty `TRUSTED_PROXIES`, or cookies that are not Secure, #299).
- [ ] The `parser` image build, and a check that `parse_net` has no route out.
- [ ] Role split check on the live database (not verified yet, SECURITY.md 7a).
- [ ] Daily database backup (exists since P12; confirm it still runs and test a restore).
- [ ] Container restart policy.
- [ ] Certificate renewal.
- [ ] Log rotation.
- [ ] A health check.
- [ ] Confirm the 24 h upload sweep and the daily purge (`purge_expired`) actually run in the scheduler.
- [ ] Paid Gemini key with a monthly spend limit (the owner sets it in Google AI Studio; ROADMAP 5.5).
- [ ] nginx buffering off for the SSE route (set in `deploy/nginx/indesk.conf`, #269; confirm after the update).
- [ ] The sandbox cannot reach the network (ROADMAP 5.4); the same for the parser. Not verified on the deployed stack.
- Never run redis `FLUSHDB` on production.
- Fonts are still loaded from Google at runtime (BACKLOG).
### Polish
- ~~Empty navbar auth slot before hydration.~~ The navbar reserves space in all states (#314, 15f7a61).
- "Coming soon" text contrast was about 4.0:1; the light `--mute` is darker since 4.7C (#312); the ratio was not re-measured.
- ~~The time tile mixes browser and server clocks on resume.~~ Fixed: it uses the `server_now` offset (93cbc38, #299).
- ~~Neutral chip style for "not available yet"~~ Done: the `soon` chip tone (#263).
- Korean text needs a native review (UI labels and report prose, #98).
### Other open items
- "Agents woken" is hard-coded "3 of 4" in the example run (#83); derive it from events for real runs.
- Agent icons at 128 px. (The favicon is done: `icon.svg` and `apple-icon.png`, #264.)
- Check the "Chameleon" word width in Safari and Firefox.
- `?mockOutcome` must be ignored in production (#82); verify in a production build.
- Contrast of the error pill, the disabled Run button and the counter.
- Decide which agent steps truly use an LLM (Owl is rule-based in v1, #61; Owl is code also for PDFs, #281) so README claims stay accurate.
- After section 4: compare 5 questions against a plain chatbot for the README.
- The web mock still returns HTTP 200 for an unknown report id (#94); the API returns 404 (#227). Real reports show a neutral no-report card (#240); not re-checked here for the mock path.
- Report claim rows are narrower on phones (board quirk, #95).
- Evidence table cell text is not compared with the board.
- Share and Style & download (2.8, 2.9) and the follow-up thread are built after Nov 1 (#87); real reports hide them with one line (#231).
- Claims are checked for the right row, not for naming the right column.
- Korean header words: English column headers stay English inside Korean reports.
- One source for limits in the web: `web/lib/limits.ts`, with a drift test against `api/config/limits.toml` (#301). `web/lib/workspace/validate.ts` and `web/mocks/plans.json` may still hold copies (not re-checked).
- Only an English example exists (#253, #266). The web shows it for every language; the report language note applies.

## Known issues
- Open polish items are listed above and under ROADMAP 2.16.
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- Sandbox isolation is best-effort: the kernel is shared with the host (#147); the parser has the same hardening and the same limit (#274).
- No malware scan; uploads stay `moderation=pending` (#138).
- Two tabs refreshing at the same moment can end the session (#126); the web reduces it with a lock (#177).
- The similarity floor 0.5 cannot separate answerable from unanswerable questions (measured, #289); the writer's `found=false` is the real guard. Only two unanswerable samples exist.
- Substitution gap: a question about data the file lacks can be answered with other columns, disclosed in the first sentence (#319). The README must say it plainly.
- Home team plates use an IntersectionObserver mask; they look blank in full-page screenshots only.
- A non-Ask report page returns 200 in dev (a soft 404). Handle it on purpose when Check ships.
- Rate limits exist only on the routes added recently (#296); `GET /reports/{id}`, `/runs/*`, `/usage` and `/me` are still unlimited.

## Not verified
- Sandbox network isolation on the deployed stack.
- The PDF path beyond the one live test (#288): only five runs on the demo PDFs, only two unanswerable samples; run D only through the API plus the web walk-through; Korean PDFs and the writer prompt on other documents.
- The embedding price: $0.20 per million tokens came from a reseller page and is unverified; do not state it as fact. The writer's cost shows 0.000 in `ai_calls` (no price table, BACKLOG). `real_client.py` still uses the old token estimate when Google returns no count (BACKLOG).
- Token rates 0.36 per ASCII character and 1.1 per Korean character are derived from two documents, not directly measured (#291).
- Whether the deployed server needs anything beyond the checklist above; nothing since 12a069a is deployed.
- Safari, Firefox and a real phone reading a report or following a stream are untested (EventSource and the gzip fix were checked in Chrome only).
- The deployed server's checks (first deploy) were run by the owner and are as reported; no test covers them.
- Cost per run is an estimate from token counts and the price table (#217); `ai_calls.est_cost_usd` is still 0.
- The Korean text (UI labels, report prose, the not answerable card and the notices) has not been reviewed by a native speaker.
- Whether a column is "the sum" cannot be proven in code; the prompt and live runs are the evidence (#242).
- A maximum-size CSV (20,000 rows or 5 MB) against the 1 GB sandbox, and the other stress cases of ROADMAP 5.3.
- The local rehearsal results of P12 are not recorded in git.
- Test counts (api 1450, web 513, sandbox 21) are owner-reported from the last run and were not re-run in this batch.

## Environments
- Local: web http://localhost:3000 (dev server rewrites `/api` to the API), API http://127.0.0.1:8000 through `docker compose up --build`; Postgres and Redis run in Compose.
- Production: https://indesk.76-13-198-17.sslip.io on a Hostinger VPS (Ubuntu 26.04, x86_64) behind the host nginx, which also serves another app. Clone in `/root/Indesk` (read-only GitHub deploy key), `.env` sets `COMPOSE_FILE=compose.prod.yaml`, only `web` is published (127.0.0.1:4100), backups by host cron at 03:15 (7 days). Steps: `deploy/RUNBOOK.md`.

## Releases
- 2026-10-27: first deploy at the sslip.io address (HEAD 12a069a). No tags.
