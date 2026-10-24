---
name: explain
description: Teach me a file, function or flow of this project line by line, at beginner level, using the real code.
argument-hint: [file path, function name, or flow like "login"]
disable-model-invocation: true
---

Teach me: $ARGUMENTS

- Find the real code for it in this repo. Don't change any files.
- Start with 2–3 sentences: what it is and where it fits in the app.
- If it's a flow, first show the steps as a simple numbered path (browser → server → database → back), with the file for each step.
- Then go through the code in small blocks: show the block, then explain each line in plain English: what it does, why it's there, what would break without it.
- Explain every new term the first time it appears.
- End with: one sentence I could say about it in an interview, and 3 short questions to check that I understood. Wait for my answers.
- Add a 3-line note to `docs/ai/LEARNING.md` about what we covered.
