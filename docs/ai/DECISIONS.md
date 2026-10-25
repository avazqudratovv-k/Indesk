# DECISIONS.md — Indesk

Lives at: `docs/ai/DECISIONS.md`. Dates: exact for Oct 22, Oct 24 and Oct 25 decisions; "Oct 19" marks the early decisions, approximate. "Rejected" lists only alternatives we actually discussed; "none discussed" means we did not compare options. `OPEN:` marks what is still undecided, with my recommendation.

## Product
| # | Date | Decision | Why | Rejected alternatives |
|---|---|---|---|---|
| 1 | Oct 19 | Build **Indesk**: multi-agent app that answers from uploaded files with a cited report | Shows the course's AI skills (pandas, vision, NLP, RAG) plus agents; not a chatbot or e-commerce | Photo Memory, Prism Studio, Blueprint, Launchpad, Repo City |
| 2 | Oct 19 | Five agents: Owl (manager), Chameleon (vision), Beaver (data), Hound (retrieval, renamed from Bloodhound), Cat (critic) | Clear roles, memorable animal look | none discussed |
| 3 | Oct 19 | Answer only from the user's files, never from model world knowledge | The "proof" promise; "not in your files" beats guessing | An optional "allow general knowledge" switch |
| 4 | Oct 24 | Add modes **Check a document** and **Compare** | More than a report generator, same machinery | Other ideas (cross-file contradictions, saved questions, data-quality check) go to the README as next steps |
| 5 | Oct 24 | Check and Compare count as 1 run; free checks up to 10 claims, paid up to 25; caps $0.12 / $0.08 | Bounded cost | none discussed |
| 6 | Oct 22 | Reports private by default; Share makes a read-only link that expires in 7 days; Unshare revokes | Privacy | Public-by-default sharing |
| 7 | Oct 22 | Report top uses design B: stamped document (stamp, claims list, result line) | Makes "final report / final answer" obvious | A. Verdict card, C. Answer + proof |
| 8 | Oct 22 | "Style & download" panel: template, typeface, text size, format (PDF, Word, Excel, CSV), separate Download button | Clear download flow | one-click download |
| 9 | Oct 22 | Report styling never goes through the AI; 4 templates, 3 typefaces, 3 sizes | Numbers cannot change on re-format | Free-text styling |
| 10 | Oct 25 | Cut line: Tier A (core backend, Check, Compare, full UI) first; Tier B product layer as time allows; Vision (Tier C) after Nov 1 | Deadline about Nov 1 is too short for everything | Building everything before Nov 1 |
| 11 | Oct 25 | No admin role in v1 | Less to build | An admin screen |
| 12 | Oct 25 | UI languages: English and Korean first, all text in translation files; Japanese, Russian, Uzbek added later | Time; recruiters in Korea | All five at launch |
| 13 | Oct 25 | Demo only for now, with a clear "demo" notice; legal advice before any public launch | Safety and honesty | Public launch now |
| 14 | Oct 25 | Inspiration: only the design boards | Keep one reference | Other references |

## Data, privacy and money
| # | Date | Decision | Why | Rejected alternatives |
|---|---|---|---|---|
| 15 | Oct 19 | Originals and extracted data deleted after 24 h; owner-only download within 24 h; reports kept 30 days (Free), 90 (Pro), 60 (Pay-as-you-go), 90/180/365 (Custom) | Privacy; reports kept longer than 7 days | Keeping files longer |
| 16 | Oct 19 | Consent checkbox at upload; sensitive data is the user's responsibility; we still scan and moderate | Legal and safety | none discussed |
| 17 | Oct 24 | Nudity/sexual/minor content rejected and deleted at once; ID-like documents blocked | Safety | none discussed |
| 18 | Oct 22 | Plans: Free 2 runs; Pro $9/mo 50 runs; Pay-as-you-go $5 for 20 runs; Custom calculator ($0.10 per run, minimum $9) | Shows product thinking; keeps a margin over the per-run cap. Superseded in currency by #74 (KRW only) | none discussed |
| 19 | Oct 24 | Payments simulated ("demo checkout") behind a payments interface; Stripe test mode optional later | No real money in a portfolio demo | Real payments |
| 20 | Oct 24 | Storage: local disk behind an interface; S3/R2 later | Simple now, swappable | Cloud storage now |
| 21 | Oct 24 | Demo data: Seoul subway ridership (real open CSV), a short brief we write with planted errors (labelled demo), a chart photo from the same data; a Free-size set and a big set. The user checks the dataset and reports its columns | Uses all five agents; replaces the 6-row WW2 sample | WW2 sample |
| 22 | Oct 25 | Sign-up until deploy: email + password only, no verification code; limit 5 sign-ups per hour per IP; email verification after deploy | Time | Verification now |
| 23 | Oct 25 | Retention of usage events and audit log: 90 days | Enough to investigate abuse | none discussed |
| 24 | Oct 25 | Rate limits: 5 sign-ups per hour per IP; 30 runs per day per user on paid plans; 30 people searches per minute per user | Abuse control | none discussed |
| 25 | Oct 25 | Field length limits marked `(rec)` in DATA.md are accepted | Reasonable defaults | none discussed |

