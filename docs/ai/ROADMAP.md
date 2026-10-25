# ROADMAP.md — Indesk v1

Lives at: `docs/ai/ROADMAP.md`. Last updated 2026-10-25. HEAD e9f7d1e.
UI-first. Order: 1) skeleton, tokens, layout; 2) each screen on mock data (shapes from `DATA.md`); 3) backend features matching `DATA.md`; 4) swap mock for real, one screen at a time; 5) deploy.
Each item is sized for 1 to 2 work sessions. Check a box only when the item's "done when" is true.

**Tiers (cut line decided Oct 25).** Every item has a tag:
- **[A]** core, planned for about Nov 1: the core backend (foundation, first working run, manager and critic, PDF and retrieval), Check, Compare, the full UI, the Gemini gateway and the cached example.
- **[B]** product layer: build as time allows; until built, those screens stay on mock data.
- **[C]** Vision (images, scanned PDFs, OCR test): after Nov 1.
**Order (final, owner-approved 2026-10-25; replaces the earlier order-change note).** Hard date: Nov 1. A clean, full backend comes first; the frontend may lag.
- Before Nov 1: 2.7 Report (Ask) -> backend slice (3.1 Compose/CI, 3.2 state contract, 3.4 DB, 3.5 auth as small as is clean, 3.6 uploads CSV only, 3.7 sandbox, 3.8 Gemini gateway with the fake client first, 3.9 first real run with 3.3 SSE absorbed, 3.11 critic and report API, 3.10 failure gates with Owl, Beaver and Cat as the working agents) -> 4.1 to 4.4 swap mock to real -> failure cards from 2.15 (failed, not answerable, busy today) -> 5.1 Seoul demo data (the owner checks data.seoul.go.kr) -> 5.6 deploy with HTTPS -> 5.7 README and demo video.
- After Nov 1, the same URL grows: PDF and Hound (3.12), Check, Compare, then the Tier B screens 2.8, 2.9, 2.12, 2.13, 2.14, 2.16; also Vision (3.20), exports, plans and quotas, email verification.
- If a day slips, drop first: auth beyond the minimum, then 2.15 polish. The backend core is not dropped.

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
- [ ] **2.13 [A] My page.** Reports list with status, Share/Unshare, delete with undo, file name list with "Deleted".
- [ ] **2.14 [A] People.** Search box, results, disabled Invite.
- [ ] **2.15 [A] Outcome cards.** All 9 run outcomes from the States board, plus the "busy today" message, used by Report and the run tab.
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
- [ ] **3.1 [A] Compose and CI.** Docker Compose with API, Postgres + pgvector, Redis, RQ worker; CI runs lint and tests. Done when: `docker compose up` gives a healthy API.
- [ ] **3.2 [A] State contract.** Pydantic models for `AgentState` and the trace event (fields from `DATA.md` `agent_steps`). Done when: tests validate the example records.
- [ ] **3.3 [A] Dumb stream.** SSE endpoint pushes hardcoded AgentState events on a timer; the run tab reads it instead of the mock timer. Done when: cards turn from waiting to working to done.
- [ ] **3.4 [A] Database.** SQLAlchemy models and Alembic migrations for all v1 entities, including `ai_calls` and `usage_daily`.
- [ ] **3.5 [A] Auth.** Sign up, log in, refresh with rotation, log out, `me`; Argon2; short-lived access token in an httpOnly cookie; limit 5 sign-ups per hour per IP; no verification code.
- [ ] **3.6 [A] Uploads.** Type/size/plan limit checks, consent flag, storage interface on local disk, 24 h expiry sweep, list of file names.
- [ ] **3.7 [A] Sandbox.** Docker container with no network runs pandas on a CSV and returns JSON. Done when: a malicious script cannot reach the network.
- [ ] **3.8 [A] Gemini gateway.** One server-side module for every model call: model IDs from a config file (confirm them in Google AI Studio first), the two fallback chains from `DECISIONS.md` #27 and #28, 35 s budget per request, retry on 429 and timeouts by moving to the next model, every call logged to `ai_calls`, per-user and global daily caps from `usage_daily`. Key from `api/.env` only. Done when: tests with a fake client prove the chain order, the time budget and both caps.
- [ ] **3.9 [A] First real run (free tier, demo data only).** Owl picks a tool, Beaver runs it in the sandbox, steps stream to the UI, cost recorded.
- [ ] **3.10 [A] Gates and outcomes.** Answerability and quality gates, the six outcomes, skipped/failed/retry states, step cap, budget cap, refusal on a daily cap.
- [ ] **3.11 [A] Critic and report.** Claims with evidence refs, Cat's verdicts, "VERIFIED x/y", report API. PLANNED, not built (#98): translate action for real reports (one Gemini call on prose fields only, stored under `translations.<locale>`, number check rejects changed numbers); also compute `confidence` (thresholds high/medium/low are not defined yet).
- [ ] **3.12 [A] PDF and Hound.** Text extraction, chunking, Gemini embeddings (confirm the model and vector size first), keyword + semantic search, cited passages.
- [ ] **3.13 [A] Check a document.** Claim extraction, per-claim verdicts, "not checked" list.
- [ ] **3.14 [A] Compare.** Column alignment, differences, could-not-compare notes.
- [ ] **3.15 [B] Plans and quotas.** Quota from `usage_events`, plan limits, custom quote, simulated checkout behind a payments interface.
- [ ] **3.16 [B] Share, delete, retention.** Share links (7 days, revoke), delete with 7-day undo, hourly and daily sweeps (including the 90-day cleanup of usage and audit rows).
- [ ] **3.17 [B] Exports.** PDF, Word, Excel, CSV with the 4 templates.
- [ ] **3.18 [B] People search.** Opt-in, 2+ characters, 20 results, 30 searches per minute.
- [ ] **3.19 [A] Benchmark.** 50 questions (including Check and Compare) in CI, score saved to `benchmark_runs`. Runs against a fake model client in CI and against real Gemini only by hand, so CI never spends the daily cap.
- [ ] **3.20 [C] Vision (after Nov 1).** Image moderation gate, OCR test on 4 to 5 photos per language (Korean, Japanese, Russian, Uzbek) against the three candidates, OCR with confidence, Gemini vision fallback. Done when: the test table is written into `DECISIONS.md`.

