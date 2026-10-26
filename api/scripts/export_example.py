"""Write app/example/example_report.json from one real report in the dev database. No model call.

    docker compose run --rm -v "$PWD/api/app/example:/app/app/example" api \
        python scripts/export_example.py REPORT_ID

The report must be finished and English. Read the output before keeping it: the script drops
internal ids, Beaver's code and the column list, but it cannot judge the wording."""

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app` imports from /app/scripts

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Claim, Evidence, Report, Run  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.example import EXAMPLE_PATH, build_example  # noqa: E402
from app.schemas.reports import Claim as ClaimView  # noqa: E402
from app.schemas.reports import Evidence as EvidenceView  # noqa: E402
from app.schemas.reports import ReportDetail  # noqa: E402
from app.services.reports import report_view  # noqa: E402


def read_report(db: Session, report_id: uuid.UUID) -> ReportDetail:
    row = db.execute(
        select(Report, Run.lang).join(Run, Run.id == Report.run_id).where(Report.id == report_id)
    ).first()
    if row is None:
        sys.exit("no such report")
    report, lang = row
    claims = db.scalars(select(Claim).where(Claim.report_id == report.id).order_by(Claim.n)).all()
    evidence = db.scalars(
        select(Evidence).where(Evidence.run_id == report.run_id).order_by(Evidence.ref)
    ).all()
    return ReportDetail(
        report=report_view(report, lang),
        claims=[ClaimView.model_validate(c) for c in claims],
        evidence=[EvidenceView.model_validate(e) for e in evidence],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report_id", type=uuid.UUID)
    parser.add_argument("--out", type=Path, default=EXAMPLE_PATH)
    args = parser.parse_args()
    with Session(get_engine(get_settings().database_url.get_secret_value())) as db:
        detail = read_report(db, args.report_id)
    if detail.report.lang != "en":
        sys.exit("the example must be an English report")
    args.out.write_text(
        json.dumps(build_example(detail), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
