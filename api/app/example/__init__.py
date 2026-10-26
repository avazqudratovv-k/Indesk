"""The cached "Try with an example" report: a file, validated once, served with no model call.

`example_report.json` is made by scripts/export_example.py from a real report; this module only
reads it back."""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.reports import Claim, Evidence, EvidencePayload, Report, ReportDetail

EXAMPLE_PATH = Path(__file__).parent / "example_report.json"
EXAMPLE_META_PATH = EXAMPLE_PATH.with_name("example_report.meta.json")  # not served; for the owner

EXAMPLE_ID = "example"
EXAMPLE_OWNER_ID = "00000000-0000-0000-0000-000000000000"  # placeholder; owns nothing real
EXAMPLE_FILE_NAME = "seoul_subway_2026-09.csv"  # the public demo file's name
EXAMPLE_EXPIRES_AT = datetime.fromisoformat("2099-01-01T00:00:00+00:00")

# The only evidence-payload keys an example keeps. Beaver's code and the column list stay out.
PAYLOAD_KEYS = (
    "title", "body", "tool", "quote", "text", "rows_used", "table", "chart", "reason", "method",
    "ko",
)  # fmt: skip


def build_example(source: ReportDetail) -> dict[str, Any]:
    """A real report as a public example: stable placeholder ids, the demo file name, no code, no
    column list, no internal id. Everything it keeps is shown on the report page anyway."""
    report = source.report
    claims = [
        Claim.model_validate(
            {
                **c.model_dump(mode="json", exclude_unset=True),
                "id": f"{EXAMPLE_ID}-claim-{c.n}",
                "report_id": EXAMPLE_ID,
            }
        )
        for c in source.claims
    ]
    evidence = [
        Evidence.model_validate(
            {
                "id": f"{EXAMPLE_ID}-evidence-{e.ref}",
                "run_id": f"{EXAMPLE_ID}-run",
                "step_id": f"{EXAMPLE_ID}-step",
                "ref": e.ref,
                "type": e.type,
                "file_name": EXAMPLE_FILE_NAME,
                "location": e.location,
                "payload": EvidencePayload.model_validate(
                    {
                        k: v
                        for k, v in e.payload.model_dump(mode="json", exclude_unset=True).items()
                        if k in PAYLOAD_KEYS
                    }
                ),
            }
        )
        for e in source.evidence
    ]
    cleaned = Report.model_validate(
        {
            **report.model_dump(mode="json", exclude_unset=True),
            "id": EXAMPLE_ID,
            "run_id": f"{EXAMPLE_ID}-run",
            "owner_id": EXAMPLE_OWNER_ID,
            "pdf_key": None,
            "expires_at": EXAMPLE_EXPIRES_AT,
            "deleted_at": None,
            "purge_at": None,
        }
    )
    detail = ReportDetail(report=cleaned, claims=claims, evidence=evidence)
    out: dict[str, Any] = detail.model_dump(mode="json", exclude_unset=True)
    return out


@lru_cache
def load_example() -> ReportDetail:
    """Read and validate the file. A bad file raises, so startup (see main.lifespan) stops."""
    return ReportDetail.model_validate(json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")))
