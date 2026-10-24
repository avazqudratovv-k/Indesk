---
paths:
  - "api/**/*.py"
---

# Backend API rules (FastAPI)

- Validate every input with Pydantic models (type, length, range, allowed values).
- Every route checks auth first, then ownership of the record (report, upload, run). Hiding a button is not protection.
- Return errors as codes the frontend can translate (for example `DAILY_CAP_USER`); no raw messages or stack traces.
- Never log secrets, tokens, file contents, question text or full request bodies.
- Every model call goes through the Gemini gateway; never call Gemini from a route or an agent directly. Model IDs come from the config file.
- Agent output is validated against its Pydantic result shape before it is stored or rendered.
- New fields are additive; never rename or remove a field the frontend uses in the same change.
- Tests use the fake model client and never call real Gemini. Add or update a test for every rule you add.
