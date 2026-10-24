# DESIGN.md — Indesk

Lives at: `docs/design/DESIGN.md` (exported design images go in the same folder, `docs/design/`). Last updated 2026-10-25.

Source: the design artifact **FINAL DESIGN PROJECT 2** (desktop boards 1280 px wide, mobile boards 390 px wide, light and dark). Token values below are copied from that design's CSS.

## 1. Direction
- **Mood:** an analyst's field notes: calm, precise, a little alive. Cool paper-like light theme; deep indigo dark theme with a soft glow.
- **Light theme = "Nocturne".** **Dark theme = "Midnight"**: indigo surfaces, faint aurora glow in the background, gradient headline text, glowing primary button. Not just black.
- **Final answer = design B "stamped document":** a cream paper block with a green stamp, a ruled list of claims, and a result line. It stays cream in dark mode.
- **Brand:** logo "Assembly" (five dots around a file), animal agents (owl, chameleon, beaver, hound, cat). Tone: startup-style product.
- **Inspiration:** only the design boards. No other references.

## 2. Design tokens
### Colors (CSS variables)
| Token | Light (Nocturne) | Dark (Midnight) |
|---|---|---|
| `--paper` (page) | `#EDEFF5` | `#0D1024` |
| `--paper2` | `#E3E6EF` | `#12163A` |
| `--card` | `#F8F9FC` | `#171C42` |
| `--rule` | `#D5D9E5` | `#232A5A` |
| `--rule2` | `#AEB4C7` | `#38417C` |
| `--ink` (text) | `#0A0D18` | `#ECEEFF` |
| `--ink2` | `#2A2F42` | `#C5CAEC` |
| `--mute` | `#636A80` | `#8F97C9` |
| `--accent` | `#5B49F0` | `#A596FF` |
| `--accentInk` (text on accent) | `#FFFFFF` | `#0B0A2A` |
| `--accentSoft` | `#E6E3FF` | `#272470` |
| `--accentText` | `#4033C4` | `#C6BDFF` |
| `--green` / `--ok` | `#0B7F54` | `#5CE5AA` |
| `--greenBg` | `#D8F2E4` | `#103A33` |
| `--bad` | `#D93A22` | `#FF8A7C` |
| `--badBg` | `#FFE6E1` | `#3D1C2E` |
| `--badLine` | `#F2A598` | `#8A3A4E` |
| `--warn` | `#8A5A00` | `#FFCB62` |
| `--warnBg` | `#FFF0C9` | `#3A2E1A` |
| `--hl` (highlight) | `#DAD6FF` | `#332F85` |
| `--track` | `#D5D9E5` | `#262D63` |
| `--disabled` | `#CBD0DD` | `#2B3270` |
| `--code` / `--codeInk` | `#0B0E18` / `#E8EAF4` | `#090B1F` / `#E6E8FA` |
| `--quoteBg` / `--quoteInk` | `#E3EEFF` / `#1B4C8F` | `#14305A` / `#A9D6FF` |
| `--hlInk` (text on highlight) | `#0A0D18` | `#ECE9FF` |
| `--medal` | `#E3E6EF` | `#1E2452` |
| `--warm` (= `--warnBg`) | `#FFF0C9` | `#3A2E1A` |
| `--grid` | `rgba(10,13,24,.07)` | `rgba(165,175,255,.08)` |
| `--dot` | `rgba(10,13,24,.28)` | `rgba(190,198,255,.35)` |
| `--shadow` | `0 18px 40px -26px rgba(20,24,60,.35)` | `0 24px 60px -30px rgba(3,5,30,.95)` |
| `--glow` | `rgba(91,73,240,.25)` | `rgba(165,150,255,.38)` |

**Agent colors**
| Agent | Light | Dark |
|---|---|---|
| Owl | `#C98A12` | `#F4BE55` |
| Chameleon | `#0E9F7E` | `#52E0B8` |
| Beaver | `#D4601F` | `#F58E52` |
| Hound | `#6C4CF0` | `#B49DFF` |
| Cat | `#D8316E` | `#FF80B2` |

