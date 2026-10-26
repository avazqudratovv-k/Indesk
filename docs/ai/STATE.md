# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-27

## Status in one line
Screens 2.1 to 2.7b are done on mock data. The backend foundation (P1 to P7), the Ask flow with Owl and Beaver (P8a), the first real Gemini calls (P8b) and the web swap for log in, sign up and the Ask run (4.1 to 4.3) P9 (Cat as code, the report and `GET /api/reports/{id}`), web 4.4 (the real report screen), the P9 follow-up (report quality), the Korean least fix, P10a (run gates, quotas, caps, `GET /api/usage`), P10b (`GET /api/example`, `lang` on the report), P10c (DB roles, migrate service, compose split, API gaps) and the Ask = one CSV change (`TOO_MANY_FILES`) are committed. A real Ask run goes through Owl, Beaver and Cat and ends with a report the web shows. Check and Compare still end as unconfigured. HEAD 43dd394. The dev database was reset with `docker compose down -v` after 10c; the stack now runs with split DB roles (`indesk_migrator` and `indesk_app`, #255). Nov 1 is now a soft target (Nov 1 to 3), not a hard date. **Real runs through Owl, Beaver and Cat matched independently computed answers** for top station, line totals (Korean and English) and the weekday versus weekend average. Line totals ran in P8b, in web 4.4 and in the follow-up. Both previously untested chain entries returned HTTP 200, so every chain entry is now verified live.

## Commits since the last docs batch (7fcfccb)
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
Decisions for all of these: DECISIONS #99 to #260.

## What exists
### `web/`
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`, `/workspace` (Ask and run tabs), `/reports/[id]`. `/my` and `/people` are `RoutePlaceholder` pages behind `RequireAuth`. Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/`, `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, RequireAuth), `plans/`, `report/`, workspace and run components.
- Real API code: `lib/api/` (client, errors, single-flight refresh), `lib/auth/` (api, hint, bootstrap, safe-next), `lib/run/live/` (submit, SSE watch, reducer, trace keys, storage). `lib/run/mock-run.ts` still drives the example run.
- Mocks: `web/mocks/*.json` with `index.ts`; types in `lib/types.ts`. The mock session helper and `dev_session` are gone (#179).
- Tests: Vitest (`npm test`). i18n: en and ko, locale from the `NEXT_LOCALE` cookie.
- Shell and screen deviations from the boards: DECISIONS #69 to #77, #79 to #98, #174 to #197.
### `api/` (FastAPI, Python 3.12 in Docker)
- Routes (all under `/api`): `GET /health`, `GET /ready`; `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /me`; `GET /usage`; `GET /example`; `POST /uploads`, `GET /uploads`, `GET /uploads/{id}`, `DELETE /uploads/{id}`; `POST /runs` (202, optional `Idempotency-Key`), `GET /runs/active`, `GET /runs/{id}`, `GET /runs/{id}/events` (SSE); `GET /reports/{id}` (owner only). Check the code before relying on this list.
- Services in `compose.yaml`: api, worker, scheduler, sandbox, db (pgvector), redis, and a one-shot `migrate` (runs as the migrator role). Dev mounts are in `compose.override.yaml`; `compose.prod.yaml` is a skeleton. Migrations 0001 to 0004.
- Gateway (`app/ai/`), sandbox service (`api/sandbox/`), run machine and executor (`app/runs/`), Owl and Beaver with `AskFlow` (P8a, #198 to #210). Cat and the report (P9, #219 to #229).
- `api/config/models.toml` holds two chains (light and main, 3 entries each, #198). All six names were listed for the key. Per-entry `thinking_level` or `thinking_budget` (#214).
- Tests: `api/tests/` (pytest against real Postgres and Redis database 15, and a fake model client). Counts at HEAD 43dd394: 1051 api + 21 sandbox (`-m sandbox`) + 209 web (as reported by the owner; the api count is re-run at the end of docs batch 13). CI jobs: `api`, `sandbox`, `web`.

## In progress
- Nothing.

## Next
1. **Rate-limit values:** put real values into `limits.toml` (the daily run caps and `free_runs` are placeholders, #246, #247). The owner reads aistudio.google.com/rate-limit first.
2. **Docs.**
3. **Copy-honesty and web prompt:** question chips and example copy match the demo file, plus the web steps in ROADMAP 5.1 (example, `lang`, new error messages, counting tags, one-CSV dropzone, active-run handling).
4. **Deploy (5.x), then README and demo video.** (The Seoul demo CSV itself is committed, 86fe0b2.)
- PLANNED, not built (#98): "Translate to <other language>" for real reports (not in API or web yet; 4.4 shows only a language note, #236); dropped first if a day slips.
- ROADMAP 2.16 holds the open polish and accessibility items collected so far.

## Later
### API gaps
Closed in P10c (#257): `RUN_ACTIVE` carries `run_id`, `GET /runs/active`, `DELETE /uploads/{id}`, `no-transform` on the stream. The web does not use them yet.
- `TOO_MANY_STREAMS` (429) reaches the browser as an anonymous error (a web fix, #260).
- No retry endpoint for a failed agent (DATA.md lists `POST /runs/{id}/steps/{step}/retry`).
### Deploy checklist
- `TRUSTED_PROXIES` must cover the proxy, or all visitors share one rate-limit bucket.
- `ALLOWED_ORIGINS` set to the public origin.
- Secure cookies (set automatically when `APP_ENV=production`; test it).
- nginx: `proxy_buffering off` and compression for the SSE route.
- Done in P10c: split DB roles with a test that the app role cannot DROP, ALTER, CREATE or TRUNCATE (#255); the compose mounts moved to `compose.override.yaml` (#256). `compose.prod.yaml` is only a skeleton until 5.6.
- Replace the placeholder run caps and `free_runs` with values that fit Google's real rate limits (DECISIONS OPEN 6).
- Paid Gemini key with a monthly limit, and production caps (#32, #160).
- Never run redis `FLUSHDB` on production.
- Trim fonts (about 966 KB) and hide links to unbuilt pages (`/workspace/reports`, "My page", the reports list).
### Polish
- Empty navbar auth slot before hydration.
- "Coming soon" text contrast is about 4.0:1.
- The time tile mixes browser and server clocks on resume.
- Neutral chip style for "not available yet" (#197).
- Korean text needs a native review (UI labels and report prose, #98).
### Other open items
- "Agents woken" is hard-coded "3 of 4" in the example run (#83); derive it from events for real runs.
- Favicon (`favicon.ico` returns 404) and agent icons at 128 px.
- Check the "Chameleon" word width in Safari and Firefox.
- `?mockOutcome` must be ignored in production (#82); verify in a production build.
- Contrast of the error pill, the disabled Run button and the counter.
- Decide which agent steps truly use an LLM (Owl is rule-based in v1, #61) so README claims stay accurate.
- After section 4: compare 5 questions against a plain chatbot for the README.
- The web mock still returns HTTP 200 for an unknown report id (#94); the API returns 404 (#227). Real reports show a neutral no-report card (#240); not re-checked here for the mock path.
- Report claim rows are narrower on phones (board quirk, #95).
- Evidence table cell text is not compared with the board.
- Share and Style & download (2.8, 2.9) and the follow-up thread are built after Nov 1 (#87); real reports hide them with one line (#231).
- Claims are checked for the right row, not for naming the right column.
- Korean header words: English column headers stay English inside Korean reports.
- One source for the 5 MB file limit: the server now reads `limits.toml` (#128); `web/lib/workspace/validate.ts` and `web/mocks/plans.json` still hold copies.
- `GET /api/example` exists (P10b, #253) but Home "Try with an example" still uses the mock until the web swap. Only an English example exists.
- The web does not know `TOO_MANY_FILES` and `UPLOAD_IN_USE` yet, so users see the generic validation text (#259).

## Known issues
- Open polish items are listed above and under ROADMAP 2.16.
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- Sandbox isolation is best-effort: the kernel is shared with the host (#147).
- No malware scan; uploads stay `moderation=pending` (#138).
- Two tabs refreshing at the same moment can end the session (#126); the web reduces it with a lock (#177).

## Not verified
- Safari, Firefox and a real browser reading a report are untested.
- The real rate limits per model name are unknown (owner reads aistudio.google.com/rate-limit). The daily run caps and `free_runs` are placeholders (#246).
- Gates and quotas against real traffic; nothing has gone through nginx; `compose.prod.yaml` was only checked with `docker compose config`.
- Cost per run is an estimate from token counts and the price table (#217); `ai_calls.est_cost_usd` is still 0.
- EventSource and the gzip fix were checked in Chrome only. Safari, Firefox and real phones are untested.
- The Korean text (UI labels, report prose and the 4.4 report strings) has not been reviewed by a native speaker.
- Whether a column is "the sum" cannot be proven in code; the prompt and live runs are the evidence (#242).
- The api count (1051), the sandbox count (21) and the web count (209) are as reported by the owner; the api suite is re-run at the end of docs batch 13.

## Environments
- Local: web http://localhost:3000 (dev server rewrites `/api` to the API), API http://127.0.0.1:8000 through `docker compose up --build`; Postgres and Redis run in Compose.
- Production: not deployed yet.

## Releases
- None yet.
