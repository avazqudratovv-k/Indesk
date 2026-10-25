# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-25

## Status in one line
ROADMAP 1.1 to 1.7 and screens 2.1 to 2.6 (Home, Log in, Sign up, Plans, Workspace Ask tab, Workspace run tab) are done and committed, all on mock data. HEAD e771b11. Next is 2.7 Report (Ask). Tier A deadline about 2026-11-01.

## What exists (`web/`)
- Screens: Home (`app/page.tsx`), `/login`, `/signup`, `/plans`. Other routes are `RoutePlaceholder` pages. Dev pages: `/dev/tokens`, `/dev/components`, `/dev/mock`.
- Components: `ui/` (Button, Card, Chip, DemoNotice, Eyebrow), `layout/` (Shell, Navbar, Footer, TabBar, PageBackground, LanguageMenu, ThemeToggle, BrandMark, SessionProvider, DevSessionSwitch), `home/`, `auth/` (AuthForm, AuthPage, AuthSide, `validate.ts`), `plans/` (PlansView, PlanCard, CustomCalculator, Checkout, UsagePanel, EnforceCard).
- Mocks: `web/mocks/*.json` (users, uploads, runs, run-files, reports, claims, evidence, share-links, plans) with `index.ts`; types in `lib/types.ts`.
- Helpers: `lib/plans/` (`calc.ts`, `card.ts`, `format.ts`), `lib/session.ts` and `session-server.ts` (mock `dev_session` cookie), `lib/theme.ts`, `hooks/` (`use-session`, `use-theme`), `i18n/` (en and ko, locale from the `NEXT_LOCALE` cookie), `messages/en.json` and `ko.json`.
- Shell behaviour and screen deviations from the boards: DECISIONS #69 to #77 (shell, auth, plans) and #79 to #84 (workspace Ask and run tabs).

## In progress
- Nothing.

## Next
1. ROADMAP 2.7 Report (Ask).
2. ROADMAP 2.16 holds the open polish and accessibility items collected so far.
3. ROADMAP section 3: backend (confirm Gemini model IDs in AI Studio first; choose the embedding model at 3.12).

## Later (collected during 2.5 and 2.6)
- When runs become real, derive "Agents woken" from events (it is hard-coded "3 of 4" from the board, #83).
- 2.5b: synthetic sample files for the Ask tab.
- Favicon (ROADMAP 2.16) and agent icons at 128 px.
- Check the "Chameleon" word width in Safari and Firefox.
- Production check that `?mockOutcome` is ignored (#82).
- Contrast of the error pill, the disabled Run button and the counter.
- Before the backend: decide which agent steps truly use an LLM (Owl is rule-based in v1, #61), so README claims stay accurate.
- After section 4: compare 5 questions against a plain chatbot for the README.

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
