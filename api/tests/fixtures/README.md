# Contract fixtures

Verbatim copies of `web/mocks/{reports,claims,evidence,runs,uploads,users}.json` (the web mock contract built in ROADMAP 2.7).
They are copies, not symlinks, so the API tests run from `api/` alone (the Docker image only contains `api/`).

Drift risk: if a mock changes in `web/mocks/`, this copy does not follow. When the web contract changes, re-copy the files
and fix the Pydantic schemas until `tests/test_contract_fixtures.py` passes again.