## AI provider and models
| # | Date | Decision | Why | Rejected alternatives |
|---|---|---|---|---|
| 26 | Oct 25 | **All AI features use Google Gemini.** Key only on the server, in an env file, never committed or sent to the browser | User decision; free tier while developing | Anthropic API (chosen Oct 24, replaced), OpenAI |
| 27 | Oct 25 | Light jobs (Owl routing and planning, Hound pick-and-quote, claim extraction): `gemini-3.5-flash-lite`. Fallback chain: `gemini-3.1-flash-lite`, then `gemini-3.8-flash` | Fast and cheap; all three are on the free tier | One model with no fallback |
| 28 | Oct 25 | Main reasoning (Beaver writes pandas code, Chameleon vision, Cat verdicts): `gemini-3.8-flash`. Fallback chain: `gemini-3.6-flash`, then `gemini-3.5-flash-lite` | Strongest model that is on the free tier | `gemini-4-argon` as default (paid only) |
| 29 | Oct 25 | `gemini-4-argon` only as an optional escalation when Beaver and Cat disagree; off by default; paid tier only | Strongest model but not on the free tier; price rises Dec 1, 2026 | Using it by default |
| 30 | Oct 25 | Model IDs live in a config file, not in code. Confirm each ID in Google AI Studio before the first call (the IDs were read from the official pricing page and third-party lists) | Models change often | Hard-coded names |
| 31 | Oct 25 | Time budget: 35 s per model request, shared across the whole fallback chain. A model that errors, hits a rate limit (HTTP 429) or runs out of its slice passes the request to the next model. If all fail, the agent shows "Failed" with Retry | Within the 30 to 40 s the user asked for | Fixed 45 s per step |
| 32 | Oct 25 | Per-user daily cap: 30 runs and 300 model calls. Global daily cap: 100 runs and 1,000 model calls (the cached example is excluded). Starting values in config; tune after reading the project's real limits at aistudio.google.com/rate-limit | The free tier has per-project limits that Google no longer lists in one table | No caps |
| 33 | Oct 25 | Free tier only while developing, with public demo data only. Move to the paid tier (billing on, $20 monthly limit) before anyone uploads their own files | Google's pricing page says free-tier content is used to improve Google's products; paid is not | Using real files on the free tier |
| 34 | Oct 25 | Embeddings: a Gemini embedding model. Model ID and vector size are decided at the backend step (ROADMAP 3.12), not now (Oct 25). Plan: pick the current Gemini embedding model in AI Studio, store the vector size in config, and keep BGE-M3 (local) only as a comparison test | "Gemini for all AI features" | BGE-M3 as the main choice |
| 35 | Oct 24 | Compute in code: pandas on the whole file; the model sees column names, a sample and results | Reliable on big files | Sending whole files to the model |
| 36 | Oct 24 | Agents return structured results (claim, value, method, evidence, confidence, caveats); the app renders them and draws charts | Consistent look, numbers cannot change | Free-form AI formatting |
| 37 | Oct 24 | Orchestration: our own typed state machine | Learn how agents work; easy to test | Heavy agent frameworks |
| 38 | Oct 24 | OCR (Tier C, after Nov 1): test Tesseract, PaddleOCR, a cloud OCR and the Gemini vision model on 4 to 5 real photos per language (Korean, Japanese, Russian, Uzbek); Gemini vision is the fallback | Pick by accuracy and cost | Choosing now |
| 39 | Oct 24 | Safety: ClamAV malware scan; an open NSFW image classifier first | Free and local | none discussed |
| 40 | Oct 24 | Sandbox: Docker container, no network, 5 s CPU, memory limit | Safe generated code | none discussed |
| 41 | Oct 24 | PDF text: PyMuPDF | Fast text and page extraction | none discussed |
| 42 | Oct 24 | Per-run safety limits: 12 steps, budget cap per run (Ask $0.05, Check $0.12, Compare $0.08), one retry per agent step | Bounded cost and time | none discussed |

