from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Column, Field, SQLModel


class AppBaseModel(SQLModel):
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc)
        )
    )
