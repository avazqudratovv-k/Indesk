---
name: deploy
description: Pre-deploy checklist and exact server commands for this project. Fill in the commands once; reuse every release.
disable-model-invocation: true
---

Prepare a deploy. Don't run anything on the server yourself; give me the commands.

1. Pre-checks on this machine: build, lint, typecheck and tests pass; `git status` is clean; the branch is pushed.
2. Check what changed since the last release (`git log --oneline <last tag or commit>..HEAD`). Flag anything risky: schema changes, new env variable names, new API fields (backend must deploy before frontend), data scripts.
3. If there are new env variable NAMES, list them, so I add them to the server's env file myself.
4. Give me the server commands in order:
   <!-- FILL IN ONCE FOR THIS PROJECT, for example: -->
   <!-- ssh root@<server-ip> -->
   <!-- cd ~/<backend> && git pull origin main && docker compose up -d --force-recreate -->
   <!-- curl -s http://127.0.0.1:<port>/ready -->
   <!-- cd ~/<frontend> && git pull origin master && docker compose up -d --force-recreate -->
5. Give me a 5-step check to run on the live site afterwards.
6. Add a line to `docs/ai/STATE.md` under "Releases": date, commit, what shipped.
