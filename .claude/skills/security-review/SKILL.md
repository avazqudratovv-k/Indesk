---
name: security-review
description: Audit the code for real security issues (the mistakes AI-written apps often have) and prove each finding. Use before every deploy and after big features.
argument-hint: [optional: area to focus on, e.g. "auth" or "payments"]
disable-model-invocation: true
---

Security audit. Focus: $ARGUMENTS (if empty, audit everything).

Rules: don't change code yet. Never read .env files (names in .env.example only). Report only real, reachable issues, not style.

Check, skipping areas this project doesn't use:
1. Secrets: hardcoded keys/tokens, secrets in client-exposed env prefixes (NEXT_PUBLIC_, VITE_, EXPO_PUBLIC_), .env in .gitignore, secrets in git history (`git log -p -S` for key patterns), secrets in logs.
2. Access control: every resolver/route/server action checks auth AND ownership; try the two-account scenario (user B with user A's ID); admin-only actions refused for normal users; deleted/suspended users' tokens refused.
3. Client trust: prices, totals, quantities, discounts, roles, statuses or user IDs taken from the request instead of computed on the server.
4. Input and queries: missing server validation, injection (SQL, NoSQL operator objects like {"$gt":""}, regex), mass assignment (extra fields like role saved from the body).
5. Auth details: password hashing, token signing secret strength and expiry, token storage, password reset flow, brute-force protection.
6. Abuse: rate limits on login, signup, password, AI, uploads; counters that the client can reset; unbounded list sizes or page limits.
7. Payments (if any): server-side price, webhook signature check, idempotency, status checked before granting access.
8. Uploads: type/size checks on the server, stored path, served headers, no execution.
9. AI features: key server-side only, usage caps, prompt injection from user content, model output rendered safely (no raw HTML), user data not leaked into prompts of other users.
10. Deployment: debug/playground/introspection off, stack traces hidden, security headers, CORS origins exact, HTTPS, ports bound to 127.0.0.1, database user rights, source maps, dependency audit (`npm audit --omit=dev`).
11. Compare with docs/security/SECURITY.md: rules marked Tested that have no test, and rules that the code breaks.

For each finding:
- Severity (Critical / High / Medium / Low), file:line;
- what an attacker does, step by step, and the harm;
- PROOF: a request, script or test that shows it (run it locally against the dev server if safe; never against production);
- the fix, in one or two sentences.

Output: Critical first (flag at the very top), then High, Medium, Low; then "Checked and fine" (one line each); then "Couldn't check". Add confirmed issues to docs/ai/BACKLOG.md under Bugs. Don't commit.
