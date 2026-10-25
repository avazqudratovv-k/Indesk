import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import CheckConstraint, DateTime, MetaData, func, text
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Stable constraint names, so migrations can drop them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Primary key: a random uuid, made by the database when the app does not set one.
uuid_pk = Annotated[
    uuid.UUID,
    mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")),
]
# Every timestamp is timestamptz.
Timestamp = Annotated[datetime, mapped_column(DateTime(timezone=True))]
created_at_col = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now())
]


def enum_check(column: str, enum: type[StrEnum], name: str) -> CheckConstraint:
    """CHECK (column IN (...)) from a closed enum. Text + CHECK, not a native Postgres enum."""
    values = ", ".join(f"'{member.value}'" for member in enum)
    return CheckConstraint(f"{column} IN ({values})", name=name)
