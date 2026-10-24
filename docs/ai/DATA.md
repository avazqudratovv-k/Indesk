# DATA.md — Indesk

Lives at: `docs/ai/DATA.md`. Last updated 2026-10-25.

Database: PostgreSQL + pgvector. Entities, relationships, API operations and one mock record each.
Field types and limits: the `(rec)` limits are accepted (decided Oct 25). All AI calls go to Google Gemini; model IDs live in a config file (see `DECISIONS.md`).
Names: the agent keys in the database are `manager | vision | data | retrieval | critic`. In the UI they are Owl, Chameleon, Beaver, Hound, Cat. In the UI "waiting" = `queued`, "working" = `running`; "Skipped" is shown for `skipped`.

## 1. Entities
Legend: R = required. Types: uuid, text, int, bool, ts (timestamp), jsonb, vector.

### users
| Field | Type | R | Limits / notes |
|---|---|---|---|
| id | uuid | yes | |
| email | text | yes | unique, lowercase, max 254 (rec) |
| password_hash | text | yes | Argon2 |
| display_name | text | yes | 1 to 60 (rec) |
| handle | text | yes | unique, lowercase, 3 to 30 (rec) |
| discoverable | bool | yes | default false (opt-in for People search) |
| plan | text | yes | free, pro, payg, custom |
| lang | text | yes | en, ko, ja, ru, uz |
| theme | text | yes | light, dark |
| default_view | text | yes | simple, detailed |
| notify | bool | yes | default true (rec) |
| created_at | ts | yes | |
| deleted_at | ts | no | |

### refresh_tokens
id uuid R; user_id uuid R; family_id uuid R (all tokens from one login; if an old token is reused, the whole family is revoked); token_hash text R (never store the token); replaced_by uuid (the next token after rotation); expires_at ts R; revoked_at ts. The access token is short-lived and travels in an httpOnly cookie, not in this table.

### subscriptions
id; user_id; plan (free, pro, custom) R; status R; custom_config jsonb (runs 10 to 1000, max_file_mb 25/100/250, data_tier, retention_days 90/180/365, parallel 1/3/5); provider_customer_id text (simulated in v1); current_period_end ts.

### payments
id; user_id; provider_ref text; amount int (cents); currency text; status text; test_mode bool R (always true in v1).

### usage_events
id; user_id R; run_id; kind R (run, credit_purchase); amount int R (a run records 1); created_at R. Plan quota is computed from this table. Retention 90 days.

### uploads
| Field | Type | R | Limits / notes |
|---|---|---|---|
| id | uuid | yes | |
| user_id | uuid | yes | |
| filename | text | yes | max 255 (rec) |
| mime | text | yes | CSV, PDF, JPG, PNG, TXT |
| size | int | yes | Free 2 MB; Pro 25 MB; Custom 25/100/250 MB |
| sha256 | text | yes | |
| storage_key | text | no | removed at deletion |
| page_count | int | no | PDF: Free 10, Pro 200 |
| row_count | int | no | CSV: Free 5,000, Pro 200,000, Custom 200,000 or 1,000,000 |
| status | text | yes | uploaded, ready, deleted |
| moderation | text | yes | pending, passed, blocked |
| created_at | ts | yes | |
| expires_at | ts | yes | created_at + 24 h |
| deleted_at | ts | no | row stays (name, type, size) after deletion |

Pasted text is stored as a .txt upload, max about 200 KB.

### chunks
id; upload_id R; page int; text R; tsv tsvector; embedding vector(N); ocr_confidence float 0 to 1. Deleted with the upload. N is the vector size of the chosen Gemini embedding model (`OPEN:` see the end of this file).

### runs
| Field | Type | R | Limits / notes |
|---|---|---|---|
| id | uuid | yes | |
| user_id | uuid | yes | |
| question | text | yes | max 1,000 characters (rec) |
| mode | text | yes | ask, check, compare |
| question_type | text | no | new, explain, reformat |
| status | text | yes | queued, running, finished |
| outcome | text | no | answered, partial, not_answerable, needs_better_input, rejected, failed |
| outcome_reason | text | no | plain-language reason |
| counted | bool | yes | false for not_answerable (at the gate), needs_better_input, rejected, failed |
| lang | text | yes | |
| tokens_in, tokens_out, tool_calls | int | yes | step cap 12 tool calls |
| cost_usd | numeric | yes | estimated at Gemini paid prices even on the free tier; caps: Ask 0.05, Check 0.12, Compare 0.08 |
| started_at, finished_at | ts | no | |
| error | text | no | |

