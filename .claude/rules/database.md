---
paths:
  - "**/schemas/**"
  - "**/models/**"
  - "**/migrations/**"
  - "prisma/**"
---

# Database rules (example — adapt the paths and rules)

- Schema changes are additive by default (new optional fields). Removing or renaming needs a migration plan written in DECISIONS.md first.
- Add indexes for every field used to filter or sort lists.
- Scripts that change data refuse to run without an explicit confirm variable naming the target database.
- Never run destructive commands (drop, delete many, reset) against production. Ask me.