## Stack and deployment
| # | Date | Decision | Why | Rejected alternatives |
|---|---|---|---|---|
| 43 | Oct 24 | Backend: Python 3.12, FastAPI, Pydantic | Course skills; typed agent output; easy streaming | NestJS (already used in Ticketzy; wanted a different stack) |
| 44 | Oct 24 | Database: PostgreSQL + pgvector + built-in full-text search (tsvector) | One database for rows, vectors and keywords | A separate vector database |
| 45 | Oct 24 | SQLAlchemy 2.0 + Alembic | Standard Python choice | none discussed |
| 46 | Oct 25 | Queue: Redis + **RQ** | Simpler to learn | arq |
| 47 | Oct 24 | Live trace to the browser with SSE (server-sent events) | Simple one-way stream | Vercel AI SDK, Langfuse/Logfire for the user-facing trace (maybe later for developer debugging only) |
| 48 | Oct 24 | Exports: WeasyPrint (PDF), python-docx (Word), openpyxl (Excel), csv | Common formats | none discussed |
| 49 | Oct 24 | Frontend: Next.js (App Router) + TypeScript | Course skills; matches the design | Vercel AI SDK |
| 50 | Oct 25 | Auth: email + password (Argon2); short-lived access token in an httpOnly cookie plus a rotating refresh token (stored hashed) | Safe default | Tokens in browser storage |
| 51 | Oct 25 | Styling: CSS variables from DESIGN.md with CSS Modules; no component library | The design is custom | A component library |
| 52 | Oct 25 | i18n: `next-intl` | Works with the Next.js App Router | none discussed |
| 53 | Oct 25 | Touch targets at least 44 px on mobile | Accessibility | 38 px small buttons |
| 54 | Oct 25 | Hosting: the same VPS as the user's other project, running Docker Compose with nginx in front, with an sslip.io hostname (decided Oct 25) | Simple and cheap | none discussed |
| 55 | Oct 25 | Repo folders: `web/`, `api/`, `docs/ai/`, `docs/security/`, `docs/design/` (design files inside docs, no top-level `design/`); `AGENTS.md` and `.gitignore` at the repo root | User decision | A top-level `design/` |
| 56 | Oct 24 | Tests: pytest; 50-question benchmark in CI | Proof it works | none discussed |
| 57 | Oct 25 | Roadmap is UI-first: skeleton and tokens, then each screen on mock data, then backend, then swap mock to real, then deploy | See the product early; screens define the data | Backend first |
| 58 | Oct 19 | Working method: Claude writes prompts for Claude Code; no secrets in prompts; `.env` never read by Claude Code; minimum database rights | Security and control | none discussed |
| 66 | Oct 25 | Locale comes from the `NEXT_LOCALE` cookie, no URL prefix (next-intl without i18n routing) | Simple routes; matches the routes in DESIGN.md | Locale in the URL |
| 67 | Oct 25 | The mock session (`dev_session` cookie) is ignored in production builds; `/dev/*` pages return 404 in production | The deployed demo must never fake a sign-in | none discussed |
| 68 | Oct 25 | Mock files use the shape `{ "_note", "records" }` so invented values can be marked as placeholders | Honesty about what is real | none discussed |
| 78 | Oct 25 | Working agreement: UI changes are verified with the `indesk-verify` skill (headless Chrome by script, never the Chrome extension: screenshots matrix, measured sizes and contrast, scroll and click checks, lint, typecheck, build). Screen prompts never edit docs/; docs are updated in separate batched prompts | Repeatable checks; the extension was not reliable; fewer doc conflicts | Chrome extension checks; docs edited in every screen prompt |