### run_files
run_id; upload_id; role (subject, source, a, b).

### agent_steps
id; run_id R; agent R (manager, vision, data, retrieval, critic); seq int R; status R (queued, running, done, skipped, failed, timed_out); attempt int (1 or 2); kind R (plan, tool, result, flag); payload jsonb (structured result: claim, value, method, evidence, confidence, caveats); started_at; finished_at; cost_usd; model text (the Gemini model that finally answered). The model request budget is 35 s including fallbacks; one retry of the step after a failure.

### evidence
id; run_id R; step_id R; ref text R (D1, R1, U1…); type R (table, chart, code, image_boxes, passage, diff); file_name R; location text (rows, page, bars); payload jsonb (snapshot, so the report works after the file is deleted).

### reports
id; run_id R; owner_id R; title R; summary_json R; confidence text; verified_count int; total_claims int; pdf_key text; template (plain, classic, compact, summary); typeface (clean, serif, technical); text_size (s, m, l); created_at R; expires_at R (Free 30 d, Pro 90, Pay-as-you-go 60, Custom 90/180/365); deleted_at; purge_at (deleted_at + 7 days).

### claims
id; report_id R; n int R; text R; status R (verified, flagged, unverified, mismatch); origin R (answer, document); doc_quote; doc_location; doc_value; computed_value; evidence_refs text[].

### share_links
id; report_id R; token_hash R (random token, shown once); created_at R; expires_at R (created_at + 7 days); revoked_at. A report has no link until created.

### ai_calls (usage tracking, one row per Gemini request)
| Field | Type | R | Limits / notes |
|---|---|---|---|
| id | uuid | yes | |
| run_id | uuid | no | null for calls outside a run (for example embeddings at upload) |
| step_id | uuid | no | |
| user_id | uuid | yes | |
| purpose | text | yes | route, plan, pick, compute, vision, critic, extract_claims, embed |
| model | text | yes | for example `gemini-3.8-flash` |
| attempt | int | yes | 1 = first model in the chain, 2 = first fallback, 3 = second fallback |
| status | text | yes | ok, rate_limited, timeout, error |
| tokens_in, tokens_out | int | yes | |
| est_cost_usd | numeric | yes | at paid prices |
| latency_ms | int | yes | counts against the 35 s budget |
| created_at | ts | yes | retention 90 days |

### usage_daily (feeds the daily caps)
day date R; user_id uuid (null = the global row); runs int; model_calls int; est_cost_usd numeric. Unique on (day, user_id). Caps (config, starting values): per user 30 runs and 300 model calls per day; global 100 runs and 1,000 model calls per day; the cached example is excluded. When a cap is reached the run is refused before any model call with outcome `rejected` and reason `daily_cap_user` or `daily_cap_global`, and it does not count as a run.

### audit_log
id; user_id; action R; target; ip_hash; created_at R. Retention 90 days.

### benchmark_runs
id; commit_sha R; score int R; total int R; details jsonb.

### Later (after v1, not built)
- report_members: report_id, user_id, role (owner, editor, viewer), can_download_pdf, invited_by, created_at
- report_invites: id, report_id, email, role, token_hash, expires_at
- comments: id, report_id, claim_id, author_id, parent_id, body, created_at, edited_at, deleted_at

## 2. Relationships
- users 1—N uploads, runs, reports, subscriptions, payments, usage_events, refresh_tokens
- runs N—N uploads through run_files
- runs 1—N agent_steps; runs 1—N evidence; agent_steps 1—N evidence; runs 1—N ai_calls; users 1—N usage_daily rows (plus one global row)
- runs 1—1 reports; reports 1—N claims; reports 1—N share_links
- uploads 1—N chunks
- claims refer to evidence by `evidence_refs` (the `ref` values)
- Access rule: a request may read or change a report only if the user is its owner (later: a member with the right role). The public page works only with a live, unexpired, unrevoked link. Original-file download: owner only and now < expires_at.

## 3. Main API operations
Paths are accepted. "Auth" = signed-in user; "Owner" = signed-in user who owns the item.

