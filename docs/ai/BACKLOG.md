# Backlog

<!-- Bugs, small ideas and "later" items, so nothing gets lost in a chat.
     Move an item into ROADMAP.md when you decide to do it. -->

## Bugs
- [ ] <what, where, steps to reproduce> — priority: <high/medium/low>

## Small improvements
- [ ] Claims are checked for naming the right row, not the right column — priority: medium (found in 4.4 and P9 follow-up)
- [ ] Korean header words: translate English column headers inside Korean reports (they stay English today, #242) — priority: low

## Ideas
- [x] ~~Add an additive `lang` field to the report~~ Done in P10b (#254); the web uses it since P11 (#262)
- [x] ~~`TOO_MANY_STREAMS` (429) handling in the web~~ Done in P11 B2 with a probe request (#264)
- [ ] Retry endpoint for a failed agent (`POST /runs/{id}/steps/{step}/retry`, DATA.md) — priority: not set (#260)
- [ ] `ai_calls.est_cost_usd`: still 0; wire it only if internal monitoring needs it (#217, #260) — priority: not set
- [ ] Korean example report for `GET /api/example` (only English exists, #253) — priority: not set

## After the first deploy (added 2026-10-27, priorities not set)
- [ ] Off-box backup copy (backups stay on the same machine today, #270)
- [ ] Report purge job: `expires_at` only hides a report, the row and its evidence stay
- [ ] Remove `retention_days` from the offer types (the web no longer shows it, #263)
- [ ] The sign-up limit (5 per hour per IP) blocks repeated browser checks: add a test-user fixture
- [ ] File picker and copy for Check and Compare, before those modes ship
- [ ] Delete the mock-only strings and the mock report code
- [ ] Cat lane: the third claim is clipped at 390 px on the Home film
- [ ] Fonts are loaded from Google at runtime (privacy and speed)
- [ ] Repeat the `X-Forwarded-For` check after Next upgrades
- [ ] Run a maximum-size CSV against the 1 GB sandbox
- [ ] Optional nginx rate limit in front of the app
- [ ] Email verification (ROADMAP 5.8)
- [ ] README note: "weekday" includes public holidays in the September data
- [ ] Title casing at the source (Owl) instead of the display-only CSS capital (#264)
- [ ] A "My reports" list and an account page (Tier B)

## Added in docs batch 15 (2026-10-30, priorities not set)
- [ ] `deploy/RUNBOOK.md` "Update" has no step for the pgvector extension on the existing database volume; migration 0005 needs it (#287)
- [ ] PDF in the web: accept `.pdf` in Ask, PDF error messages (en, ko), Hound and quote display (STATE "PDF in the web")
- [ ] P14b: confirm the embedding model ID live, tune the 0.5 similarity floor, chunk sizes and the embedding price (#279, #280)
- [ ] `web/lib/workspace/validate.ts` and `web/mocks/plans.json` still hold their own copies of the file and row limits
- [ ] DATA.md still says 5,000 rows for CSV uploads (the limit is 20,000, #278)
