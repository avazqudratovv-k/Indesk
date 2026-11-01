import re
import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$")


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL.match(value) or ".." in value:
        raise ValueError("invalid email")
    return value


def _no_control_chars(value: str) -> str:
    if any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("control characters")
    return value


Email = Annotated[str, AfterValidator(_email)]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
    AfterValidator(_no_control_chars),
]


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    # Length is checked here, before anything is hashed.
    password: Annotated[str, Field(min_length=10, max_length=128, repr=False)]
    display_name: DisplayName


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    # A short password is just a wrong password; only the upper bound protects the hasher.
    password: Annotated[str, Field(min_length=1, max_length=128, repr=False)]


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    # Any other value than en or ko is treated as en by the service.
    lang: Annotated[str | None, Field(default=None, max_length=16)]


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(min_length=1, max_length=256, repr=False)]
    # Same rule as sign-up.
    new_password: Annotated[str, Field(min_length=10, max_length=128, repr=False)]
