from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class AppBaseModelMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
