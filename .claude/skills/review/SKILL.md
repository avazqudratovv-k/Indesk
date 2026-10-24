---
name: review
description: Review the uncommitted changes before I commit, and suggest a commit message.
disable-model-invocation: true
---

Review my uncommitted changes before I commit.

1. Run `git status` and `git diff` (and `git diff --staged`).
2. Check for: bugs, missing error handling, security problems (secrets, missing auth checks, unsafe input), leftover debug code, files that shouldn't be committed (`.env`, build output, large binaries), missing translations or tests, changes unrelated to the task.
3. Answer in this format:
   - Must fix before commit (with file:line);
   - Should fix soon;
   - Looks good;
   - Suggested commit message (one line, imperative, under 72 characters).
4. Don't change files unless I ask.
