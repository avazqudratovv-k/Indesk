import uuid
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict

from app.core.errors import ErrorCode


def _id_to_str(value: object) -> object:
    return str(value) if isinstance(value, uuid.UUID) else value


# Ids travel as strings. The database holds uuids; the web mocks use short ids such as "rep_01".
Id = Annotated[str, BeforeValidator(_id_to_str)]


class ApiModel(BaseModel):
    """Base for response shapes: built from ORM rows; an unknown field is an error."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorBody(BaseModel):
    code: ErrorCode
    run_id: str | None = None  # only on RUN_ACTIVE: the run that is in the way


class ErrorResponse(BaseModel):
    """The one error format: {"error": {"code": "..."}}; RUN_ACTIVE adds run_id."""

    error: ErrorBody
