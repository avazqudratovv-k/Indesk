# api

FastAPI backend. Python 3.12 runs only inside Docker; nothing to install on your machine.

Secrets go in `api/.env` (ignored by git; compose reads it if present). See `.env.example` for the variable names.

Run these from the repo root:

- Start everything: `docker compose up -d --build` (API on http://127.0.0.1:8000; db and redis are not published)
- Check: `curl localhost:8000/api/health` and `curl localhost:8000/api/ready`
- Test: `docker compose run --rm --build api pytest`
- Lint and types: `docker compose run --rm --build api ruff check .` and `docker compose run --rm --build api mypy .`
- Logs: `docker compose logs -f api worker`
- Stop (keeps the database volume): `docker compose down`

The code is baked into the image (no bind mount), so use `--build` after editing.
Dev database password: compose uses a dev-only default; override with the `POSTGRES_PASSWORD` shell variable if you want.
