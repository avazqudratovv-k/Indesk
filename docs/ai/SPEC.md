# SPEC.md — Indesk

Lives at: `docs/ai/SPEC.md`. Working name: **Indesk** (earlier "Insight Desk"). Status: design finished (FINAL DESIGN PROJECT 2), no code yet. Last updated 2026-10-25.
Rule used in this file: only what we decided. Anything not decided is marked `OPEN:` with a recommendation.

## 1. The problem
People have files with numbers in them (CSV tables, PDF reports, photos of charts) and want answers they can trust. A general AI chat answers from memory and from a pasted excerpt. It cannot read a very large file, it guesses when the file has no answer, and it does not show proof.

This is also a portfolio project: it is deployed to impress recruiters, not for real users. So it must never fail in front of someone who tries it with a big file.

## 2. The product in 2 sentences
Indesk lets you upload CSV, PDF or image files, ask a question, and watch five AI agents work as a team. You get a cited report where every claim is marked verified or flagged, plus two extra modes: **Check a document** (fact-check a document against your data) and **Compare** (what changed between two files).

One-line pitch: "an analyst that has to show its work." Home headline: "Answers from your files, with proof."
All AI features use **Google Gemini** (see `DECISIONS.md`).

The five agents: **Owl** (manager: routes and plans), **Chameleon** (vision/OCR), **Beaver** (data, pandas), **Hound** (retrieval/RAG), **Cat** (critic: verifies every claim).

## 3. Users and roles
| Role | Who | Can do |
|---|---|---|
| Visitor | Not signed in | See Home, Plans, Log in, Sign up. Open a public share link (Shared report). Try the cached example. Cannot upload or ask. |
| User | Signed in, any plan (Free, Pro, Pay-as-you-go, Custom) | Upload files, ask, Check, Compare, follow-up questions, change report style, download PDF/Word/Excel/CSV, share/unshare own reports, delete own reports (7-day undo), see My page, search People (only discoverable users), change plan (simulated checkout). |
| Report owner | The user who ran the report | Everything a User can do on that report. Only the owner can download the original file, and only within 24 h of upload. |
| Link viewer | Anyone with a live share link | Read the report. Cannot download the original files. Cannot ask. |
| Collaborator | Later (not in v1) | Owner/editor/viewer roles, comments. Never gets original files. |

There is **no admin role** in v1. Operate through the database and logs.

## 4. Main user flows
**A. Try the example (visitor or user)**
1. On Home click "Try with an example".
2. A prepared Seoul-subway run opens from a cached result, so it appears instantly, costs no AI calls and cannot fail.
3. The visitor sees the agents' trace and the report. To run their own files they must sign up.

**B. Sign up and log in**
1. Sign up with email, password, display name (no verification code until after deploy). 2. Log in. 3. Lands in Workspace. Plan starts as Free (2 runs). Sign-ups are limited to 5 per hour per IP.

**C. Ask a question**
1. Workspace, tab "1 Ask a question", mode "Ask a question".
2. Upload one or more files (or paste text), tick the consent box, type the question, press "Ask the team".
3. Server checks type, size, plan limits and daily caps, scans for malware, moderates images. Rejected files are named with the reason.
4. The app jumps to tab "2 Agents at work".

**D. Watch the run**
1. Owl plans; only needed agents wake (unneeded ones show "Skipped").
2. Each agent card shows status and expands to show its real artifact (Beaver: calculation + table + chart; Chameleon: image with boxes; Hound: quoted passage; Cat: verdicts; Owl: the plan line).
3. The run ends in exactly one outcome: answered, partial, not answerable, needs better input, rejected, failed.
4. If today's AI cap is reached, the user sees a plain "busy today, try again tomorrow" message, and the cached example still works.

**E. Read the report**
1. Top of page: stamped final answer (stamp "VERIFIED 5 OF 6", claims list, result line).
2. Toggle Simple / Detailed (words explained only in Detailed). Each claim has an evidence chip (file, location) and a verified/flagged badge.
3. Follow-ups appear as a chat thread under the report.

**F. Style and download**
1. Click "Style & download". 2. Pick template, typeface, text size. 3. Pick a format (PDF, Word, Excel, CSV). 4. Press the separate Download button.

**G. Share**
1. Report is private by default. 2. Click Share, create a link (read-only, expires in 7 days). 3. Unshare revokes it at once.

**H. Check a document**
1. Mode "Check a document": one document to check (PDF or pasted text) plus source data files.
2. Result: "N of M claims hold", each claim shows the document's figure next to the computed one; opinions are listed as "not checked".

**I. Compare**
1. Mode "Compare": file A and file B of the same kind. 2. Result: what changed, biggest movers, what could not be compared.

**J. My page**
1. Lists reports (status Private / Shared with expiry) and uploaded file names (name, type, size; "Deleted" after 24 h). 2. Share/Unshare, delete with 7-day undo.

**K. Plans**
1. Free, Pro $9/mo, Pay-as-you-go $5/20 runs, Custom plan calculator. 2. Simulated "demo checkout".

**L. People**
1. Signed-in users search by name or handle (2+ characters, 20 results max). Only people who opted in are found.

