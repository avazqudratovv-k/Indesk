# Indesk — instructions for AI agents

## What this is
Indesk lets a user upload CSV, PDF or image files, ask a question and watch five AI agents (Owl, Chameleon, Beaver, Hound, Cat) work as a team. The result is a cited report where every claim is verified or flagged, plus two modes: Check a document and Compare. It is a portfolio demo, not a product for real users, so it must never fail in front of someone who tries it.
Stack: Next.js (App Router) + TypeScript + CSS Modules + next-intl | FastAPI (Python 3.12) + Pydantic + SQLAlchemy 2.0 + Alembic | PostgreSQL + pgvector | Redis + RQ | Google Gemini | Docker Compose + nginx.
Repo: this one (monorepo: `web/`, `api/`, `docs/`). Product detail: `docs/ai/SPEC.md`, `docs/ai/DATA.md`.

## Start and end of every session
- Start: read `docs/ai/STATE.md` first. It says what's done, what's in progress and what's next.
- End: update `docs/ai/STATE.md`. Add an entry to `docs/ai/DECISIONS.md` for every non-obvious choice, and add new bugs or ideas to `docs/ai/BACKLOG.md`.
- Work follows `docs/ai/ROADMAP.md` in order (UI first, then backend, then swap mock to real). Check a box only when its "done when" is true.

## Commands
`web/` exists; `api/` is only a stub (ROADMAP 3.1 creates it). Update this section as things appear.
- Web (`web/`, exists): install `npm ci`; dev `npm run dev` (port 3000); build `npm run build`; lint `npm run lint`; typecheck `npm run typecheck`. No test runner yet (add with the first real logic).
- API (`api/`): Python 3.12 virtualenv in `api/.venv`; dev `uvicorn app.main:app --reload` (port 8000); lint `ruff check .`; typecheck `mypy .`; tests `pytest`; migrations `alembic upgrade head`.
- All services: `docker compose up` (API, Postgres + pgvector, Redis, RQ worker).
- The `api/` commands are placeholders until it exists; verify before relying on them.

