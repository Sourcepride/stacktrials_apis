from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Column, Field, SQLModel


class AppBaseModel(SQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    updated_at: datetime = Field(default=lambda: datetime.now(tz=timezone.utc))
