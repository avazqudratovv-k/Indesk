# ROADMAP.md — Indesk v1

Lives at: `docs/ai/ROADMAP.md`. Last updated 2026-10-31. HEAD 93cbc38.
UI-first. Order: 1) skeleton, tokens, layout; 2) each screen on mock data (shapes from `DATA.md`); 3) backend features matching `DATA.md`; 4) swap mock for real, one screen at a time; 5) deploy.
Each item is sized for 1 to 2 work sessions. Check a box only when the item's "done when" is true.

**Tiers (cut line decided Oct 25).** Every item has a tag:
- **[A]** core, planned for about Nov 1: the core backend (foundation, first working run, manager and critic, PDF and retrieval), Check, Compare, the full UI, the Gemini gateway and the cached example.
- **[B]** product layer: build as time allows; until built, those screens stay on mock data.
- **[C]** Vision (images, scanned PDFs, OCR test): after Nov 1.
**Order (final, owner-approved 2026-10-25; replaces the earlier order-change note).** Nov 1 is a soft target (Nov 1 to 3) since 2026-10-26, not a hard date. A clean, full backend comes first; the frontend may lag.
- Before Nov 1: 2.7 Report (Ask) -> backend slice (3.1 Compose/CI, 3.2 state contract, 3.4 DB, 3.5 auth as small as is clean, 3.6 uploads CSV only, 3.7 sandbox, 3.8 Gemini gateway with the fake client first, 3.9 first real run with 3.3 SSE absorbed, 3.11 critic and report API, 3.10 failure gates with Owl, Beaver and Cat as the working agents) -> 4.1 to 4.4 swap mock to real -> failure cards from 2.15 (failed, not answerable, busy today) -> 5.1 Seoul demo data (the owner checks data.seoul.go.kr) -> 5.6 deploy with HTTPS -> 5.7 README and demo video.
- After Nov 1, the same URL grows: PDF and Hound (3.12), Check, Compare, then the Tier B screens 2.8, 2.9, 2.12, 2.13, 2.14, 2.16; also Vision (3.20), exports, plans and quotas, email verification.
- If a day slips, drop first: auth beyond the minimum, then 2.15 polish. The backend core is not dropped.
- **Post-deploy order (decided, #320).** After the one deploy: README and demo video (5.7), then Check a document (3.13), then Compare (3.14), then Vision (3.20), then account delete, then exports (3.17). Until then Check, Compare and Vision say "Not available yet".
- **Where we are (2026-10-31).** Done: P1 to P9 (3.1, 3.2, 3.4 to 3.8, run job and SSE, Owl and Beaver, first real Gemini calls, Cat and the report API) web 4.1 to 4.4, the P9 follow-up and the Korean least fix; P10a, P10b, P10c and Ask = one CSV; the real caps, P11, the regenerated example, P12 and P13; the first deploy (2026-10-27, HEAD 12a069a); P14a, P14b (live PDF test, #288) and the PDF web part (4.5A to 4.5C), the web honesty pass 4.7A to 4.7E, not answerable with reasons, the 6-hour session, My page (API, purge job, web) and the small API gaps. All of it is committed and **not deployed**; the live site stays untouched until the one deploy (checklist in STATE). Remaining order: **the one deploy** -> **README and demo video (5.7)** -> Check -> Compare -> Vision -> account delete -> exports; **indesk.uz switch** when the domain is active. Each step is listed below under "Remaining steps".

If time runs out, cut from the bottom: [C] first, then [B] items from the bottom up. Never cut the cached example.

How to work: for each item, Claude writes a prompt, you paste it into a fresh Claude Code session, paste back the report, then commit. Never put keys in prompts. The Gemini key goes only in `api/.env` (ignored by git), and Claude Code never reads it.

## 1. Skeleton, design tokens, layout
- [x] **1.1 [A] Repo and docs.** Create the repo with `web/`, `api/`, `docs/ai/`, `docs/security/`, `docs/design/`. Put `SPEC.md`, `DECISIONS.md`, `DATA.md`, `ROADMAP.md` in `docs/ai/`; `SECURITY.md` in `docs/security/`; `DESIGN.md`, the board sources in `docs/design/source/` and the board PNGs in `docs/design/png/` (names like `0. Home.png` and `Mobile · 0. Home.png`) in `docs/design/`. Add `AGENTS.md` and a `.gitignore` containing `.env` at the repo root. Done when: docs are in place and `.env` is ignored.
- [x] **1.2 [A] Next.js app.** `web/`: Next.js App Router, TypeScript, one empty page per route in `DESIGN.md`. Done when: every route opens and shows its name.
- [x] **1.3 [A] Design tokens.** `tokens.css` with all light and dark variables from `DESIGN.md`, fonts loaded, theme switch via `data-theme`, CSS Modules for components. Done when: a test page shows every color swatch in both themes.
- [x] **1.4 [A] Base components.** Button (default, ink, primary, sm/lg), icon button, eyebrow, card, chip, demo notice. Touch targets at least 44 px on mobile. Done when: a components page shows each in light and dark.
- [x] **1.5 [A] Layout shell.** Navbar (links, language switch, theme toggle, avatar), footer with the demo notice, 760 px breakpoint, signed-in/signed-out nav, mobile bottom tab bar (signed in: Home, Workspace, My, Plans; signed out: Home, Workspace, Plans). Done when: it matches the Home board at 1280 and 390 px. Shell changes after the first build: mobile navbar scrolls away and hides Log in / Sign up on the auth pages (#70), floating pill tab bar (#71), logo tilt (#72).
- [x] **1.6 [A] Translations.** `next-intl`; `en` and `ko` files with keys for all UI text. Done when: switching language changes the navbar and footer.
- [x] **1.7 [A] Mock data.** `web/mocks/*.json` using the example records in `DATA.md`, plus a development switch "signed in / signed out". Done when: a page can read a mock report.

## 2. Screens on mock data (one per item)
- [x] **2.1 [A] Home.** Headline, looping silent demo (can be a recorded animation), "Try with an example", team, three modes.
- [x] **2.2 [A] Log in.** Form and validation messages, fake submit.
- [x] **2.3 [A] Sign up.** Form, fake submit, demo notice.
- [x] **2.4 [A] Plans.** Cards and the custom plan calculator (price rule in `DECISIONS.md` #18, prices in KRW per #74), demo checkout screen.
- [x] **2.5 [A] Workspace: Ask tab.** Tabs, mode switch, upload list, consent box with the demo notice, question box, chips, info blocks. (Commit 52b8a70; additions in DECISIONS #80, #81.)
- [x] **2.6 [A] Workspace: run tab.** Agent cards with expandable artifacts, handover card, trace driven by a timer on mock events, guardrails, "No run yet" state. Built in four parts: 2.6a run tab and demo run (d89399d), 2.6b-1 agent tabs, handover, Owl and Cat views (1edb207), 2.6b-2 Chameleon, Beaver and Hound views (41cb257), follow-up fix (e771b11). Decisions #82 to #84.
- [x] **2.7 [A] Report (Ask).** Stamped final answer, Simple/Detailed, claims with evidence chips, confidence bar. Built in 339a5b2, fixed in e9f7d1e. Decisions #85 to #97. The follow-up thread, Share and Style & download are not built (#87).
- [x] **2.7b [A] Korean prose for mock reports.** `translations.ko` on rep_01 and rep_04, `ko` on their claims and evidence; number check script `web/scripts/check-report-numbers.mjs`. Built in e0dd7f6. Decision #98.
- [ ] **2.8 [A] Style & download panel.** Template, typeface, size, format, Download button (shows a message).
- [ ] **2.9 [A] Share panel.** Private/shared states, copy link, expiry text, unshare.
- [ ] **2.10 [A] Report (Check).** Document-vs-computed rows, mismatch styling, "not checked" list.
- [ ] **2.11 [A] Report (Compare).** Totals, movers with bars, could-not-compare.
- [ ] **2.12 [A] Shared report.** Public read-only view, expired-link message.
- [ ] **2.13 [A] My page.** Left open: built in part (1c4db61, f5db74a, c096fc7, 423b837; decisions #295, #302, #307 to #309, #316). Reports list and file list with delete, usage and account cards. Not built there: Share/Unshare, delete with undo (delete is hard, no undo, no refund), the Pro and settings toggles, Delete account (#308). Original text: reports list with status, Share/Unshare, delete with undo, file name list with "Deleted".
- [ ] **2.14 [A] People.** Search box, results, disabled Invite.
- [x] **2.15 [A] Outcome cards.** Done; ticked in docs batch 16 on the owner's list of stale items. The not answerable card with reason, file facts and chips and the per-outcome run mark were added (#293, #304 to #306).
- [ ] **2.16 [A] Dark mode and mobile pass.** Every screen checked at 390 and 1280, light and dark, English and Korean. Done when: no horizontal scroll, no unreadable text, touch targets at least 44 px.
  Open items collected while building 2.1 to 2.4:
  - [ ] Footer tagline contrast is 3.8 (needs 4.5).
  - [ ] Hero eyebrow and "See plans" worst-pixel contrast.
  - [ ] Phone section titles are 30 px vs 38 px on the board.
  - [ ] Reduced-motion tests across screens.
  - [ ] Mobile PNG comparisons against the boards.
  - [ ] Plans at exactly 360 px.
  - [ ] Plans phone row inset (40 px as on the board) may be too wide; user to decide.
  - [ ] Footer links and some text links are under 44 px.
  - [ ] Desktop calculator slider is 32 px (board value).
  - [ ] Stray `styles.login` class (renders "undefined") in `Navbar.tsx`.
  - [ ] Fonts are about 966 KB; trim at deploy (first paint about 2.7 MB).
  - [ ] Korean copy review by the user for Home, Auth and Plans (including the Home heading "누구를 위한 서비스인가요" and heading punctuation such as 결제가 완료되었어요.).
  - [ ] Safari, Firefox, a real touch device and a real screen reader are untested.
  - [ ] Free file size (5 MB, DECISIONS #79) comes from one source shared by the UI, mocks and backend.
  - [ ] The film board PNG renders blank, so the Home film is compared against the live design.

## 3. Backend features (match DATA.md)
- [x] **3.1 [A] Compose and CI.** Docker Compose with API, Postgres + pgvector, Redis, RQ worker; CI runs lint and tests. Done when: `docker compose up` gives a healthy API. Built in P1 (bc1cc5e); the scheduler and sandbox services were added in P4 and P5. Decisions #99 to #107.
- [x] **3.2 [A] State contract.** Pydantic models for `AgentState` and the trace event (fields from `DATA.md` `agent_steps`). Done when: tests validate the example records. Built in P2 (dd680e1); the trace line is in `app/runs/trace.py`. Decisions #108 to #118.
- [x] **3.3 [A] Dumb stream.** SSE endpoint pushes hardcoded AgentState events on a timer; the run tab reads it instead of the mock timer. Done when: cards turn from waiting to working to done. Absorbed: no separate timer stream was built; the real SSE endpoint came with the run job in P7 (debdb7b), and the run tab reads it since 4.3 (b2a13b2). The scripted agents (`RUNS_DEV_STUB`, development only) fill the role of the dumb stream. Decisions #162 to #173.
- [x] **3.4 [A] Database.** SQLAlchemy models and Alembic migrations for all v1 entities, including `ai_calls` and `usage_daily`. Built in P2 (dd680e1); migration 0002 (one active run per user) came with P7.
- [x] **3.5 [A] Auth.** Sign up, log in, refresh with rotation, log out, `me`; Argon2; short-lived access token in an httpOnly cookie; limit 5 sign-ups per hour per IP; no verification code. Built in P3 (fb57432). Decisions #119 to #127.
- [x] **3.6 [A] Uploads.** Type/size/plan limit checks, consent flag, storage interface on local disk, 24 h expiry sweep, list of file names. Built in P4 (b91b346), CSV only; the upload rate limit and max columns came in P5. The malware scan (ClamAV) is not built. Decisions #128 to #138.
- [x] **3.7 [A] Sandbox.** Docker container with no network runs pandas on a CSV and returns JSON. Done when: a malicious script cannot reach the network. Built in P5 (13bca05). Decisions #139 to #153. The sandbox is best-effort isolation (shared kernel, #147); the SECURITY.md pass (5.4) still has to check it.
- [x] **3.8 [A] Gemini gateway.** One server-side module for every model call: model IDs from a config file (confirm them in Google AI Studio first), the two fallback chains from `DECISIONS.md` #27 and #28, 35 s budget per request, retry on 429 and timeouts by moving to the next model, every call logged to `ai_calls`, per-user and global daily caps from `usage_daily`. Key from `api/.env` only. Done when: tests with a fake client prove the chain order, the time budget and both caps. Built in P6 (ed12345), decisions #154 to #161. The model names in `models.toml` are not verified and nothing has run against real Gemini (see P8b). `models.toml` holds the two chains of #27 and #28 since P8a (#198).
- [x] **3.9 [A] First real run (free tier, demo data only).** Owl picks a tool, Beaver runs it in the sandbox, steps stream to the UI, cost recorded. Split into P8a (agents and tests with the fake gateway) and P8b (live smoke test); the run job, state machine and SSE already exist (P7). Done in P8a (09e5340) and P8b (7897561). Cost is an estimate only; `ai_calls` records none yet.
- [x] **3.10 [A] Gates and outcomes.** (Part of P9; the step cap, one retry, token budget and the daily-cap refusal already exist from P7.) Answerability and quality gates, the six outcomes, skipped/failed/retry states, step cap, budget cap, refusal on a daily cap.
- [x] **3.11 [A] Critic and report.** (P9.) Claims with evidence refs, Cat's verdicts, "VERIFIED x/y", report API. PLANNED, not built (#98): translate action for real reports (one Gemini call on prose fields only, stored under `translations.<locale>`, number check rejects changed numbers); also compute `confidence` (thresholds high/medium/low are not defined yet).
- [ ] **3.12 [A] PDF and Hound.** **Update 2026-10-31:** the web part (4.5A to 4.5C) and the live check (P14b, #288, #289) are done; only the deploy of this part is open, so the box stays open until the one deploy. The text below is the 2026-10-30 status. Text extraction, chunking, Gemini embeddings (confirm the model and vector size first), keyword + semantic search, cited passages. **Split status (2026-10-30):** API side done, tested with the fake client only: text extraction in the isolated parser service, chunking, migration 0005, embeddings (`gemini-embedding-2`, 768; ID not yet confirmed live), hybrid search, Hound, the PDF writer and Cat's quote checks (P14a, 545495d and 2973536 with follow-ups; decisions #274 to #285). **Not done:** the web (accept PDF in Ask, PDF error messages, Hound and quote display; see STATE "PDF in the web"), the live check and tuning (P14b), the deploy of this part. The box stays open until the web part and P14b are done.
- [ ] **3.13 [A] Check a document.** Claim extraction, per-claim verdicts, "not checked" list.
- [ ] **3.14 [A] Compare.** Column alignment, differences, could-not-compare notes.
- [ ] **3.15 [B] Plans and quotas.** Quota from `usage_events`, plan limits, custom quote, simulated checkout behind a payments interface.
- [ ] **3.16 [B] Share, delete, retention.** Share links (7 days, revoke), delete with 7-day undo, hourly and daily sweeps. **Built partly (#297):** the daily `purge_expired` job deletes expired reports with their runs, old finished runs without a report and `ai_calls` older than 90 days. `usage_events`, `usage_daily` and `audit_log` are kept on purpose (#298). Share links, undo and the 7-day delete window are not built; delete is hard (#295).
- [ ] **3.17 [B] Exports.** PDF, Word, Excel, CSV with the 4 templates.
- [ ] **3.18 [B] People search.** Opt-in, 2+ characters, 20 results, 30 searches per minute.
- [ ] **3.19 [A] Benchmark.** 50 questions (including Check and Compare) in CI, score saved to `benchmark_runs`. Runs against a fake model client in CI and against real Gemini only by hand, so CI never spends the daily cap.
- [ ] **3.20 [C] Vision (after Nov 1).** Image moderation gate, OCR test on 4 to 5 photos per language (Korean, Japanese, Russian, Uzbek) against the three candidates, OCR with confidence, Gemini vision fallback. Done when: the test table is written into `DECISIONS.md`.

## Remaining steps (added 2026-10-26)
Names used in commits and in STATE. Each is sized for one to two sessions. Check a box only when its "done when" is true.
- [x] **P8a [A] Owl and Beaver (fake gateway).** Prompts and structured output for Owl (plan) and Beaver (pandas code through the sandbox), the agents wired into the executor, tests against the fake gateway and a synthetic demo CSV. Done when: a run on the synthetic CSV ends `answered` or `partial` in tests, with trace lines, and no real model is called. (Covers the agent half of 3.9.) Built in 09e5340; decisions #198 to #210. Nothing has run against real Gemini.
- [x] **P8b [A] Live smoke test.** Run `scripts/list_models.py` with the real key and fix `models.toml`; run one real Ask on the Seoul CSV by hand (free tier, public data only). Done when: the model names are confirmed, the run completes or fails with a clear reason, and the result is written in STATE and DECISIONS (resolves OPEN 2 and 5 in DECISIONS). (Finishes 3.9.) Built in 7897561; decisions #211 to #218. Four real runs (three question types, one in Korean) ended answered and matched independently computed answers. Results of the carried-forward checks:
  - Korean column names work end to end. Upload is UTF-8 with a BOM, handled by `utf-8-sig`; cp949 was not needed for this file.
  - "Grew fastest since X" was not tested: the file covers one month. Add a plan task only if a multi-month file ever needs it.
  - Thinking field and model names: confirmed for the entries tested (#214). Two chain entries are still untested (see P9). Real rate limits per name are still open (owner reads aistudio.google.com/rate-limit).
- [x] **P9 [A] Cat and the report API.** Done in fae02e5 (test fix 5c12875); decisions #219 to #229. Both probe entries returned HTTP 200 live. Cat's verdicts, claims with evidence refs, "VERIFIED x/y", confidence thresholds, gates and the six outcomes, `GET /api/reports/{id}`; the translate action stays PLANNED (#98). Done when: tests prove a claim without evidence is never `verified` and the report API checks ownership. (3.10 and 3.11.) Carried forward from P8a: Cat treats result strings as untrusted data, because they can come from CSV cells. Carried forward from P8b: the prompt includes two one-call probes, one for the third light entry (`gemini-3.8-flash`, thinking_budget 0) and one for the second main entry (`gemini-3.6-flash`, thinking_budget 1024), so the budget-0 setting on 3.8-flash is verified or fixed.
- [x] **4.4 [A] Report (Ask) on the real API.** Done in 294f9da; decisions #230 to #241. The web translates the `verify` trace key and the evidence `reason` and `method` codes; no code and no chart in v1; the "not connected yet" line is gone. English question 2 (line totals) ran live in P8b, in 4.4 and in the follow-up.
- [x] **P9 follow-up [A] Report quality.** Done in 1fe735a; decision #242. `add_metrics` sums, unique labels, number grouping, plain column words; prompts owl-2, beaver-2, cat-2.
- [x] **Korean least fix [A].** Done in e6103d0; decision #243. Korean least wording is checked against the column minimum.
- [x] **P10a [A] Run gates and quotas.** Done in 7eb642a; decisions #245 to #252. Run gates, free quota, daily run caps, `GET /api/usage`, failure kind in `ai_calls`. The cap values are placeholders (DECISIONS OPEN 6).
- [x] **P10b [A] Example and `lang`.** Done in c73fc54; decisions #253, #254. `GET /api/example` from a static export; `lang` on the report.
- [x] **P10c [A] DB roles, compose split, API gaps.** Done in be59343; decisions #255 to #257. Migrator and app roles, `migrate` service, `compose.override.yaml`, `RUN_ACTIVE` with `run_id`, `GET /api/runs/active`, `DELETE /api/uploads/{id}`, `no-transform` on the stream.
- [x] **Ask = one CSV [A].** Done in 43dd394; decision #258. `TOO_MANY_FILES` (422) at `POST /runs`.
- [x] **P11 [A] Web copy honesty (batch A, B1, B2).** Done in 108a974 (A: example from `GET /api/example`, `lang`, P10 error messages, `RUN_ACTIVE` Watch link, usage tags, one CSV slot), 9a82146 (B1: copy honesty, `built` flag, 404 for mock reports), 1516cbb (B2: Workspace and report copy, Seoul chips, sample CSV, example banner, favicon). Decisions #262 to #265.
- [x] **P12 [A] Production deploy files.** Done in 3e9746b; decisions #268 to #270. `compose.prod.yaml`, web image, host nginx conf, backups, `deploy/RUNBOOK.md`. The local rehearsal results are not recorded.
- [x] **Real caps [A].** Done in f4b40b2; decision #261. 150 runs and 600 calls a day for the site, 10 runs and 50 calls a day per user, 3 free runs.
- [x] **Example regeneration [A].** Done in 4fa7f61; decisions #266, #267.
- [x] **P13 [A] Seoul sample pre-attached in Ask.** Done in 12a069a (with the follow-up d170dce); decisions #272, #286.
- [x] **P14a [A] PDF in Ask, API side.** Part 1 in 545495d (isolated parser service, upload codes and limits, migration 0005), part 2 in 2973536 (embeddings, hybrid retrieval, Hound, PDF writer, Cat quote checks, CI job `parser`), then the 20,000 row limit (5c7471e), the demo PDFs (22ae66c) and the follow-ups eaefadf (`found=false`, cosines, `--reset-quota`), 773257a (Cat number rule, own daily counters), befb65d, 75705de, 45e371c (test fixes). Decisions #274 to #287. Done when (API side): tests prove the PDF flow with the fake client. Fake client only; not run against real Gemini; not recorded as deployed.
- [x] **P14b [A] PDF: live check, tuning and the web part.** Done (live test 13 of 14 calls, #288; floor kept at 0.5, #289; quantity-word check, chunk guard, 250,000 embedding budget, #290, #291; web 4.5A to 4.5C, #300). The embedding price stays unverified. The deploy that creates the pgvector extension first is still open (#321). Original text:  The owner confirms the embedding model ID live (`scripts/list_models.py --embed`) and runs `scripts/smoke_live.py` on the two demo PDFs (en, ko) against `seoul_subway_2026-09_summary_truth.json`; tune `retrieval_min_similarity` (0.5 is a guess), the chunk sizes and the embedding price; then the web part (STATE "PDF in the web") and a deploy that first creates the pgvector extension on the existing volume (#287). Closes 3.12 when done.
- [x] **P10 [A] Quotas, busy today and deploy hardening (parent; the original text is kept below).** Ticked 2026-10-30 with these still open: the retry endpoint (not built; STATE "API gaps"), `est_cost_usd` (still 0, optional), and whether "busy today" is shown as the 2.15 outcome card (2.15 is unchecked; not verified). Closed since: real cap values (f4b40b2), the web parts of 5.1 (P11), free-run counting tags (#262), split DB roles (#255), the `compose.yaml` mount (#256). Note: the "done when" below says no open API item is left in STATE, and the retry endpoint is still listed there; the box is ticked at the owner's instruction. Original text: real values for the caps, the retry endpoint, `est_cost_usd`, and the web parts listed in 5.1. Plan quota and counting (free runs, "Uses 1 of your 2 free runs"), `daily_cap_user`, `daily_cap_global` and `model_busy` shown as "busy today" (2.15), restore the counting tags (#195), split DB roles (#118), remove the `compose.yaml` mount from the api service (#152), retry endpoint if the copy still promises it. Done when: the deploy checklist in STATE has no open API or Compose item. Carried forward from P8b: store the failure KIND of an HTTP 400 in `ai_calls` (today any 400 is stored only as OTHER, so the cause of a fallback is hidden); wire `est_cost_usd` in `ai_calls` if wanted for internal monitoring (#217); read the real rate limits per model name before setting the daily caps. Follow-up from P8a: one HTTP-level test (a full run, then `GET /runs/{id}` and the SSE stream, with the sentinel absent from both). Add `lang` to the report (additive field), so the web can drop the extra `GET /runs/{id}` fetch (#236).
- [ ] **5.x [A] Deploy section.** After P10: 5.1 Seoul demo data, 5.2 cached example, 5.3 stress tests, 5.4 security pass, 5.5 paid tier, 5.6 deploy, 5.7 README and demo video (see section 5; the order in "Order (final)" above still puts 5.1, 5.6 and 5.7 first when time is short).

## 4. Swap mock to real (per screen)
Do in this order. For each: replace mock reads with API calls, keep the mock as a test fixture, check loading, empty and error states.
- [x] **4.1 [A] Log in and Sign up.** Built in a5461cd (with 4.2). Decisions #174 to #183.
- [x] **4.2 [A] Workspace Ask tab (real upload and run start).** Built in a5461cd (real auth, Log out, disabled Check and Compare) and finished in b2a13b2 (upload and run start). Ask only; CSV only.
- [x] **4.3 [A] Run tab (real SSE).** Built in b2a13b2. Decisions #184 to #197. EventSource was checked in Chrome only.
- [x] **4.4 [A] Report (Ask).** Done in 294f9da (see the item above). PLANNED, not built (#98): "Translate to <other language>" button, result labelled "AI translation", shown when the report language differs from the site language.
- [ ] **4.5 [A] Check report.**
- [ ] **4.6 [A] Compare report.**
- [x] **4.7 [A] Home "Try with an example"** (cached real result). Done; ticked in docs batch 16 on the owner's list of stale items. The example reads `GET /api/example` since P11 (#262); web steps 4.7A to 4.7E followed (#301, #303, #318).
- [ ] **4.8 [B] My page.** Left open: the real page and API are built (see 2.13); Share and undo are not.
- [ ] **4.9 [B] Share panel and Shared report.**
- [ ] **4.10 [B] Style & download (real exports).**
- [ ] **4.11 [B] Plans and demo checkout.**
- [ ] **4.12 [B] People.**

## 5. Deploy
- [x] **5.1 [A] Seoul demo data.** Ticked 2026-10-30: the CSV is committed (86fe0b2) and the web copy matches it (P11, #262 to #264); two generated demo PDFs (en, ko) with a ground-truth file exist (22ae66c, #285). Not built from the original text: the "brief with planted errors" and the small and big sets; the chart photo waits for Vision. The "Still to do" text below is kept as written and is done, except those. Original: the CSV is committed (86fe0b2, `docs/demo-data/seoul_subway_2026-09.csv`, #216). Still to do: a copy-honesty prompt that changes the question chips and example copy to match the one-month Seoul file (for example "total boardings per day"; say which average is meant). Exact weekday question wording (#244): "Compare weekdays and weekends: average total boardings per day" (mean of daily network totals) and adds the source line "Source: Seoul Metropolitan Government, Korail, Airport Railroad (Seoul Open Data Plaza), KOGL Type 1". Web part of the copy-honesty step (from P10, DECISIONS #251, #254, #257 to #259): swap the mock example for `GET /api/example`; use `lang` on the report and drop the extra run fetch; add `TOO_MANY_FILES` and `UPLOAD_IN_USE` messages in en and ko (and to `knownCodes`); show the free-run counting tags from `GET /api/usage`; limit the Ask dropzone to one CSV; handle "no active run" (204) versus `RUN_ACTIVE` with `run_id`. Original task text: the user checks the dataset at data.seoul.go.kr and reports its columns and row count; then write the demo brief with planted errors (labelled demo), the small and big sets. (The chart photo joins with Vision, after Nov 1.)
- [x] **5.2 [A] Cached example.** Pre-run and store the example so it loads instantly and costs no AI calls. Done in c73fc54 (`GET /api/example`) and regenerated from a real run in 4fa7f61 (#253, #266, #267); the web reads it since P11 (#262). English only.
- [ ] **5.3 [A] Stress tests.** Biggest allowed CSV, a bad PDF, an empty file, a cap reached, all models failing. Done when: every case ends in a clear outcome.
- [ ] **5.4 [A] Security pass.** Walk through `docs/security/SECURITY.md`; rate limits, sandbox test, access tests, key check (the key never reaches the browser or logs).
- [ ] **5.5 [A] Switch to the paid tier.** Before anyone uploads their own files: create the paid-tier key with billing on and a $20 monthly limit, replace the key in the server env file, remove the free-tier key. Done when: the demo notice no longer needs the free-tier warning.
- [x] **5.6 [A] Deploy.** One small VPS with Docker Compose and nginx, HTTPS, a free subdomain, env file for secrets. The VPS is the one used for the user's other project, with an sslip.io hostname. Done 2026-10-27 at https://indesk.76-13-198-17.sslip.io (HEAD 12a069a, #268 to #271, `deploy/RUNBOOK.md`), checks as reported by the owner. Open: the switch to indesk.uz; everything since 12a069a (P14a, P14b, the web parts, My page, 6-hour session) waits for the one deploy (the pgvector extension step, #287; checklist in STATE, #321).
- [ ] **5.7 [A] README and demo video.** README with "next steps" (the three parked ideas), the 1-minute demo recorded. The README must say plainly that a question about data the file lacks can be answered with other columns, disclosed in the first sentence (#319). First item after the deploy (#320).
- [ ] **5.8 [B] Email verification.** After deploy, add email verification to sign-up.

## After v1 (not in this checklist)
Collaboration (members, invites, comments) and the fine-tuned router, in that order.

Later, carried forward from P8a (no step assigned yet):
- An explicit "cannot answer from this file" plan. Owl currently always plans.
- A richer CSV profile (distinct counts, min and max).

## OPEN questions in this file
None.
