# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-25

## Status in one line
Design and docs finished. ROADMAP 1.1 to 1.3 done in code (repo folders, Next.js app with all routes, design tokens and swatch page). No real screens yet. Tier A deadline about 2026-11-01.

## Last session
- Recorded the answers to the OPEN items in DECISIONS (#34, #54, #62 to #65), SPEC, ROADMAP and DESIGN.
- 1.1: created `web/` and `api/` (stub, `.env.example` with names only); `.env` already ignored.
- 1.2: Next.js 16.4.3 app, one placeholder page per route, plus dev-only `/dev/tokens`.
- 1.3: `web/styles/tokens.css` (light, dark, `.dk`, report paper), fonts loaded from Google Fonts, `data-theme` on `<html>`, CSS Modules.
- Passed: lint, typecheck, build. Swatch page checked in headless Chrome at 390 and 1280 px.

## In progress
- Nothing. Stopped after 1.3 as agreed.

## Next
1. ROADMAP 1.4 base components, 1.5 layout shell (with the mobile tab bar from DECISIONS #62), 1.6 translations, 1.7 mock data.
2. ROADMAP section 2: each screen on mock data.
3. ROADMAP section 3: backend (confirm Gemini model IDs in AI Studio first; choose the embedding model at 3.12).

## Known issues
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The theme toggle on `/dev/tokens` (whole page light/dark) was not clicked in a browser; the dark palette itself was checked via its scoped panels.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- No test runner yet.

## Environments
- Local: frontend http://localhost:3000, API http://localhost:8000 (planned); swatch page http://localhost:3000/dev/tokens, DB not created yet
- Production: not deployed yet

## Releases
- None yet.
