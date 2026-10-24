# <Project name> — instructions for AI agents

<!--
TEMPLATE. Replace everything in <angle brackets>. Delete sections you don't need.
Keep this file under ~200 lines: only things that are true in EVERY session.
Long procedures go into .claude/skills/, area-specific rules into .claude/rules/.
-->

## What this is
<One or two sentences: what the app does and for whom.>
Stack: <e.g. Next.js 14 (pages router) + MUI | NestJS + GraphQL | MongoDB Atlas>.
Repos: <this repo> (<role>), <other repo if any> (<role>).

## Start and end of every session
- Start: read `docs/ai/STATE.md` first. It says what's done, what's in progress and what's next.
- End: update `docs/ai/STATE.md`. Add an entry to `docs/ai/DECISIONS.md` for every non-obvious choice, and add new bugs or ideas to `docs/ai/BACKLOG.md`.

## Commands
- Install: `<npm ci | yarn install>`
- Dev: `<npm run dev>` (port <3000>)
- Build: `<npm run build>`
- Lint / typecheck: `<npm run lint>` / `<npm run typecheck>`
- Tests: `<npm test>`; end-to-end: `<npm run e2e>`
- <Seed / migrations: `...`>

## Project layout
- `<src/pages>` — <routes>
- `<src/components>` — <shared UI>
- `<src/lib>` — <helpers, API clients>
- `<apps/api/src>` — <backend modules>
- `docs/ai/` — state, decisions, roadmap, backlog (the project's memory)

## Rules (always)
- Never read, print or edit `.env` files or secrets. Refer to env variables by NAME only. New names go into `.env.example` with a placeholder; I fill in real values myself.
- Never type passwords or log in for me. If a step needs a signed-in session, open the login page and ask me.
- Do not commit or push. I review the diff and commit myself.
- Don't add a new dependency without saying why, and pin its version.
- Keep changes focused on the task. Mention unrelated problems you notice; don't fix them silently.
- Every user-facing text goes through i18n (<languages>); no hard-coded strings.
- Errors returned to the client use a code (for example `EVENT_ENDED`), never raw stack traces.
- <Project-specific rule learned the hard way, e.g. "every model injected in the batch app must be registered in BatchModule">
- <e.g. "new API fields are additive; deploy the backend before the frontend">

## Security
- Follow `docs/security/SECURITY.md` and `.claude/rules/security.md`. Never trust the client: prices, roles, user IDs and limits are decided on the server; every private record is checked for ownership on the server.
- Changes that touch auth, payments, uploads, personal data or AI: name the security rule you applied and how you tested it in the report.

## Code style
- <TypeScript strict; no `any` without a comment explaining why>
- <Naming: camelCase variables, PascalCase components, kebab-case files>
- <Prefer small functions; one component per file>
- Match the existing patterns in the file you're editing.

## Definition of done
A task is done only when:
1. build, lint, typecheck and tests pass;
2. UI changes were checked in the browser (phone width and desktop) or the report clearly says they weren't;
3. docs are updated (STATE.md, and DECISIONS.md if a choice was made; SECURITY.md status if a security control changed);
4. the report lists: what changed (files), what was verified, what was NOT verified.

## Reports
Plain English, short. Sections: what changed, what passed, what I couldn't verify, open questions.
