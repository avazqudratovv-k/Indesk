---
name: security-docs
description: Write or update docs/security/SECURITY.md for this project by interviewing me one question at a time.
disable-model-invocation: true
---

Help me write `docs/security/SECURITY.md` (the template is already in the repo).

1. First read AGENTS.md, docs/ai/SPEC.md and the code (package.json, auth, schemas, env NAMES in .env.example). Never read .env files.
2. Summarize the app in a short brief: what it does, who uses it, what data it stores, which services it uses. Label anything unknown. Ask me to confirm.
3. Then go through the 5 parts in order (rules, auth, data, threats, launch checklist). Ask ONE question at a time, explain unfamiliar terms simply, and if I'm unsure, recommend an option and say why. Never ask me for real passwords, keys or customer data.
4. For every rule and protection, write WHERE it's enforced (file or layer) and HOW to test it. Set Status honestly: Planned if not built, Built if code exists but no test, Tested only if a test passed.
5. Look in the code for each rule: if something already exists, point to it; if it's missing, say so and add it to docs/ai/BACKLOG.md under Bugs with priority.
6. Show me the finished file and the list of missing controls, ordered by real risk. Don't change application code.
