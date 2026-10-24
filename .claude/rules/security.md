# Security rules (always on — no paths, so this loads in every session)

Never trust the client. Every price, total, user ID, role, status, feature flag and limit is decided or re-checked on the server. If a value comes from the browser, the mobile app or the request body, an attacker controls it.

When writing or changing code:
- Check auth AND ownership on the server for every read and write of a private record. Hiding a button is not protection.
- Validate every input on the server (type, length, range, format, allowed values).
- No secrets in client code or `NEXT_PUBLIC_` / `VITE_` / `EXPO_PUBLIC_` variables. Never log tokens, passwords or private content.
- Build database queries with the ORM or parameters, never by joining user input into a query string or passing raw objects as filters.
- Rate-limit anything expensive or guessable (login, signup, password reset, AI calls, uploads, emails).
- Return error codes, not internal messages or stack traces.
- New dependency: say why, check it's maintained, pin the version.
- If a change touches auth, payments, uploads, personal data or AI: re-read `docs/security/SECURITY.md`, follow it, and say in the report which rule you applied and how you tested it.
- Never mark a security control as done without a test that passed. Unverified = say "not verified".