## 4. Swap mock to real (per screen)
Do in this order. For each: replace mock reads with API calls, keep the mock as a test fixture, check loading, empty and error states.
- [ ] **4.1 [A] Log in and Sign up.**
- [ ] **4.2 [A] Workspace Ask tab (real upload and run start).**
- [ ] **4.3 [A] Run tab (real SSE).**
- [ ] **4.4 [A] Report (Ask).** PLANNED, not built (#98): "Translate to <other language>" button, result labelled "AI translation", shown when the report language differs from the site language.
- [ ] **4.5 [A] Check report.**
- [ ] **4.6 [A] Compare report.**
- [ ] **4.7 [A] Home "Try with an example"** (cached real result).
- [ ] **4.8 [B] My page.**
- [ ] **4.9 [B] Share panel and Shared report.**
- [ ] **4.10 [B] Style & download (real exports).**
- [ ] **4.11 [B] Plans and demo checkout.**
- [ ] **4.12 [B] People.**

## 5. Deploy
- [ ] **5.1 [A] Seoul demo data.** The user checks the dataset at data.seoul.go.kr and reports its columns and row count; then write the demo brief with planted errors (labelled demo), the small and big sets. (The chart photo joins with Vision, after Nov 1.)
- [ ] **5.2 [A] Cached example.** Pre-run and store the example so it loads instantly and costs no AI calls.
- [ ] **5.3 [A] Stress tests.** Biggest allowed CSV, a bad PDF, an empty file, a cap reached, all models failing. Done when: every case ends in a clear outcome.
- [ ] **5.4 [A] Security pass.** Walk through `docs/security/SECURITY.md`; rate limits, sandbox test, access tests, key check (the key never reaches the browser or logs).
- [ ] **5.5 [A] Switch to the paid tier.** Before anyone uploads their own files: create the paid-tier key with billing on and a $20 monthly limit, replace the key in the server env file, remove the free-tier key. Done when: the demo notice no longer needs the free-tier warning.
- [ ] **5.6 [A] Deploy.** One small VPS with Docker Compose and nginx, HTTPS, a free subdomain, env file for secrets. The VPS is the one used for the user's other project, with an sslip.io hostname.
- [ ] **5.7 [A] README and demo video.** README with "next steps" (the three parked ideas), the 1-minute demo recorded.
- [ ] **5.8 [B] Email verification.** After deploy, add email verification to sign-up.

## After v1 (not in this checklist)
Collaboration (members, invites, comments) and the fine-tuned router, in that order.

## OPEN questions in this file
None.
