from datetime import datetime, timezone
from xmlrpc.client import boolean

from pydantic import BaseModel


class BaseSchema(BaseModel):
    class Config:
        json_encoders = {
            datetime: lambda dt: (
                (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        }


class OkModel(BaseModel):
    ok: bool


class PaginatedSchema(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ContactForm(BaseModel):
    title: str
    message: str


class ContactFormResponse(BaseModel):
    success: boolean
    message: str