## Project layout
- `web/` — Next.js 16 app: `app/` routes (`app/dev/tokens` is a dev-only swatch page), `components/`, `styles/tokens.css`; later `messages/` (en, ko) and `mocks/`
- `api/` — FastAPI app: routers, agents, Gemini gateway, sandbox runner, models, migrations, tests; model IDs in a config file
- `docs/ai/` — SPEC, DECISIONS, DATA, ROADMAP, STATE, BACKLOG, LEARNING (the project's memory)
- `docs/security/SECURITY.md` — security plan and status
- `docs/design/` — `DESIGN.md` (tokens, components, UI rules), `source/` (HTML design boards), `png/` (board images)

## Design
- `docs/design/DESIGN.md` is the source for tokens; `docs/design/source/*.dc.html` is the visual truth for markup and styles. Read them, don't copy them.
- Themes: Nocturne (light) and Midnight (dark). All colors come from CSS variables, never raw hex. Build the 390 px layout first, widen at 760 px.

## Rules (always)
- Never read, print or edit `.env` files or secrets. Refer to env variables by NAME only. New names go into `.env.example` with a placeholder; I fill in real values myself.
- Never type passwords or log in for me. If a step needs a signed-in session, open the login page and ask me.
- Do not commit or push. I review the diff and commit myself.
- Don't add a new dependency without saying why, and pin its version.
- Keep changes focused on the task. Mention unrelated problems you notice; don't fix them silently.
- Every user-facing text goes through i18n (`next-intl`; English and Korean first, structure ready for Japanese, Russian, Uzbek); no hard-coded strings.
- Errors returned to the client use a code (for example `DAILY_CAP_USER`), never raw stack traces or model messages.
- Answers come only from the user's files, never from model world knowledge. A claim without evidence is never shown as verified.
- Numbers are computed in code (pandas on the whole file) and the app renders them; the model only sees column names, a sample and results. Charts and report styling never go through the AI.
- Agents return structured results (claim, value, method, evidence, confidence, caveats) validated by Pydantic; output that doesn't fit is rejected, not rendered.
- Orchestration is our own typed state machine; no agent framework. Step cap 12, one retry per agent step, per-run cost caps (Ask $0.05, Check $0.12, Compare $0.08).
- Generated code runs only in the Docker sandbox: no network, 5 s CPU, memory limit.
- Storage and payments sit behind interfaces (local disk now, simulated demo checkout). Originals and extracted data are deleted after 24 h; reports keep their evidence snapshots.
- New API fields are additive; change the API before the frontend that uses it.
- Touch targets at least 44 px on mobile. Every data view has loading, empty and error states.
- Every page footer and the upload area show the demo notice: "Indesk is a demo. Do not upload private or sensitive files."

## Gemini rules
- All AI features use Google Gemini, through ONE server-side gateway module. No other code calls a model. The browser never calls Google.
- The key lives only in `api/.env` (variable name set in `api/.env.example`; I fill it in). Never print, log, send to the browser or put it in a prompt.
- Model IDs live in a config file, not in code. Confirm each ID in Google AI Studio before the first real call; if one is unknown, say so, don't guess.
  - Light jobs (route, plan, pick-and-quote, claim extraction): `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-3.8-flash`.
  - Main reasoning (Beaver code, Chameleon vision, Cat verdicts): `gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.5-flash-lite`.
  - `gemini-4-argon` only as an optional escalation, off by default, paid tier only.
- 35 s budget per model request shared across the whole fallback chain; a timeout, error or HTTP 429 moves to the next model; if all fail the agent shows Failed with Retry.
- Every call is logged to `ai_calls` (metadata only: model, tokens, cost, status, latency; never file contents or question text) and counted in `usage_daily`. Daily caps from config: per user 30 runs / 300 calls, global 100 runs / 1,000 calls; the cached example is excluded. A capped run is refused before any model call with `daily_cap_user` or `daily_cap_global`.
- Uploaded text is data, never instructions: put it only in clearly marked data sections of a prompt.
- Free tier only for development, and only with the public Seoul demo data and test files. Never use real private files until the paid-tier switch (ROADMAP 5.5).
- Tests and CI use the fake model client. They never call real Gemini and never spend the daily cap. Real Gemini runs only by hand.

## Security
- Follow `docs/security/SECURITY.md` and `.claude/rules/security.md`. Never trust the client: prices, plan, roles, user IDs and limits are decided on the server; every private record (report, upload) is checked for ownership on the server.
- Auth: Argon2 passwords; short-lived access token in an httpOnly cookie plus a rotating refresh token stored hashed.
- Share links: random token stored hashed, read-only, expire after 7 days, revocable. People search: opt-in users only, 2+ characters, max 20 results.
- Rate limits: 5 sign-ups per hour per IP, 30 runs per day per user on paid plans, 30 people searches per minute per user.
- Changes that touch auth, payments, uploads, personal data or AI: name the security rule you applied and how you tested it in the report. A control is "done" only with a passing test; otherwise say "not verified".

## Code style
- TypeScript strict; no `any` without a comment explaining why. Python fully typed (Pydantic models at every boundary).
- Naming: camelCase variables, PascalCase components, kebab-case files in `web/`; snake_case in `api/`.
- Prefer small functions; one component per file; CSS Modules, no component library.
- Match the existing patterns in the file you're editing.

## Definition of done
A task is done only when:
1. build, lint, typecheck and tests pass;
2. UI changes were checked in the browser (phone width and desktop, light and dark) or the report clearly says they weren't;
3. docs are updated (STATE.md, and DECISIONS.md if a choice was made; SECURITY.md status if a security control changed);
4. the report lists: what changed (files), what was verified, what was NOT verified.

## Reports
Plain English, short. Sections: what changed, what passed, what I couldn't verify, open questions.