**Primary button gradient:** `linear-gradient(135deg, #B3A6FF, #6FE3E8)`, text `#07081A`.
**Always-dark panels** (`.dk`, e.g. code, dark cards inside the light theme): paper `#06080F`, paper2 `#0B0E18`, card `#0F1320`, rule `#1A2030`, rule2 `#2E3650`, ink `#EEF0FA`, ink2 `#BFC4D8`, mute `#848CA6`, accent `#9B8CFF`, accentInk `#0A0A1E`, accentSoft `#1C1A45`, accentText `#B7ADFF`, green `#5BE0A0`, greenBg `#0F2A1D`, bad `#FF7A6B`, badBg `#331713`, badLine `#7A3027`, warn `#FFC857`, warnBg `#2E2406`, hl `#2C2A63`, track `#1E2538`, disabled `#2A3144`, code `#05060B`, quoteBg `#10223A`, quoteInk `#9FD2FF`, shadow `0 20px 50px -28px rgba(0,0,0,.9)`. Agent colors inside `.dk` differ slightly from Midnight: Owl `#F0B54A`, Chameleon `#4FD9B0`, Beaver `#F0884A`, Hound `#A28BFF`, Cat `#FF77A9`.
**Report paper (design B):** background `#FBF8F1`, text `#1A1C28`, stamp/ok `#0E7A4F`, error `#B3261E`, muted `#6b7088`, top border 8 px accent, radius 6, padding 40 48 34 (26 20 below 700 px). Same in both themes. Stamp: 3 px border `#0E7A4F`, radius 12, rotated -8deg, JetBrains Mono 900 16 px, letter-spacing .14em. Title: 400 46 / 1.08 (30 below 700 px), letter-spacing -.02em, always solid `#1A1C28` (no gradient text).
**Dark-only extras:** aurora radial gradients on the page background; inset top highlight and indigo shadow on cards; gradient text on large headlines (not on the cream paper); glow on the primary button and avatar; `color-scheme: dark`.

### Fonts
- Text and headings: **Onest** (300, 400, 500, 600, 700), fallback **Noto Sans KR**, **Noto Sans JP**, system-ui. Onest covers Latin and Cyrillic (English, Russian, Uzbek).
- Code, numbers, labels: **JetBrains Mono** (400, 500).
- Loaded from Google Fonts: `family=Onest:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+KR:wght@300;400;500;700&family=Noto+Sans+JP:wght@300;400;500;700`.

### Type scale
| Style | Size / line | Weight | Notes |
|---|---|---|---|
| Body | 16 / 1.55 | 400 | |
| Lede | 18 / 1.65 | 400 | color `--ink2` |
| Sub | 17 / 1.55 | 400 | color `--mute` |
| Fine print | 13.5 | 400 | color `--mute` |
| Eyebrow | 12 | 700, mono, uppercase, letter-spacing .14em | color `--mute` |
| H3 | 22 / 1.2 | 500 | letter-spacing -.015em |
| H2 | 46 / 1.08 | 300 | letter-spacing -.03em |
| Display (Home) | set per screen, line-height 1 | 300 | letter-spacing -.04em |
| Report title (paper) | 46 / 1.08 (30 below 700 px) | 400 | letter-spacing -.02em; Check and Compare reports use the same paper title |
| Mobile (below 760 px) | H2 32, page `h1` 40 / 1.05, lede 16.5 | | |
| Button | 15 (lg 16.5, sm 14) | 500 | |
| Nav link | 14.5 | 500 | min-height 38 |
| Brand name | 25 (23 on small screens) | 400 | letter-spacing -.045em; hidden on mobile |

### Spacing
The design has no named scale; these are the values it uses most: **4, 6, 8, 10, 12, 14, 18, 20, 24, 32, 40, 56** px. It also uses 16, 22, 26, 28, 30, 36 and 48 in specific places (listed below); use those only where named.
- Page container (`.wrap`): max-width 1200, side padding 40 (desktop), **20** below 760 px. Main area of board pages (Report, Moments, States): padding 36 32 on desktop; below 760 px side padding 20 and top 22.
- Big hero-style cards: padding 40 44 on desktop, 28 22 below 760 px.
- Gaps: 10 most common, then 8, 6, 12, 14, 20, 24; inside cards 12 to 18; card padding 24 to 36.
- Control heights: button 48 (lg 54, sm 38), icon button 40, nav link 38, mobile mast 60. Touch targets still grow to 44 on mobile.

