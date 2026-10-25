# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-25

## Status in one line
ROADMAP 1.1 to 1.7 and screens 2.1 to 2.7 (Home, Log in, Sign up, Plans, Workspace Ask tab, Workspace run tab, Report (Ask)) and 2.7b (Korean prose for mock reports) are done and committed, all on mock data. HEAD e0dd7f6. Next is the backend slice, starting with 3.1 Compose/CI. Hard date: Nov 1.

## What exists (`web/`)
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`. Other routes are `RoutePlaceholder` pages. Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/` (Button, Card, Chip, DemoNotice, Eyebrow), `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider, DevSessionSwitch), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, `validate.ts`), `plans/` (PlansView, PlanCard, CustomCalculator, Checkout, UsagePanel, EnforceCard).
- Mocks: `web/mocks/*.json` (users, uploads, runs, run-files, reports, claims, evidence, share-links, plans) with `index.ts`; types in `lib/types.ts`.
- Helpers: `lib/plans/` (`calc.ts`, `card.ts`, `format.ts`), `lib/session.ts` and `session-server.ts` (mock `dev_session` cookie), `lib/theme.ts`, `hooks/` (`use-session`, `use-theme`), `i18n/` (en and ko, locale from the `NEXT_LOCALE` cookie), `messages/en.json` and `ko.json`.
- Shell behaviour and screen deviations from the boards: DECISIONS #69 to #77 (shell, auth, plans) and #79 to #84 (workspace Ask and run tabs) and #85 to #97 (Report).
- Report (Ask) at `/reports/[id]`: `components/report/`, helpers in `lib/report/`. Follow-up thread, Share and Style & download are not built (#87).

## In progress
- Nothing.

## Next
1. Backend slice, in the order set in ROADMAP "Order (final)": 3.1 Compose/CI, 3.2 state contract, 3.4 DB, 3.5 auth, 3.6 uploads (CSV only), 3.7 sandbox, 3.8 Gemini gateway (fake client first; confirm model IDs in AI Studio first), 3.9 first real run with 3.3 SSE, 3.11 critic and report API, 3.10 failure gates.
2. Then 4.1 to 4.4, the failure cards (2.15), 5.1, 5.6, 5.7.
   - PLANNED, not built (#98): "Translate to <other language>" for real reports (API in 3.11, UI in 4.4); after the failure cards, before polish only; dropped first if a day slips.
3. ROADMAP 2.16 holds the open polish and accessibility items collected so far.

## Later (collected during 2.5 to 2.7b)
- When runs become real, derive "Agents woken" from events (it is hard-coded "3 of 4" from the board, #83).
- 2.5b: synthetic sample files for the Ask tab.
- Favicon (`favicon.ico` returns 404; ROADMAP 2.16) and agent icons at 128 px.
- Check the "Chameleon" word width in Safari and Firefox.
- Production check that `?mockOutcome` is ignored (#82).
- Contrast of the error pill, the disabled Run button and the counter.
- Before the backend: decide which agent steps truly use an LLM (Owl is rule-based in v1, #61), so README claims stay accurate.
- After section 4: compare 5 questions against a plain chatbot for the README.
- "Real runs": replace the scripted events in `use-mock-run` with server events; remove the Demo banner and the Example tags only when the numbers are real.
- An unknown report id returns HTTP 200 instead of 404 (#94).
- Report claim rows are narrower on phones (board quirk, #95); look at it in 2.16.
- Native review of the Korean report prose and the Korean UI labels (the Korean was written by Claude, #98).
- Safari, Firefox and a real touch device are untested for the Report.
- No test runner yet (for example unit checks of `lib/report/view.ts`).
- Evidence table cell text is not compared with the board.
- `GET /workspace/reports` returns 404: hide or remove links to unbuilt pages before deploy (nav links, "My page", reports list).
- Define the confidence thresholds (high/medium/low) in the backend in 3.11; today the mock stores `confidence` as a literal.
- Share and Style & download (2.8, 2.9) and the follow-up thread are built after Nov 1 (#87).
- One source for the 5 MB file limit (#79) is created in backend 3.6 (also a ROADMAP 2.16 line).

## Known issues
- Open polish items (contrast, sizes, Korean copy review, untested browsers) are listed under ROADMAP 2.16.
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- Korean UI text written by Claude Code, not yet reviewed by the user.
- No test runner yet.

## Environments
- Local: frontend http://localhost:3000, API http://localhost:8000 (planned); DB not created yet
- Production: not deployed yet

## Releases
- None yet.
