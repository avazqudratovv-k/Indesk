@AGENTS.md

<!--
Claude Code reads ONLY CLAUDE.md when both CLAUDE.md and AGENTS.md exist.
The import on line 1 pulls AGENTS.md in, so the real instructions live in one place
and other AI tools (Cursor, Codex, ...) can read AGENTS.md too.
Put only Claude Code-specific notes below.
-->

## Claude Code notes
- Skills in `.claude/skills/`: `/start-session`, `/end-session`, `/new-feature`, `/fix-bug`, `/review`, `/explain`, `/deploy`, `/security-docs`, `/security-review`.
- Area rules in `.claude/rules/` load automatically when you open matching files.
- For anything bigger than a small fix, propose a plan first and wait for my OK.
- If a fix didn't work twice, stop guessing: reproduce the bug and measure before changing code again.