### Radius
| Use | Value |
|---|---|
| Buttons, icon buttons, language switch | 12 |
| Mode switch / tab group (`ws-modes`), report toolbar | 16 |
| Section panels, tiles, claim cards, dashed hand-over card | 14 |
| Side and band panels | 24 |
| Hero panel | 28 |
| Small tags, stamp chips, nav links | 8 to 10 |
| Pills (status, evidence chip) | 999 |
| Report paper | 6 |

### Breakpoints
- **760 px:** below this, mobile layout (brand name hidden, language selector becomes a dropdown, grids become one column, a sticky bottom tab bar appears).
- **700 px:** only the report paper (padding, title size, stamp position) and the Check/Compare "no" row switch here. Use 760 for everything else and treat 700 as a known inconsistency of the board.
- **Mobile tab bar:** sticky at the bottom, three items (Home, Workspace, Plans) with a 22 px icon and an 11.5 px label; active item has ink text and a 2 px accent line on top; background paper at 88% with blur. Not in the desktop layout. `OPEN:` the design shows only the signed-out items; confirm the signed-in items (People, My reports) on mobile.
- Design boards: desktop 1280, mobile 390. Container max 1200.

## 3. Screens
Routes below are accepted. Design images are in `docs/design/png/` and design source in `docs/design/source/`. The last column gives the source file (desktop / mobile); the PNG names are `N. Title.png` for desktop and `Mobile · N. Title.png` for mobile (see the list in `docs/design/README.md`). The board for Check and Compare reports is 4b / 4c.

| Screen | Route | Who sees it | Main content | Source file (desktop / mobile) |
|---|---|---|---|---|
| Home | `/` | Everyone | Headline "Answers from your files, with proof.", silent looping demo, "Try with an example", the five agents, "Three ways to work with your files" (Ask, Check, Compare) | `Home.dc.html` / `HomeM.dc.html` |
| Log in | `/login` | Visitors | Email, password, link to Sign up | `Login.dc.html` / `LoginM.dc.html` |
| Sign up | `/signup` | Visitors | Email, password, display name | `Signup.dc.html` / `SignupM.dc.html` |
| Workspace | `/workspace` | Signed in | Heading "What would you like to know?"; tabs "1 Ask a question" and "2 Agents at work"; mode switch Ask / Check / Compare; upload, consent box, question box, chips, "What you can upload", "How each agent can end"; run tab with agent cards, handover card, live trace, "Guardrails in this run", "How a run can end" | `Workspace.dc.html` / `WorkspaceM.dc.html` |
| People | `/people` | Signed in | Search by name or handle; results (opted-in only); disabled "Invite" button | `People.dc.html` / `PeopleM.dc.html` |
| Report (Ask) | `/reports/{id}` | Owner | Stamped final answer, Simple/Detailed toggle, Share, Style & download, claims with evidence chips, confidence bar, follow-up thread, suggested questions | `Report.dc.html` / `ReportM.dc.html` |
| Report (Check) | `/reports/{id}` (mode = check) | Owner | Stamp "CHECKED n OF m MATCH", document figure vs computed figure per claim, "not checked" list | `ReportCheck.dc.html` / `ReportCheckM.dc.html` |
| Report (Compare) | `/reports/{id}` (mode = compare) | Owner | Stamp "COMPARED 2 FILES", totals, biggest movers, could-not-compare notes | `ReportCompare.dc.html` / `ReportCompareM.dc.html` |
| Shared report | `/s/{token}` | Anyone with a live link | Read-only report; no original files | `Shared.dc.html` / `SharedM.dc.html` |
| My page | `/my` | Signed in | Reports with status (Private / Shared, expires in N days), Share/Unshare, delete with undo, uploaded file names with "Deleted" status, account settings | `MyPage.dc.html` / `MyPageM.dc.html` |
| Plans | `/plans` | Everyone | Free, Pro, Pay-as-you-go, Custom calculator, demo checkout | `Plans.dc.html` / `PlansM.dc.html` |
| States (reference, not a route) | none | Developers | The 9 run outcomes as cards (answered, partial, not answerable, needs better input, rejected, failed, and the Check/Compare outcomes) | `States.dc.html` / `StatesM.dc.html` |
| Moments (reference, not a route) | none | Developers | Key moments used for the Home animation | `Moments.dc.html` / `MomentsM.dc.html` |

