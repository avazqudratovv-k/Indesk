---
paths:
  - "pages/**/*.{ts,tsx}"
  - "src/**/*.{tsx,scss,css}"
  - "libs/components/**/*"
---

# Frontend UI rules (example — adapt the paths and rules)

- Mobile first: check 360 px, 390 px and desktop for every UI change.
- All texts through i18n, in every language the app supports.
- Accessible: real buttons and labels, visible focus, 44 px tap targets, color contrast.
- Light and dark theme both use the design tokens; no hard-coded colors.
- Loading, empty and error states for every data view.
