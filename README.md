# Indesk

Upload a CSV or a PDF, ask a question, and get an answer made of checked claims with the evidence next to them. Indesk is a portfolio demo, not a product for real users. **Indesk is a demo. Do not upload private or sensitive files.**

## Live demo
- Site: https://indesk.76-13-198-17.sslip.io
- Sample report: `/reports/example` (the cached example, built from the public Seoul subway data; it costs no AI calls).
- Live demo: https://indesk.76-13-198-17.sslip.io (deployed 2026-10-31; moving to indesk.uz).

## Stack
- `web/`: Next.js (App Router), TypeScript, CSS Modules, next-intl (English and Korean)
- `api/`: FastAPI, Pydantic, SQLAlchemy 2.0, Alembic (Python 3.12, runs only in Docker)
- PostgreSQL with pgvector, Redis with RQ (worker and scheduler)
- Sandbox service (runs generated pandas code) and parser service (reads PDFs), both isolated containers
- Google Gemini, only through one server-side gateway
- Docker Compose, nginx

## AI in this project
- **One gateway, fallback chains.** All model calls go through one server-side module. Model IDs live in `api/config/models.toml`: a light chain and a main chain with 3 entries each. A timeout, error or HTTP 429 moves to the next model, within a 35 s budget per request.
- **Four agents, run by our own typed state machine** (no agent framework; step cap 12, one retry per agent step):
  - **Owl** plans the run.
  - **Beaver** answers CSV questions: the model writes pandas code, the code runs in the sandbox, the numbers come from the whole file.
  - **Hound** answers PDF questions: hybrid retrieval (vector search on pgvector plus keyword search) over the PDF's chunks.
  - **Cat** verifies in plain code, not with a model: it re-checks numbers and quotes against the evidence.
- **Structured output.** Plans and results are validated with Pydantic; output that does not fit is rejected, not rendered.
- **Sandboxed code.** Generated code runs only in a Docker sandbox: no network, 5 s CPU, a memory limit.
- **Prompt-injection fencing.** File text is data, never instructions: it goes only inside marked sections of a prompt, and model output is treated as untrusted and scrubbed before it is stored.
- **Cost and token caps.** Per run: 60,000 model tokens, and 250,000 embedding tokens for a PDF. Per day: 10 runs and 50 calls per user, 150 runs and 600 calls for the whole site (`api/config/limits.toml`).
- **Tests never call Gemini.** Tests and CI use a fake model client.

## Honest limits
- A question about data the file does not have can still be answered using other columns. The first sentence of the answer says so.
- Vision agent (Chameleon): roadmap, not built yet.
- Check a document and Compare are not built; they say "Not available yet".
- A free account gets 3 runs in total, not per month.
- Cat marks a claim it cannot verify as unverified instead of claiming proof. A claim is shown as verified only when the code checked it against the file.
- No self-service account deletion yet.

## Run locally
Python runs only in Docker. Secrets go in `api/.env` (ignored by git; names are in `api/.env.example`).
```
docker compose up -d --build
```
The API is on http://127.0.0.1:8000. Check it:
```
curl localhost:8000/api/health
curl localhost:8000/api/ready
```
The web app (`web/`, port 3000):
```
cd web
npm ci
npm run dev
```
Logs: `docker compose logs -f api worker`. Stop (keeps the database): `docker compose down`.

## Tests
Counts are from the last run recorded in `docs/ai/STATE.md` (owner-reported); they are "as of the last run", not re-measured for this README.
- API, 1450 passed (43 `sandbox` and `parser` tests are deselected by default). Full check:
  ```
  docker compose run --rm --build api sh -c "ruff check . && ruff format --check . && mypy . && pytest -q"
  ```
- Web, 513 tests: `npm test` in `web/` (also `npm run lint`, `npm run typecheck`, `npm run build`).
- Sandbox, 21 tests. These need the sandbox service in test mode (see `api/README.md`):
  ```
  docker compose -f compose.yaml -f compose.sandbox-test.yaml up -d --build sandbox
  docker compose -f compose.yaml -f compose.sandbox-test.yaml run --rm --build worker pytest -m sandbox
  ```
- Parser tests: `docker compose up -d --build parser`, then `docker compose run --rm --build api pytest -m parser`.

## Docs map
- `docs/ai/SPEC.md`: what the product does.
- `docs/ai/DATA.md`: the data model.
- `docs/ai/ROADMAP.md`: the build order and what is done.
- `docs/ai/STATE.md`: where the project is now; read this first.
- `docs/ai/DECISIONS.md`: every non-obvious choice and why.
- `docs/ai/BACKLOG.md`: bugs and ideas not done yet.
- `docs/ai/LEARNING.md`: notes on what was learned along the way.
- `docs/design/DESIGN.md`: design tokens, components and UI rules.
- `docs/security/SECURITY.md`: the security plan and the status of each control.
- `deploy/RUNBOOK.md`: how to deploy, update, back up, roll back and rotate the Gemini key.
