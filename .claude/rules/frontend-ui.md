---
paths:
  - "web/**/*.{ts,tsx,css}"
---

# Frontend UI rules (Next.js + CSS Modules)

- Mobile first: check 360 px, 390 px and desktop (1280 px) for every UI change; breakpoint 760 px.
- All texts through next-intl, in English and Korean; layouts must survive longer Korean, Russian and Uzbek strings.
- Accessible: real buttons and labels, visible focus ring (2 px accent), 44 px tap targets on mobile, contrast 4.5:1, meaning never by color alone.
- Light (Nocturne) and dark (Midnight) both use the CSS variables from `docs/design/DESIGN.md`; no hard-coded colors.
- Check against `docs/design/source/` and `docs/design/png/` before calling a screen done.
- Loading, empty and error states for every data view. Errors show a plain reason from an error code, never a raw message.
- The browser never holds a secret and never calls Google; it talks only to our API.
