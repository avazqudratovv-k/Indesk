# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-27

## Status in one line
Indesk is **live** at https://indesk.76-13-198-17.sslip.io (deployed 2026-10-27). Done: screens 2.1 to 2.7b, the backend P1 to P10c, the Ask flow with Owl, Beaver and Cat, web 4.1 to 4.4, the real caps, P11 (web batch A, B1, B2: example from the API, honest copy, Seoul chips), the example regenerated from a real run, P12 (production compose, host nginx, backups, runbook) and P13 (Seoul sample pre-attached in Ask). A real Ask run goes through Owl, Beaver and Cat and ends with a report the web shows; real runs matched independently computed answers (top station, line totals, weekday versus weekend, a Korean station chip). Check and Compare still end as unconfigured and are shown as "Coming later". HEAD 12a069a. Nov 1 is a soft target (Nov 1 to 3).

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
| Docs batch 13 | 1f2dcfa | Records P10a to P10c and Ask = one CSV |
| Real caps | f4b40b2 | `limits.toml`: 150 runs and 600 calls a day for the site (#261) |
| P11 batch A | 108a974 | Example from `GET /api/example`, `lang`, P10 error messages, `RUN_ACTIVE` Watch link, usage tags, one CSV slot |
| P11 B1 | 9a82146 | Copy honesty on Home, auth, Plans, nav; `built` flag; 404 for mock reports, `/people`, `/my` |
| P12 | 3e9746b | Production compose, web image, host nginx conf, backups, runbook |
| Example | 4fa7f61 | Cached example regenerated from a real Seoul weekday run; sidecar meta file |
| P11 B2 | 1516cbb | Workspace and report copy, Seoul chips, sample CSV, example banner, favicon |
| P13 | 12a069a | Seoul sample pre-attached in Ask, uploaded only on Run |
Decisions for all of these: DECISIONS #99 to #273.

## What exists
### `web/`
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`, `/workspace` (Ask and run tabs), `/reports/[id]` (`/reports/example` is the public example from `GET /api/example`). `/my` and `/people` are `RoutePlaceholder` pages that answer 404 while their `built` flag in `nav-items.ts` is false; mock `rep_*` reports answer 404 in production (#263). Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/`, `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, RequireAuth), `plans/`, `report/`, workspace and run components.
- Real API code: `lib/api/` (client, errors, single-flight refresh), `lib/auth/` (api, hint, bootstrap, safe-next), `lib/run/live/` (submit, SSE watch, reducer, trace keys, storage). `lib/run/mock-run.ts` still drives the example run.
- Mocks: `web/mocks/*.json` with `index.ts`; types in `lib/types.ts`. The mock session helper and `dev_session` are gone (#179).
- Tests: Vitest (`npm test`). i18n: en and ko, locale from the `NEXT_LOCALE` cookie.
- Shell and screen deviations from the boards: DECISIONS #69 to #77, #79 to #98, #174 to #197.
### `api/` (FastAPI, Python 3.12 in Docker)
- Routes (all under `/api`): `GET /health`, `GET /ready`; `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /me`; `GET /usage`; `GET /example`; `POST /uploads`, `GET /uploads`, `GET /uploads/{id}`, `DELETE /uploads/{id}`; `POST /runs` (202, optional `Idempotency-Key`), `GET /runs/active`, `GET /runs/{id}`, `GET /runs/{id}/events` (SSE); `GET /reports/{id}` (owner only). Check the code before relying on this list.
- Services in `compose.yaml`: api, worker, scheduler, sandbox, db (pgvector), redis, and a one-shot `migrate` (runs as the migrator role). Dev mounts are in `compose.override.yaml`. `compose.prod.yaml` is the standalone production stack (P12, #268); `deploy/` holds `RUNBOOK.md`, `backup.sh`, `nginx/indesk.conf`, `env.prod.example` and `compose.rehearsal.yaml`. Migrations 0001 to 0004.
- Gateway (`app/ai/`), sandbox service (`api/sandbox/`), run machine and executor (`app/runs/`), Owl and Beaver with `AskFlow` (P8a, #198 to #210). Cat and the report (P9, #219 to #229).
- `api/config/models.toml` holds two chains (light and main, 3 entries each, #198). All six names were listed for the key. Per-entry `thinking_level` or `thinking_budget` (#214).
- Tests: `api/tests/` (pytest against real Postgres and Redis database 15, and a fake model client). Counts at HEAD 12a069a: 1060 api + 21 sandbox (`-m sandbox`) + 257 web (as reported by the owner for this batch; the full api check and `npm test` are re-run at the end of docs batch 14, see the batch report for the tails). CI jobs: `api`, `sandbox`, `web`.

## In progress
- Nothing.

## Next
1. **README and demo video (5.7).**
2. **Switch to indesk.uz** when the domain is active (RUNBOOK "Switch to indesk.uz").
3. **After Nov 3:** Hound first (PDF + RAG, unlocks Check), then Chameleon, then Compare.
- PLANNED, not built (#98): "Translate to <other language>" for real reports (not in API or web yet; 4.4 shows only a language note, #236).
- ROADMAP 2.16 holds the open polish and accessibility items collected so far; BACKLOG holds the post-deploy items.

## Later
### API gaps
- No retry endpoint for a failed agent (DATA.md lists `POST /runs/{id}/steps/{step}/retry`).
### Deploy checklist (done on 2026-10-27 unless marked)
- Done: `TRUSTED_PROXIES` is the pinned edge subnet; `ALLOWED_ORIGINS` is the public origin; Secure cookies, the proxy chain and SSE through nginx were checked on the live server (SECURITY.md section 7a); split DB roles (#255); `compose.prod.yaml` (#268); the real caps (#261).
- Not verified on the deployed stack: the sandbox cannot reach the network (ROADMAP 5.4).
- Paid Gemini key with a monthly limit: the owner sets the spend limit in Google AI Studio.
- Never run redis `FLUSHDB` on production.
- Fonts are still loaded from Google at runtime (BACKLOG).
### Polish
- Empty navbar auth slot before hydration.
- "Coming soon" text contrast is about 4.0:1.
- The time tile mixes browser and server clocks on resume.
- ~~Neutral chip style for "not available yet"~~ Done: the `soon` chip tone (#263).
- Korean text needs a native review (UI labels and report prose, #98).
### Other open items
- "Agents woken" is hard-coded "3 of 4" in the example run (#83); derive it from events for real runs.
- Agent icons at 128 px. (The favicon is done: `icon.svg` and `apple-icon.png`, #264.)
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
- Only an English example exists (#253, #266). The web shows it for every language; the report language note applies.

## Known issues
- Open polish items are listed above and under ROADMAP 2.16.
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- Sandbox isolation is best-effort: the kernel is shared with the host (#147).
- No malware scan; uploads stay `moderation=pending` (#138).
- Two tabs refreshing at the same moment can end the session (#126); the web reduces it with a lock (#177).

## Not verified
- Sandbox network isolation on the deployed stack.
- Safari, Firefox and a real phone reading a report or following a stream are untested (EventSource and the gzip fix were checked in Chrome only).
- The deployed server's checks were run by the owner and are as reported; no test covers them.
- Cost per run is an estimate from token counts and the price table (#217); `ai_calls.est_cost_usd` is still 0.
- The Korean text (UI labels, report prose and the 4.4 report strings) has not been reviewed by a native speaker.
- Whether a column is "the sum" cannot be proven in code; the prompt and live runs are the evidence (#242).
- A maximum-size CSV against the 1 GB sandbox, and the other stress cases of ROADMAP 5.3.
- The local rehearsal results of P12 are not recorded in git.
- Counts (api 1060, sandbox 21, web 257) are as reported by the owner; see the batch 14 report for the re-run.

## Environments
- Local: web http://localhost:3000 (dev server rewrites `/api` to the API), API http://127.0.0.1:8000 through `docker compose up --build`; Postgres and Redis run in Compose.
- Production: https://indesk.76-13-198-17.sslip.io on a Hostinger VPS (Ubuntu 26.04, x86_64) behind the host nginx, which also serves another app. Clone in `/root/Indesk` (read-only GitHub deploy key), `.env` sets `COMPOSE_FILE=compose.prod.yaml`, only `web` is published (127.0.0.1:4100), backups by host cron at 03:15 (7 days). Steps: `deploy/RUNBOOK.md`.

## Releases
- 2026-10-27: first deploy at the sslip.io address (HEAD 12a069a). No tags.