## Design
| # | Date | Decision | Why | Rejected alternatives |
|---|---|---|---|---|
| 59 | Oct 19 | Logo "Assembly" (five dots around a file); animal agent look | Memorable | none discussed |
| 60 | Oct 24 | Themes: Nocturne (light) and Midnight (dark, more than a black background); desktop and mobile boards | Polish for recruiters | Plain black dark mode |
| 61 | Oct 24 | Collaboration and the fine-tuned router come after v1 | Scope | Building them in v1 |
| 62 | Oct 25 | Mobile bottom tab bar: signed in = Home, Workspace, My, Plans; signed out = Home, Workspace, Plans. People is reached from the desktop navbar and from My. | The design boards show only the signed-out bar; the user decided the signed-in one | Five tabs |
| 63 | Oct 25 | The Moments board is not in Tier A; it is reference only and is left for later | Time | Using it for the Home animation now |
| 64 | Oct 25 | The paid Gemini tier is switched on before the link is shared with anyone (same as #33) | Free-tier content is used by Google | Sharing the link on the free tier |
| 65 | Oct 25 | The product demo notice uses the SPEC wording "Indesk is a demo. Do not upload private or sensitive files." The design boards' "clickable design mockup" footer text is not used | The app is real, not a mockup | Board wording |
| 69 | Oct 25 | Page background follows the board CSS exactly: `PageBackground` in the shell (contour art, noise, top fade, Midnight aurora) on every screen; orbit, hero art and closing-band art are Home-only. Assets copied from `docs/design/assets` to `web/public/bg/`. Noise is a tiled copy of the board's feTurbulence (same alpha), not a full-page SVG filter | Boards 1:1; cheap on long pages | Generated contours.svg + masks (guess from PNGs) |
| 70 | Oct 25 | Mobile navbar (below 761 px) is not sticky and scrolls away with the page. The board's mast is sticky at every width, so this is a deliberate deviation. From 761 px up it stays sticky. On /login and /signup on mobile the navbar's Log in and Sign up buttons are hidden (logo, language menu and theme toggle stay) | User choice; more room on small screens | Board: sticky at every width |
| 71 | Oct 25 | Mobile bottom tab bar is a floating pill (replaces the board's full-width bar): the active tab is a chip with icon and label, inactive tabs are icon only with aria-labels, icons use the same colour token as the theme toggle, 44 px targets, safe-area aware, hidden from 761 px. The tab lists of #62 are unchanged (signed in: Home, Workspace, My, Plans; signed out: Home, Workspace, Plans) | User choice | Board's full-width bar |
| 72 | Oct 25 | Logo behaviour (from the user's logo file): the mark tilts -8deg over .5s on hover (hover-capable devices only), on keyboard focus-visible, and on tap/click (a tap class for 600 ms). The link still navigates home. The wordmark is hidden below 761 px as on the board. Reduced motion: no transition | User's logo file | none discussed |
| 73 | Oct 25 | Auth screens (2.2, 2.3) deviate from the board: no Google or GitHub buttons or divider, no terms checkbox; a display name field is added (1 to 60 characters); password 10 to 128 characters (the board says 10; 128 is the added maximum); email max 254; headings and buttons read "Sign up" / "Log in" (ko 회원가입 / 로그인); "Reports kept for 7 days" is corrected to 30 days (Free plan). The submit is fake: in dev builds it sets `dev_session=in` and goes to /workspace; in production it shows "This demo has no accounts yet…" and signs nobody in (see #67) | Email and password only, no social login (#50); SPEC sign-up needs a display name; retention follows #15 | Board's social buttons and terms box |
| 74 | Oct 25 | Plans (2.4) shows prices in KRW only, in English and Korean, formatted with `Intl.NumberFormat`. Supersedes the USD prices of #18 in currency (#18 is kept). Prices: Free ₩0; Pro ₩12,000 per month (50 runs); Pay as you go ₩6,500 for 20 runs; Custom ₩130 per run with a ₩12,000 minimum. Internal cost fields (`cost_usd`) stay in USD and are never shown to users | Owner decision; Korean audience | USD prices (#18) |
| 75 | Oct 25 | Plans option groups (largest file, data size, retention, parallel runs) are shown as on the board but change no price. The board's "+₩" extras are not defined in SPEC or decisions, so they are hidden and only the number of runs sets the price. Revisit in section 3 together with the backend limits (do not advertise a limit the backend does not enforce). Signed-out visitors pressing a paid button go to /login | No invented prices | Inventing extra prices |
| 76 | Oct 25 | Plans corrections to the board to match SPEC: Free reports kept 30 days (board said 7); Pro shows "Reports kept for 90 days" instead of "PDF export and priority queue" (priority queue is not in SPEC, exports are not Pro-only); Pay as you go shows "kept 60 days"; the enforcement item "Email verification and a bot check" is replaced by "Sign-ups are limited per hour" (no email verification until after deploy, #22). The usage simulator is client-only demo state (no storage, no network) and is marked as a demo | Copy must match what the product does | Board wording |
| 77 | Oct 25 | Demo checkout rules: nothing is stored, logged, put in a URL or sent anywhere; no native form submission; autocomplete off and no card name attributes; values are cleared on close, Cancel, Done and unmount. Users type their own details within limits (card number 16 digits grouped by 4, expiry MM/YY with month 01 to 12 and not in the past, CVC 3 or 4 digits); no Luhn check. The outcome is a local deterministic test-mode rule: 4000 0000 0000 0002 is declined (animated cross and shake, plan unchanged, Try again keeps values); any other 16-digit number succeeds (animated check, then Done applies the plan). The window always shows "Demo: no real payments are taken." and "Do not enter real card details." and the two test numbers | Payments are simulated (#19); card data must never leave the page | Real or stored card handling |

## OPEN questions in this file
1. Gemini embedding model ID and vector size (#34), decided at ROADMAP 3.12.
2. Confirm every Gemini model ID in Google AI Studio before the first real call (#30).
