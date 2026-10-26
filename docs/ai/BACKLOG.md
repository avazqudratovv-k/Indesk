# Backlog

<!-- Bugs, small ideas and "later" items, so nothing gets lost in a chat.
     Move an item into ROADMAP.md when you decide to do it. -->

## Bugs
- [ ] <what, where, steps to reproduce> — priority: <high/medium/low>

## Small improvements
- [ ] Claims are checked for naming the right row, not the right column — priority: medium (found in 4.4 and P9 follow-up)
- [ ] Korean header words: translate English column headers inside Korean reports (they stay English today, #242) — priority: low

## Ideas
- [x] ~~Add an additive `lang` field to the report~~ Done in P10b (#254); the web still has to use it (ROADMAP 5.1)
- [ ] `TOO_MANY_STREAMS` (429) handling in the web: EventSource cannot read an error body (#260) — priority: not set
- [ ] Retry endpoint for a failed agent (`POST /runs/{id}/steps/{step}/retry`, DATA.md) — priority: not set (#260)
- [ ] `ai_calls.est_cost_usd`: still 0; wire it only if internal monitoring needs it (#217, #260) — priority: not set
- [ ] Korean example report for `GET /api/example` (only English exists, #253) — priority: not set