| Operation | Route (rec) | Input | Output | Who |
|---|---|---|---|---|
| Sign up | `POST /api/auth/signup` | email, password, display_name | user, session | Visitor |
| Log in | `POST /api/auth/login` | email, password | user, session | Visitor |
| Refresh / log out | `POST /api/auth/refresh`, `/logout` | refresh token | new session / ok | Auth |
| Me / update settings | `GET/PATCH /api/me` | lang, theme, default_view, discoverable, notify | user | Auth |
| Upload file | `POST /api/uploads` | file or pasted text, consent=true | upload (id, name, size, status, moderation) or rejection reason | Auth |
| List my uploads | `GET /api/uploads` | none | name, type, size, status | Auth (own) |
| Download original | `GET /api/uploads/{id}/file` | none | file | Owner, within 24 h only |
| Start run | `POST /api/runs` | mode, question, files with roles | run (id, status), or a limit, quota or daily-cap error | Auth |
| Live trace | `GET /api/runs/{id}/events` (SSE) | none | AgentState events | Owner |
| Get run | `GET /api/runs/{id}` | none | run, steps, outcome | Owner |
| Retry agent | `POST /api/runs/{id}/steps/{step}/retry` | none | step | Owner |
| Follow-up | `POST /api/reports/{id}/followups` | question | new run | Owner |
| Get report | `GET /api/reports/{id}` | none | report, claims, evidence | Owner |
| Update style | `PATCH /api/reports/{id}` | template, typeface, text_size | report | Owner |
| Export | `GET /api/reports/{id}/export?format=...` (pdf, docx, xlsx or csv) | format | file | Owner |
| Delete / undo | `DELETE /api/reports/{id}`, `POST /api/reports/{id}/restore` | none | ok | Owner (restore within 7 days) |
| Create / revoke share link | `POST /api/reports/{id}/share`, `DELETE /api/reports/{id}/share` | none | link (token shown once), expires_at | Owner |
| Public report | `GET /api/shared/{token}` | token | read-only report | Anyone with a live link |
| My reports | `GET /api/reports` | none | list with status | Auth (own) |
| People search | `GET /api/people?q=` | q (2+ characters) | up to 20: display_name, handle, languages | Auth; rate limited |
| Plans / usage | `GET /api/plans`, `GET /api/usage` | none | plans; for the user: runs left on the plan and today's runs and model calls against the daily caps | Visitor / Auth |
| Custom price | `POST /api/plans/custom/quote` | choices | price (server computed, rounded up, minimum $9) | Auth |
| Demo checkout | `POST /api/checkout` | plan or custom config | simulated payment, subscription | Auth |
| Try example | `GET /api/example` | none | cached example run and report | Everyone |

Rate limits (decided): 5 sign-ups per hour per IP; 30 runs per day per user on paid plans (the plan quota applies first); 30 people searches per minute per user. AI daily caps are in `usage_daily` above. A run refused by a cap returns the reason `daily_cap_user` or `daily_cap_global`.

## 4. Example mock records
Use these shapes for the UI-first mock data. The Seoul figures are placeholders until the real dataset is checked.

