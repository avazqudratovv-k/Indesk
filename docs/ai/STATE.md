# Project state

<!-- The handoff file. Any new chat reads this first, so keep it short and current.
     /end-session updates it. Overwrite old content; history lives in git and DECISIONS.md. -->

Updated: 2026-10-25

## Status in one line
Design and docs are finished; no app code yet. Roadmap 0 of 7 items in section 1 done. Deadline for Tier A: about 2026-11-01.

## Last session
- Checked `docs/design/DESIGN.md` against `docs/design/source/`: colors all matched; fixed missing tokens, report paper details, radius table, spacing, mobile padding (20, not 16), the 700 px report breakpoint, the mobile bottom tab bar, and screen file names.
- Filled in `AGENTS.md` (stack, commands, layout, Gemini rules) and adapted `.claude/rules/` to `web/` and `api/`.

## In progress
- ROADMAP 1.1 (repo and docs) — next exact step: create `web/` and `api/` folders, `.env.example` files with placeholder names only, and confirm `.env` is ignored. Waiting for the user's OK on the plan.

## Next
1. ROADMAP 1.1 to 1.7: skeleton, tokens, base components, layout shell, translations, mock data.
2. ROADMAP section 2: each screen on mock data.
3. ROADMAP section 3: backend (Gemini gateway 3.8 needs model IDs confirmed in Google AI Studio first).

## Known issues
- None in code. Open questions: Gemini embedding model ID and vector size (DECISIONS #34); VPS company and free subdomain (#54); date for the move to the paid Gemini tier (SPEC); signed-in items of the mobile tab bar (DESIGN.md).
- The design source files include `support.js` by reference but it is not in the repo; the boards don't render on their own (read them as markup).

## Environments
- Local: frontend http://localhost:3000, API http://localhost:8000 (planned), DB not created yet
- Production: not deployed yet

## Releases
- None yet.
