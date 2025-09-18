from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class AppSQLModel(SQLModel):
    class Config:
        json_encoders = {
            datetime: lambda dt: (
                (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        }


class AppBaseModelMixin(AppSQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
