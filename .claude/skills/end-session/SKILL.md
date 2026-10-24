---
name: end-session
description: Close a work session by updating the project's memory files so the next chat knows what happened.
disable-model-invocation: true
---

Close this work session. Only edit files under `docs/ai/`.

1. Update `docs/ai/STATE.md`:
   - "Last session" — date and 3–6 bullet points of what was done;
   - "In progress" — anything unfinished, with the exact next step;
   - "Next" — the next 1–3 tasks;
   - "Known issues" — anything broken right now.
2. For every non-obvious choice made in this session, add an entry to `docs/ai/DECISIONS.md` (number, date, decision, why, alternatives rejected).
3. Add bugs, ideas and "later" items you noticed to `docs/ai/BACKLOG.md`.
4. Tick finished items in `docs/ai/ROADMAP.md`.
5. Show me a short summary of what you changed in these files. Don't commit.
