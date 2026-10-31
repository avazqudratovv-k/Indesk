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
- [x] ~~Report purge job~~ Done: `purge_expired` runs daily in the scheduler (#297)
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
- [x] ~~A "My reports" list and an account page~~ My page is built (#302); Delete account is not built (after the deploy, #308)

## Added in docs batch 15 (2026-10-30, priorities not set)
- [ ] `deploy/RUNBOOK.md` "Update" has no step for the pgvector extension on the existing database volume; migration 0005 needs it (#287)
- [x] ~~PDF in the web~~ Done in 4.5A to 4.5C (#300)
- [x] ~~P14b live check~~ Done (#288, #289): the ID works, the 0.5 floor is kept, not tuned. The embedding price is still unverified (see below)
- [ ] `web/lib/workspace/validate.ts` and `web/mocks/plans.json` may still hold their own copies of the file and row limits; the main source is now `web/lib/limits.ts` with a drift test (#301). Not re-checked
- [x] ~~DATA.md says 5,000 rows~~ Fixed in docs batch 16 (the limit is 20,000, #278)

## Added in docs batch 16 (2026-10-31, priorities not set)
Open items:
- [ ] Substitution gap: a question about data the file lacks can be answered with other columns, disclosed in the first sentence. Idea: a closed `metric_match` field in Owl's plan, in shadow mode first. Decided NOT before the deploy (#319). The README must say it plainly
- [ ] The similarity floor cannot separate unanswerable questions (answerable 0.71 to 0.80, unanswerable 0.62 and 0.72); only two unanswerable samples exist. Keep 0.5, the writer's `found=false` is the guard (#289). Collect more unanswerable samples before revisiting
- [ ] Not answerable run D was tested only through the API plus the web walk-through
- [ ] Embedding price: $0.20 per million tokens came from a reseller page and is unverified; confirm on Google's price page
- [ ] The writer's cost shows 0.000 in `ai_calls` (no price table)
- [ ] `real_client.py` still uses the old token estimate when Google returns no count (#291)
- [ ] Home team plates use an IntersectionObserver mask (blank in full-page screenshots only)
- [ ] A non-Ask report page returns 200 in dev (a soft 404); handle it on purpose when Check ships
- [ ] `reports.pdf_key` and `reports.deleted_at` are written by nothing; if exports ever write `pdf_key`, delete the object too (the purge already tries, best effort, #297)
- [ ] Account delete, after the deploy (#308, #320)
- [ ] Rate limits exist only on the routes added recently (#296); `GET /reports/{id}`, `/runs/*`, `/usage` and `/me` are still unlimited
- [ ] Native Korean review is still open (UI labels, report prose, the not answerable card, the notices)
- [ ] Check a document, Compare and Vision (Chameleon): after the deploy, in that order (#320)
- [ ] Restore the removed Check and Compare copy from git history when those modes ship (#303)
- [ ] Deploy checklist items are in STATE (#321); `deploy/RUNBOOK.md` "Update" still has no pgvector step