```json
// users
{"id":"u_01","email":"kim@example.com","display_name":"Kim","handle":"kim","discoverable":true,"plan":"free","lang":"en","theme":"dark","default_view":"simple","notify":true,"created_at":"2026-10-25T09:00:00Z","deleted_at":null}
```
```json
// refresh_tokens
{"id":"rt_01","user_id":"u_01","family_id":"fam_01","token_hash":"sha256:ab12…","replaced_by":null,"expires_at":"2026-11-24T09:00:00Z","revoked_at":null}
```
```json
// subscriptions
{"id":"sub_01","user_id":"u_01","plan":"custom","status":"active","custom_config":{"runs":100,"max_file_mb":100,"data_tier":"200k_rows_200_pages","retention_days":180,"parallel":3},"provider_customer_id":"sim_cus_01","current_period_end":"2026-11-25T00:00:00Z"}
```
```json
// payments
{"id":"pay_01","user_id":"u_01","provider_ref":"sim_pay_01","amount":1400,"currency":"USD","status":"succeeded","test_mode":true}
```
```json
// usage_events
{"id":"ue_01","user_id":"u_01","run_id":"r_01","kind":"run","amount":1,"created_at":"2026-10-25T09:05:00Z"}
```
```json
// uploads
{"id":"up_01","user_id":"u_01","filename":"seoul-subway-ridership.csv","mime":"text/csv","size":1843200,"sha256":"9f2c…","storage_key":"uploads/u_01/up_01","page_count":null,"row_count":4800,"status":"ready","moderation":"passed","created_at":"2026-10-25T09:00:00Z","expires_at":"2026-10-26T09:00:00Z","deleted_at":null}
```
```json
// chunks
{"id":"ch_01","upload_id":"up_02","page":2,"text":"Hapjeong station recorded the largest rise…","tsv":"'hapjeong':1 'largest':5 …","embedding":"[0.012, -0.044, …]","ocr_confidence":null}
```
```json
// runs
{"id":"r_01","user_id":"u_01","question":"Which stations grew fastest since 2019?","mode":"ask","question_type":"new","status":"finished","outcome":"answered","outcome_reason":null,"counted":true,"lang":"en","tokens_in":18200,"tokens_out":2100,"tool_calls":7,"cost_usd":0.041,"started_at":"2026-10-25T09:05:00Z","finished_at":"2026-10-25T09:05:12Z","error":null}
```
```json
// run_files
{"run_id":"r_01","upload_id":"up_01","role":"subject"}
```
```json
// agent_steps
{"id":"st_01","run_id":"r_01","agent":"data","seq":2,"status":"done","attempt":1,"kind":"result","payload":{"claim":"Hapjeong grew 18%","value":"+18%","method":"growth per station, 2019 vs latest year","evidence":["D1"],"confidence":0.97,"caveats":[]},"started_at":"2026-10-25T09:05:02Z","finished_at":"2026-10-25T09:05:07Z","cost_usd":0.019,"model":"gemini-3.8-flash"}
```
```json
// evidence
{"id":"ev_01","run_id":"r_01","step_id":"st_01","ref":"D1","type":"table","file_name":"seoul-subway-ridership.csv","location":"rows 1–4800","payload":{"columns":["station","year","boardings"],"rows_used":4800}}
```
```json
// reports
{"id":"rep_01","run_id":"r_01","owner_id":"u_01","title":"Hapjeong leads station growth since 2019","summary_json":{"answer":"Ridership grew fastest at Hapjeong, Seongsu and Magok."},"confidence":"high","verified_count":5,"total_claims":6,"pdf_key":null,"template":"plain","typeface":"clean","text_size":"m","created_at":"2026-10-25T09:05:12Z","expires_at":"2026-11-24T09:05:12Z","deleted_at":null,"purge_at":null}
```
```json
// claims
{"id":"cl_01","report_id":"rep_01","n":1,"text":"Hapjeong grew 18%","status":"verified","origin":"answer","doc_quote":null,"doc_location":null,"doc_value":null,"computed_value":"+18%","evidence_refs":["D1"]}
```
```json
// claims (Check mode, mismatch)
{"id":"cl_05","report_id":"rep_02","n":5,"text":"Magok grew 21%","status":"mismatch","origin":"document","doc_quote":"Magok grew 21% over the period.","doc_location":"page 2","doc_value":"21%","computed_value":"14.1%","evidence_refs":["D1","U1"]}
```
```json
// share_links
{"id":"sl_01","report_id":"rep_01","token_hash":"sha256:77ee…","created_at":"2026-10-25T09:10:00Z","expires_at":"2026-11-01T09:10:00Z","revoked_at":null}
```
```json
// ai_calls (first model rate-limited, fallback answered)
{"id":"ai_01","run_id":"r_01","step_id":"st_01","user_id":"u_01","purpose":"compute","model":"gemini-3.6-flash","attempt":2,"status":"ok","tokens_in":5200,"tokens_out":640,"est_cost_usd":0.0064,"latency_ms":6100,"created_at":"2026-10-25T09:05:05Z"}
```
```json
// usage_daily
{"day":"2026-10-25","user_id":"u_01","runs":1,"model_calls":9,"est_cost_usd":0.041}
```
```json
// audit_log
{"id":"al_01","user_id":"u_01","action":"share_link_created","target":"rep_01","ip_hash":"sha256:31c0…","created_at":"2026-10-25T09:10:00Z"}
```
```json
// benchmark_runs
{"id":"bm_01","commit_sha":"a1b2c3d","score":44,"total":50,"details":{"failed":["q07","q19"]}}
```

## summary_json shapes (mock, to confirm at 3.13 and 3.14)
Taken from `web/mocks/reports.json`. Every shape has `answer`.
- Ask: `{ "answer": string }`
- Check: `{ "answer": string, "not_checked": string[] }`
- Compare: `{ "answer": string, "totals": [{ "label", "a", "b", "change" }], "movers": [{ "label", "change_pct" }], "could_not_compare": string[] }`

Example claim IDs overlap across reports because they are examples; real IDs are uuids.

## OPEN questions in this file
1. The Gemini embedding model ID and its vector size `N` for `chunks.embedding` (recommend: choose the current Gemini embedding model in Google AI Studio and keep `N` in config).
