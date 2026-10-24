---
name: fix-bug
description: Fix a bug by reproducing it first, finding the real cause, fixing it, and proving the fix.
argument-hint: [what goes wrong, where, and what should happen]
disable-model-invocation: true
---

Bug: $ARGUMENTS

1. Reproduce: make the bug happen yourself before changing anything (a test, a script, Playwright, curl, logs). Write down the exact steps and what you observed.
2. Find the cause: explain in plain words WHY it happens, with the file and line. If you can't reproduce it, say so and ask me for details (a screenshot, a recording, the steps); don't guess.
3. Fix the cause, not the symptom. Keep the change small.
4. Prove it: repeat step 1 and show that it's gone. Add a test that would have caught it, if possible.
5. Check nearby: does the same mistake exist elsewhere? List it, don't fix it without asking.
6. Report: cause, fix (files), before/after evidence, what you couldn't verify. Add a DECISIONS.md entry if the fix sets a rule. Don't commit.
