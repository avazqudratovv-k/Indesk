# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-25

## Status in one line
ROADMAP 1.1 to 1.7 done in code (skeleton, tokens, base components, next-intl en/ko, layout shell, mock data). No real screens yet. Tier A deadline about 2026-11-01.

## Last session
- 1.4: base components (button, icon button, eyebrow, card, chip, demo notice) with a components page.
- 1.5: layout shell: navbar, footer with demo notice and tagline, mobile bottom tab bar.
- 1.6: next-intl with en and ko message files; locale from the `NEXT_LOCALE` cookie.
- 1.7: `web/mocks/*.json` from the DATA.md examples, plus the dev signed-in/signed-out switch.

## In progress
- Nothing.

## Next
1. ROADMAP section 2, starting with 2.1 Home.
2. ROADMAP section 3: backend (confirm Gemini model IDs in AI Studio first; choose the embedding model at 3.12).

## Known issues
- Pinned TypeScript 6.0.3, not 7.0.2: typescript-eslint does not support TS 7 yet. Revisit when it does.
- `next dev` writes `web/AGENTS.md` (Next.js agent rules) on its own; kept for now, can be disabled with `agentRules: false` in next.config.
- The theme toggle on `/dev/tokens` (whole page light/dark) was not clicked in a browser; the dark palette itself was checked via its scoped panels.
- The design source references `support.js`, which is not in the repo; boards don't render alone.
- Korean UI text written by Claude Code, not yet reviewed by the user.
- No test runner yet.

## Environments
- Local: frontend http://localhost:3000, API http://localhost:8000 (planned); swatch page http://localhost:3000/dev/tokens, DB not created yet
- Production: not deployed yet

## Releases
- None yet.
