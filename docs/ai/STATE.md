# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-26

## Status in one line
Screens 2.1 to 2.7b are done on mock data. The backend foundation (P1 to P7), the Ask flow with Owl and Beaver (P8a) and the web swap for log in, sign up and the Ask run (4.1 to 4.3) are committed. A real Ask run goes through Owl and Beaver on the fake gateway in tests and ends `answered` with no report (Cat and reports come in P9); Check and Compare still end as unconfigured. HEAD 09e5340. Nov 1 is now a soft target (Nov 1 to 3), not a hard date. **No real Gemini call has happened.** The model names, the thinking field for `gemini-3.x` and the prompt text are untested.

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
Decisions for all of these: DECISIONS #99 to #210.

## What exists
### `web/`
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`, `/workspace` (Ask and run tabs), `/reports/[id]`. `/my` and `/people` are `RoutePlaceholder` pages behind `RequireAuth`. Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/`, `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, RequireAuth), `plans/`, `report/`, workspace and run components.
- Real API code: `lib/api/` (client, errors, single-flight refresh), `lib/auth/` (api, hint, bootstrap, safe-next), `lib/run/live/` (submit, SSE watch, reducer, trace keys, storage). `lib/run/mock-run.ts` still drives the example run.
- Mocks: `web/mocks/*.json` with `index.ts`; types in `lib/types.ts`. The mock session helper and `dev_session` are gone (#179).
- Tests: Vitest (`npm test`). i18n: en and ko, locale from the `NEXT_LOCALE` cookie.
- Shell and screen deviations from the boards: DECISIONS #69 to #77, #79 to #98, #174 to #197.
### `api/` (FastAPI, Python 3.12 in Docker)
- Routes (all under `/api`): `GET /health`, `GET /ready`; `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /me`; `POST /uploads`, `GET /uploads`, `GET /uploads/{id}`; `POST /runs` (202, optional `Idempotency-Key`), `GET /runs/{id}`, `GET /runs/{id}/events` (SSE). Check the code before relying on this list.
- Services in `compose.yaml`: api, worker, scheduler, sandbox, db (pgvector), redis. Migrations 0001 and 0002.
- Gateway (`app/ai/`), sandbox service (`api/sandbox/`), run machine and executor (`app/runs/`), Owl and Beaver with `AskFlow` (P8a, #198 to #210). Cat is not built; see "Next".
- `api/config/models.toml` holds two chains (light and main, 3 entries each, #198); the names are unverified.
- Tests: `api/tests/` (pytest against real Postgres and Redis database 15, and a fake model client). Counts reported for P8a: 796 api + 20 sandbox (`-m sandbox`) + 138 web. CI jobs: `api`, `sandbox`, `web`. These were not re-run in the docs batch.

## In progress
- Nothing.

## Next
1. **P8b:** live smoke test with the real Gemini key and the Seoul CSV (run `scripts/list_models.py` first; confirm model IDs, the thinking field name and prices; DECISIONS OPEN 5).
2. **P9:** Cat (critic), claims and evidence, the report API.
3. **Web 4.4:** Report (Ask) on the real API; remove the line "Results appear in the report (not connected yet)".
4. **P10:** quotas and counting, "busy today" cards, split DB roles, deploy fixes from the checklist below.
5. **5.x:** Seoul demo data, cached example, stress tests, security pass, paid tier, deploy, README and video.
- PLANNED, not built (#98): "Translate to <other language>" for real reports (API in P9, UI in 4.4); dropped first if a day slips.
- ROADMAP 2.16 holds the open polish and accessibility items collected so far.

## Later
### API gaps
- `RUN_ACTIVE` (409) carries no run id.
- No endpoint for the active run (the web keeps the id in localStorage, #185).
- No `DELETE /uploads/{id}`.
- `TOO_MANY_STREAMS` (429) reaches the browser as an anonymous error.
- The SSE stream has no `Cache-Control: no-transform` (it sends `no-cache` and `X-Accel-Buffering: no`).
- No retry endpoint for a failed agent (DATA.md lists `POST /runs/{id}/steps/{step}/retry`).
### Deploy checklist
- `TRUSTED_PROXIES` must cover the proxy, or all visitors share one rate-limit bucket.
- `ALLOWED_ORIGINS` set to the public origin.
- Secure cookies (set automatically when `APP_ENV=production`; test it).
- nginx: `proxy_buffering off` and compression for the SSE route.
- Split DB roles: a migrator and a limited app role; test that the app role cannot DROP TABLE (#118).
- Remove the `compose.yaml` mount from the api service (#152).
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
- An unknown report id returns HTTP 200 instead of 404 (#94).
- Report claim rows are narrower on phones (board quirk, #95).
- Evidence table cell text is not compared with the board.
- Define the confidence thresholds (high/medium/low) in the backend in P9; the mock stores `confidence` as a literal.
- Share and Style & download (2.8, 2.9) and the follow-up thread are built after Nov 1 (#87).
- One source for the 5 MB file limit: the server now reads `limits.toml` (#128); `web/lib/workspace/validate.ts` and `web/mocks/plans.json` still hold copies.
- `GET /api/example` and the cached example do not exist yet (ROADMAP 5.2); Home "Try with an example" still uses the mock.

## Known issues
- Open polish items are listed above and under ROADMAP 2.16.
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- The API connects to Postgres as the superuser until P10 (#118).
- Sandbox isolation is best-effort: the kernel is shared with the host (#147).
- No malware scan; uploads stay `moderation=pending` (#138).
- Two tabs refreshing at the same moment can end the session (#126); the web reduces it with a lock (#177).

## Not verified
- No real Gemini call has happened. The model names in `api/config/models.toml`, the thinking field for `gemini-3.x` (`thinkingBudget` or `thinkingLevel`) and the Owl and Beaver prompt text are untested (DECISIONS OPEN 2 and 5).
- EventSource and the gzip fix were checked in Chrome only. Safari, Firefox and real phones are untested.
- The Korean text has not been reviewed by a native speaker.
- Build, lint, typecheck and tests were not re-run in this docs batch.

## Environments
- Local: web http://localhost:3000 (dev server rewrites `/api` to the API), API http://127.0.0.1:8000 through `docker compose up --build`; Postgres and Redis run in Compose.
- Production: not deployed yet.

## Releases
- None yet.
