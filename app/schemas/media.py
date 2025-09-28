import re
from typing import Literal, Optional

from pydantic import BaseModel, HttpUrl, field_validator

from app.common.enum import DocumentPlatform, MediaType, Providers
from app.models.provider_model import ProviderBase


class DocumentValidationResponse(BaseModel):
    """Response for document validation"""

    is_valid: bool
    provider: DocumentPlatform
    media_type: MediaType
    direct_url: Optional[str] = None
    preview_url: Optional[str] = None
    embed_url: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    file_name: Optional[str] = None
    page_count: Optional[int] = None  # For PDFs
    error_message: Optional[str] = None


class DocumentItem(BaseModel):
    """Schema for external document items"""

    provider: DocumentPlatform
    url: HttpUrl
    media_type: MediaType
    title: Optional[str] = None
    description: Optional[str] = None
    file_name: Optional[str] = None

    @field_validator("url", mode="before")
    def validate_url(cls, v, values):
        """Ensure URL is from allowed providers"""
        url_str = str(v)

        is_external = values.data.get("provider") == DocumentPlatform.DIRECT_LINK

        if is_external:
            return v

        allowed_patterns = [
            r"drive\.google\.com",
            r"docs\.google\.com",
            r"onedrive\.live\.com",
            r"1drv\.ms",
            r"sharepoint\.com",
            r"dropbox\.com",
        ]

        if not any(
            re.search(pattern, url_str, re.IGNORECASE) for pattern in allowed_patterns
        ):
            raise ValueError("URL must be from an allowed provider")
        return v


class EXTFile(BaseModel):
    id: str
    name: str
    mime_type: Optional[str]
    provider: DocumentPlatform
    link: str


class RetrivedFiles(BaseModel):
    items: list[EXTFile]


class ProvidersResp(BaseModel):
    items: list[ProviderBase]


class StorageItem(BaseModel):
    id: str
    name: str
    type: Literal["file", "folder"]
    mime_type: Optional[str] = None  # Drive uses mimeType; Dropbox not always available
    path: Optional[str] = None  # Dropbox path_display; None for Drive
    url: Optional[str] = None  # Public URL (Drive webViewLink or Dropbox shared link)