**Demo notice:** every public page footer and the upload area show a clear notice: "Indesk is a demo. Do not upload private or sensitive files." (Also see the Gemini free-tier note in section 6.)

## 5. v1 scope
**Cut line (decided Oct 25):** the core backend (foundation, first working run, manager and critic, PDF and retrieval), Check, Compare and the full UI come first (Tier A). Vision comes after Nov 1 (Tier C). The product layer (Tier B) is built as time allows; its screens still exist in the UI on mock data. Tiers are defined in `ROADMAP.md`.

| In v1 | Tier | Why |
|---|---|---|
| Sign up / log in | A | Quotas and private reports need accounts |
| Ask, Check, Compare modes | A | The product's core |
| CSV and text PDF | A | Data and retrieval skills |
| Five agents with live trace and expandable artifacts (Chameleon appears only when images exist, from Tier C) | A | The main demo |
| Verified/flagged claims, evidence chips | A | The trust promise |
| Full UI, all screens, light/dark, desktop and mobile | A | Final design; screens without a real backend stay on mock data |
| Gemini gateway: fallback chain, 35 s time budget, per-user and global daily caps | A | Reliability and cost control |
| Cached "Try with an example" | A | Never fails in front of recruiters |
| Share (7-day link), My page, delete with undo | B | Decided privacy rules |
| Plans, quotas, custom plan calculator, simulated checkout | B | Product thinking without real money |
| Exports PDF/Word/Excel/CSV, 4 templates | B | Decided |
| People search (opt-in; Invite button disabled) | B | Decided |
| Images and scanned PDFs: moderation, OCR tested on 4 languages, vision | C (after Nov 1) | Cut line |
| Email verification | after deploy | Decided Oct 25 |

| Not in v1 | Why |
|---|---|
| Collaborators, invites, comments | Large; data model designed now, built later |
| Fine-tuned small router model | Course-skill upgrade after v1; rule-based router comes first |
| Real payments | Simulated checkout only; Stripe test mode may replace it later |
| XLSX, DOCX/PPTX upload | "Later" |
| Video, audio, ZIP, password-protected PDF, live DB/URL connections | Not supported |
| General-knowledge answers | Answers come only from the user's files |
| Free-text report styling ("make it pink") | Styling never goes through the AI |
| README next steps: cross-file contradiction alerts, saved questions re-run on new data, data-quality check | Decided to document only |

## 6. Constraints
- **Deadline:** about 2026-11-01 (two weeks from 2026-10-18); 12 to 14 hours a day planned. Only Tier A is promised for that date.
- **Budget:** $0 while developing on the Gemini free tier. After moving to the paid tier, a **$20 monthly limit** until deploy. Per-run cost caps (estimated at paid prices, tracked even on the free tier): Ask about $0.05, Check about $0.12, Compare about $0.08.
- **AI provider:** Google Gemini only, key only on the server. **Free-tier warning:** Google's pricing page says free-tier content is used to improve Google's products; paid tier is not. So while on the free tier, use only the public Seoul demo data and test files, never real private files. Move to the paid tier before recruiters or anyone else upload their own files. The move happens before the link is shared with anyone (decided Oct 25).
- **Must-learn (first AI project):** FastAPI, pandas, computer vision/OCR, NLP, RAG, LLMs, agent orchestration. The user wants to understand each step.
- **Languages:** English and Korean first; all text in translation files so Japanese, Russian and Uzbek can be added after (the design already has all five).
- **Touch targets:** at least 44 px on mobile.
- **Working method:** Claude writes prompts for Claude Code; the user pastes them. Never put API keys or passwords in prompts or chat. Claude Code must never read, print or edit `.env` files. Database users get minimum rights. Each prompt states the repo path, "fresh chat, normal mode", whether servers should run, and "do not commit".
- **Privacy:** original files deleted after 24 h; reports kept 30 days (Free), 90 (Pro), 60 (Pay-as-you-go), 90/180/365 (Custom).
- **Public launch:** demo only for now; get legal advice before any public launch.

## 7. What success looks like (1-minute demo)
- 0:00 to 0:10 Home: silent looping animation with the headline "Answers from your files, with proof."
- 0:10 to 0:25 Click "Try with an example": the Seoul subway run opens instantly (cached).
- 0:25 to 0:40 Agents at work: Beaver reads a large CSV, Hound quotes the PDF; Cat checks. (Chameleon reading the chart photo joins after Nov 1.)
- 0:40 to 0:50 Report: stamped answer "VERIFIED 5 OF 6", one claim flagged "not proven", evidence chips with file and location.
- 0:50 to 1:00 Switch to Check a document: the planted error "Magok grew 21%" is shown next to the data's 14.1%.
- Success means: no errors, nothing slower than a few seconds on the cached example, works in light and dark, looks right on a phone. Figures above come from the mock design; the real numbers come from the real Seoul data, which the user is checking.
- A recruiter who uploads their own big file gets either a correct cited answer or a clear, polite message ("needs better input", size limit, "busy today"), never a crash.

## OPEN questions in this file
None. (The paid-tier switch happens before the link is shared; hosting is the user's existing VPS with an sslip.io hostname.)
