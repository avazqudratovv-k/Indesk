---
name: new-feature
description: Plan, build and verify a new feature end to end, following the project's definition of done.
argument-hint: [short feature description]
disable-model-invocation: true
---

New feature: $ARGUMENTS

Step 1 — Plan (don't write code yet)
- Read AGENTS.md, docs/ai/STATE.md and the code areas this touches.
- Write a plan: what the user sees, which files change, data/API changes, risks, how you'll verify it.
- Ask me up to 3 questions if something is unclear. Wait for my OK.

Step 2 — Build
- Implement in small steps. Follow the existing patterns and the rules in .claude/rules/.
- Add or update tests for the new behavior.

Step 3 — Verify
- Run build, lint, typecheck and tests. Fix failures.
- If it's UI: check it in the browser at 360 px, 390 px and desktop, light and dark. If you can't, say so.
- If it needs a signed-in user: open the login page and ask me to sign in. Never type passwords.

Step 4 — Report
- What changed (files), what passed, what you could NOT verify, open questions.
- Add a DECISIONS.md entry if a choice was made. Don't commit.
