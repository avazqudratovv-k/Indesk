# Indesk — design source

Exported from the Claude Design canvas "FINAL DESIGN PROJECT 2". Each screen is a self-contained HTML file with the exact markup and inline styles (colors, fonts, spacing). Use these as the visual source of truth; build real components from them, don't copy the files into the app.

Theme: Nocturne (light) / Midnight (dark).

## Desktop (1280 px wide)

| Screen | File | Height |
|---|---|---|
| 0. Home | `source/Home.dc.html` | 2500 px |
| 1. Log in | `source/Login.dc.html` | 900 px |
| 2. Sign up | `source/Signup.dc.html` | 980 px |
| 3. Workspace: ask, check, compare, agents at work | `source/Workspace.dc.html` | 2700 px |
| 3b. People (signed in only) | `source/People.dc.html` | 1300 px |
| 4. Report | `source/Report.dc.html` | 3750 px |
| 5. Shared report (public, read-only) | `source/Shared.dc.html` | 1500 px |
| 6. My page | `source/MyPage.dc.html` | 1200 px |
| 7. Plans and usage | `source/Plans.dc.html` | 2500 px |
| 8. States and rules: agents, outcomes, follow-ups, styles and exports | `source/States.dc.html` | 2950 px |
| 9. Moments: sign-up, payment, run results, failures | `source/Moments.dc.html` | 1800 px |
| 4b. Report: check a document | `source/ReportCheck.dc.html` | 2400 px |
| 4c. Report: compare two files | `source/ReportCompare.dc.html` | 1900 px |

## Mobile (390 px wide)

| Screen | File | Height |
|---|---|---|
| Mobile · 0. Home | `source/HomeM.dc.html` | 3300 px |
| Mobile · 1. Log in | `source/LoginM.dc.html` | 1200 px |
| Mobile · 2. Sign up | `source/SignupM.dc.html` | 1300 px |
| Mobile · 3. Workspace: ask, agents at work, what each did | `source/WorkspaceM.dc.html` | 5000 px |
| Mobile · 3b. People (signed in only) | `source/PeopleM.dc.html` | 2600 px |
| Mobile · 4. Report | `source/ReportM.dc.html` | 6500 px |
| Mobile · 5. Shared report (public, read-only) | `source/SharedM.dc.html` | 2400 px |
| Mobile · 6. My page | `source/MyPageM.dc.html` | 2200 px |
| Mobile · 7. Plans and usage | `source/PlansM.dc.html` | 4600 px |
| Mobile · 8. States and rules | `source/StatesM.dc.html` | 5900 px |
| Mobile · 9. Moments | `source/MomentsM.dc.html` | 4200 px |
| Mobile · 4b. Report: check a document | `source/ReportCheckM.dc.html` | 3400 px |
| Mobile · 4c. Report: compare two files | `source/ReportCompareM.dc.html` | 3000 px |

## Notes for Claude Code
- The files are Claude Design component pages (`<x-dc>` markup, a small `data-dc-script` block, and a `support.js` include). They won't render on their own outside the canvas; read them for structure, text and styles.
- Pull the design tokens (colors for light and dark, fonts, sizes, spacing, radius) out of these files into `docs/ai/DESIGN.md` before building screens.
- For visual reference images, export PNGs from the canvas (Share → Export) into `docs/design/png/`.
