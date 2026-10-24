# ROADMAP.md — Indesk v1

Lives at: `docs/ai/ROADMAP.md`. Last updated 2026-10-25.
UI-first. Order: 1) skeleton, tokens, layout; 2) each screen on mock data (shapes from `DATA.md`); 3) backend features matching `DATA.md`; 4) swap mock for real, one screen at a time; 5) deploy.
Each item is sized for 1 to 2 work sessions. Check a box only when the item's "done when" is true.

**Tiers (cut line decided Oct 25).** Every item has a tag:
- **[A]** core, planned for about Nov 1: the core backend (foundation, first working run, manager and critic, PDF and retrieval), Check, Compare, the full UI, the Gemini gateway and the cached example.
- **[B]** product layer: build as time allows; until built, those screens stay on mock data.
- **[C]** Vision (images, scanned PDFs, OCR test): after Nov 1.
If time runs out, cut from the bottom: [C] first, then [B] items from the bottom up. Never cut the cached example.

How to work: for each item, Claude writes a prompt, you paste it into a fresh Claude Code session, paste back the report, then commit. Never put keys in prompts. The Gemini key goes only in `api/.env` (ignored by git), and Claude Code never reads it.

## 1. Skeleton, design tokens, layout
- [ ] **1.1 [A] Repo and docs.** Create the repo with `web/`, `api/`, `docs/ai/`, `docs/security/`, `docs/design/`. Put `SPEC.md`, `DECISIONS.md`, `DATA.md`, `ROADMAP.md` in `docs/ai/`; `SECURITY.md` in `docs/security/`; `DESIGN.md` and the exported board PNGs (`Home.png`, `HomeM.png`, … as listed in `DESIGN.md`) in `docs/design/`. Add `AGENTS.md` and a `.gitignore` containing `.env` at the repo root. Done when: docs are in place and `.env` is ignored.
- [ ] **1.2 [A] Next.js app.** `web/`: Next.js App Router, TypeScript, one empty page per route in `DESIGN.md`. Done when: every route opens and shows its name.
- [ ] **1.3 [A] Design tokens.** `tokens.css` with all light and dark variables from `DESIGN.md`, fonts loaded, theme switch via `data-theme`, CSS Modules for components. Done when: a test page shows every color swatch in both themes.
- [ ] **1.4 [A] Base components.** Button (default, ink, primary, sm/lg), icon button, eyebrow, card, chip, demo notice. Touch targets at least 44 px on mobile. Done when: a components page shows each in light and dark.
- [ ] **1.5 [A] Layout shell.** Navbar (links, language switch, theme toggle, avatar), footer with the demo notice, 760 px breakpoint, signed-in/signed-out nav. Done when: it matches the Home board at 1280 and 390 px.
- [ ] **1.6 [A] Translations.** `next-intl`; `en` and `ko` files with keys for all UI text. Done when: switching language changes the navbar and footer.
- [ ] **1.7 [A] Mock data.** `web/mocks/*.json` using the example records in `DATA.md`, plus a development switch "signed in / signed out". Done when: a page can read a mock report.

## 2. Screens on mock data (one per item)
- [ ] **2.1 [A] Home.** Headline, looping silent demo (can be a recorded animation), "Try with an example", team, three modes.
- [ ] **2.2 [A] Log in.** Form and validation messages, fake submit.
- [ ] **2.3 [A] Sign up.** Form, fake submit, demo notice.
- [ ] **2.4 [A] Plans.** Cards and the custom plan calculator (price rule in `DECISIONS.md` #18), demo checkout screen.
- [ ] **2.5 [A] Workspace: Ask tab.** Tabs, mode switch, upload list, consent box with the demo notice, question box, chips, info blocks.
- [ ] **2.6 [A] Workspace: run tab.** Agent cards with expandable artifacts, handover card, trace driven by a timer on mock events, guardrails, "No run yet" state.
- [ ] **2.7 [A] Report (Ask).** Stamped final answer, Simple/Detailed, claims with evidence chips, confidence bar, follow-up thread.
- [ ] **2.8 [A] Style & download panel.** Template, typeface, size, format, Download button (shows a message).
- [ ] **2.9 [A] Share panel.** Private/shared states, copy link, expiry text, unshare.
- [ ] **2.10 [A] Report (Check).** Document-vs-computed rows, mismatch styling, "not checked" list.
- [ ] **2.11 [A] Report (Compare).** Totals, movers with bars, could-not-compare.
- [ ] **2.12 [A] Shared report.** Public read-only view, expired-link message.
- [ ] **2.13 [A] My page.** Reports list with status, Share/Unshare, delete with undo, file name list with "Deleted".
- [ ] **2.14 [A] People.** Search box, results, disabled Invite.
- [ ] **2.15 [A] Outcome cards.** All 9 run outcomes from the States board, plus the "busy today" message, used by Report and the run tab.
- [ ] **2.16 [A] Dark mode and mobile pass.** Every screen checked at 390 and 1280, light and dark, English and Korean. Done when: no horizontal scroll, no unreadable text, touch targets at least 44 px.

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
- [ ] **3.11 [A] Critic and report.** Claims with evidence refs, Cat's verdicts, "VERIFIED x/y", report API.
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
- [ ] **4.4 [A] Report (Ask).**
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
- [ ] **5.6 [A] Deploy.** One small VPS with Docker Compose and nginx, HTTPS, a free subdomain, env file for secrets. (`OPEN:` VPS company and subdomain service.)
- [ ] **5.7 [A] README and demo video.** README with "next steps" (the three parked ideas), the 1-minute demo recorded.
- [ ] **5.8 [B] Email verification.** After deploy, add email verification to sign-up.

## After v1 (not in this checklist)
Collaboration (members, invites, comments) and the fine-tuned router, in that order.

## OPEN questions in this file
1. VPS company and free subdomain service (5.6).
