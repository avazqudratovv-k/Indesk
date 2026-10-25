"""The report contract built in ROADMAP 2.7 is the contract: the Pydantic schemas must parse
the web mock records and give them back unchanged. Fixtures are copies of web/mocks (see
tests/fixtures/README.md)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.reports import Claim, Evidence, Report
from app.schemas.runs import Run

FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED_REPORTS = {"rep_01", "rep_04"}


def records(name: str) -> list[dict[str, Any]]:
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = data["records"]
    return out


def roundtrip(model: type[BaseModel], record: dict[str, Any]) -> dict[str, Any]:
    # exclude_unset: keys the record never had (for example `ko`) are not invented on the way out.
    return model.model_validate(record).model_dump(mode="json", exclude_unset=True)


def ids(rows: list[dict[str, Any]]) -> list[str]:
    return [r["id"] for r in rows]


@pytest.mark.parametrize("record", records("reports"), ids=ids(records("reports")))
def test_report_roundtrips_unchanged(record: dict[str, Any]) -> None:
    assert roundtrip(Report, record) == record


@pytest.mark.parametrize("record", records("claims"), ids=ids(records("claims")))
def test_claim_roundtrips_unchanged(record: dict[str, Any]) -> None:
    assert roundtrip(Claim, record) == record


@pytest.mark.parametrize("record", records("evidence"), ids=ids(records("evidence")))
def test_evidence_roundtrips_unchanged(record: dict[str, Any]) -> None:
    assert roundtrip(Evidence, record) == record


@pytest.mark.parametrize("record", records("runs"), ids=ids(records("runs")))
def test_run_roundtrips_unchanged(record: dict[str, Any]) -> None:
    assert roundtrip(Run, record) == record


def test_fixtures_include_the_required_reports_and_their_runs() -> None:
    reports = {r["id"]: r for r in records("reports")}
    assert REQUIRED_REPORTS <= reports.keys()
    run_ids = set(ids(records("runs")))
    evidence_runs = {e["run_id"] for e in records("evidence")}
    claim_reports = {c["report_id"] for c in records("claims")}
    for rep_id in REQUIRED_REPORTS:
        assert reports[rep_id]["run_id"] in run_ids
        assert reports[rep_id]["run_id"] in evidence_runs
        assert rep_id in claim_reports


def test_growth_chart_rides_on_the_d1_evidence_payload() -> None:
    d1 = next(e for e in records("evidence") if e["id"] == "ev_01")
    chart = Evidence.model_validate(d1).payload.chart
    assert chart is not None
    assert chart.unit == "%"
    assert chart.series[0].label == "Hapjeong"
    assert (chart.series[0].value, chart.series[0].photo_value) == (18.2, 18)
    assert len(chart.series) == 8


def test_korean_translations_survive() -> None:
    rep = Report.model_validate(next(r for r in records("reports") if r["id"] == "rep_01"))
    assert rep.translations is not None
    assert rep.translations.ko is not None
    assert rep.translations.ko.summary_json.top_rows is not None
    claim = Claim.model_validate(next(c for c in records("claims") if c["id"] == "cl_01"))
    assert claim.ko is not None


def test_unknown_report_field_is_rejected() -> None:
    record = {**records("reports")[0], "invented": 1}
    with pytest.raises(ValidationError):
        Report.model_validate(record)


def test_unknown_claim_status_and_evidence_type_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Claim.model_validate({**records("claims")[0], "status": "verifed"})
    with pytest.raises(ValidationError):
        Evidence.model_validate({**records("evidence")[0], "type": "screenshot"})


def test_unknown_key_inside_evidence_payload_is_rejected() -> None:
    record = records("evidence")[0]
    with pytest.raises(ValidationError):
        Evidence.model_validate({**record, "payload": {**record["payload"], "sql": "select 1"}})
