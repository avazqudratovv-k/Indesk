---
name: start-session
description: Start a work session by reading the project's memory files and summarizing where things stand. Use at the start of a new chat.
disable-model-invocation: true
---

Start a work session.

1. Read `docs/ai/STATE.md`, the top of `docs/ai/ROADMAP.md`, and `docs/ai/BACKLOG.md`.
2. Run `git status` and `git log --oneline -5`.
3. Tell me, in at most 10 lines:
   - what was done last time;
   - what is in progress or uncommitted;
   - the next 1–3 steps you suggest, and why;
   - anything that looks inconsistent (for example STATE.md says done, but there are uncommitted changes).
4. Wait for me to choose. Don't change any files.