Navbar: Home, Workspace, People (signed in), My reports (signed in), Plans; Log in and Sign up when signed out.

## 4. Components
- **Navbar:** brand, links with accent underline on the active one, language switch (buttons on desktop, dropdown on mobile), theme toggle, avatar.
- **Buttons:** default, ink, primary (gradient), sizes sm / default / lg; icon button.
- **Eyebrow label** (small mono caps with accent dot or line), **cards**, **chips** (pills), **footer**.
- **Mode switch** (Ask / Check / Compare) and **tabs** (Ask / Agents at work); both use `aria-pressed` buttons.
- **Upload area** with file list and the consent checkbox; **question box**; **suggested-question chips**.
- **Agent card:** name, role, status (waiting, working, done, skipped, failed + Retry), expandable artifact. **Handover card** (what each agent passes on). **Live trace feed**. **Guardrails panel**.
- **Outcome card** (one per outcome, plus the "busy today" message).
- **Demo notice** (footer and upload area).
- **Report paper** (stamp, title, summary, claim rows, result line); **Simple/Detailed toggle**; **claim row** with verified/flagged/mismatch badge; **evidence chip** (icon for table, image, document or no source, plus file name and location); **confidence bar** (segments); **words-explained list** (Detailed only).
- **Style & download panel** (template, typeface, size, format buttons, Download); **Share panel** (create link, copy, expiry, preview, unshare).
- **Follow-up thread** (chat under the report).
- **Plan card**; **custom plan calculator**; **demo checkout**.
- **People result row**; **My page file list row**; **report list row**.
- **Chart** (drawn by the app from numbers, never by the AI).

## 5. UI rules
- **Mobile first:** build the 390 px layout first, then widen at 760 px. No horizontal page scroll. Wide tables scroll inside their own box. All touch targets are at least 44 px tall and wide on mobile (the design's small 38 px buttons grow to 44 px).
- **Light and dark:** every component uses the tokens above, never raw colors. Theme is stored per user (`users.theme`) and in the browser for visitors.
- **Loading:** a run shows each agent as queued, then working with its current action; buttons that wait show a disabled state. Exports show a progress message.
- **Empty:** run tab before any run says "No run yet, go to Ask". My page with no reports says so and links to Workspace. People search with an empty box shows only people the user has shared with.
- **Error:** every failure maps to one of the run outcomes with a plain reason and a next step (limits shown, "needs better input" with the exact reason, failed agent with Retry). Never a blank page, never a raw error.
- **Honesty marks:** flagged and unverified claims keep their warning marks in every template and export; the verified stamp is hidden when the critic did not run ("not checked").
- **Accessibility:** real `<button>` and `<a>` elements; visible focus ring (2 px `--accent`, offset 3 px); `aria-pressed` on toggles; `aria-label` on icon-only buttons; respect `prefers-reduced-motion`; meaning never by color alone (verdicts use text and symbols: "✓ matches", "✗ differs", "! not proven"); body text contrast 4.5:1.
- **Languages:** English and Korean first; all text comes from translation files (`next-intl`); layouts must survive longer Korean, Russian and Uzbek strings, because those are added later.
- **Demo notice:** the footer of every page and the upload area show "Indesk is a demo. Do not upload private or sensitive files." It uses `--warn` on `--warnBg`.
- **Busy state:** when a daily AI cap is reached the page shows the outcome-style message "Busy today, try again tomorrow", with the cached example as the next step.

## OPEN questions in this file
1. Exact content of the Moments board (reference only; confirm before using it for the Home animation).
