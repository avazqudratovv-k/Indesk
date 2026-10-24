---
paths:
  - "api/**/models/**"
  - "api/**/migrations/**"
  - "api/**/alembic/**"
---

# Database rules (SQLAlchemy + Alembic, PostgreSQL + pgvector)

- Schema changes are additive by default (new nullable columns). Removing or renaming needs a migration plan written in DECISIONS.md first.
- Every schema change is an Alembic migration; never edit the database by hand.
- Add indexes for every field used to filter or sort lists (for example `user_id`, `expires_at`, `(day, user_id)` on `usage_daily`).
- Queries use the ORM or bound parameters, never user input joined into a SQL string.
- Entities and fields follow `docs/ai/DATA.md`; if the code needs a change, update DATA.md in the same session.
- The API database user has minimum rights (no DROP); the sandbox has no database access.
- Scripts that change data refuse to run without an explicit confirm variable naming the target database.
- Never run destructive commands (drop, delete many, reset) against production. Ask me.
