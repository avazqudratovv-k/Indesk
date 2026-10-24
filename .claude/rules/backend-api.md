---
paths:
  - "apps/**/src/**/*.ts"
  - "src/server/**/*.ts"
---

# Backend API rules (example — adapt the paths and rules)

- Validate every input (DTOs with class-validator, or zod).
- Every endpoint/resolver checks auth and role first.
- Return errors as codes the frontend can translate; no raw messages.
- Never log secrets, tokens or full request bodies.
- New fields are additive; never rename or remove a field the frontend uses in the same change.
- Add or update a test for every rule you add.
