from pydantic import BaseModel


class OkModel(BaseModel):
    ok: bool


class PaginatedSchema(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool
