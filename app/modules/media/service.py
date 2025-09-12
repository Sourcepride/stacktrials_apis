import io
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from fastapi import UploadFile
from PIL import Image

from app.common.constants import ALLOWED_EXTENSIONS
from app.common.enum import DocumentPlatform, MediaType


class DocumentUrlConverter:
    """Convert share URLs to various formats needed for viewing"""

    @staticmethod
    def detect_media_type(url: str, content_type: Optional[str] = None) -> MediaType:
        """Detect media type from URL or content type"""
        url_lower = url.lower()

        if content_type:
            if content_type.startswith("image/"):
                return MediaType.IMAGE
            elif "pdf" in content_type:
                return MediaType.PDF
            elif any(
                doc_type in content_type
                for doc_type in ["word", "document", "presentation", "spreadsheet"]
            ):
                return MediaType.DOCUMENT
            elif content_type.startswith("video/"):
                return MediaType.VIDEO

        # Fallback to URL analysis
        if any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            return MediaType.IMAGE
        elif ".pdf" in url_lower:
            return MediaType.PDF
        elif any(
            ext in url_lower
            for ext in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]
        ):
            return MediaType.DOCUMENT
        elif any(ext in url_lower for ext in [".mp4", ".avi", ".mov", ".wmv"]):
            return MediaType.VIDEO

        return MediaType.OTHER

    @staticmethod
    def convert_google_drive_urls(url: str, media_type: MediaType) -> dict[str, str]:
        """Convert Google Drive URLs for different purposes"""
        # Extract file ID
        patterns = [
            r"/file/d/([a-zA-Z0-9-_]+)",
            r"id=([a-zA-Z0-9-_]+)",
            r"/d/([a-zA-Z0-9-_]+)",
        ]

        file_id = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                break

        if not file_id:
            return {"direct_url": url, "preview_url": url, "embed_url": url}

        base_urls = {
            "direct_url": f"https://drive.google.com/uc?export=download&id={file_id}",
            "preview_url": f"https://drive.google.com/file/d/{file_id}/view",
            "embed_url": f"https://drive.google.com/file/d/{file_id}/preview",
        }

        # Special handling for Google Docs, Sheets, Slides
        if (
            "/document/d/" in url
            or "/spreadsheets/d/" in url
            or "/presentation/d/" in url
        ):
            if "/document/d/" in url:
                base_urls["embed_url"] = (
                    f"https://docs.google.com/document/d/{file_id}/edit?usp=sharing&embedded=true"
                )
                base_urls["preview_url"] = (
                    f"https://docs.google.com/document/d/{file_id}/edit?usp=sharing"
                )
            elif "/spreadsheets/d/" in url:
                base_urls["embed_url"] = (
                    f"https://docs.google.com/spreadsheets/d/{file_id}/edit?usp=sharing&embedded=true"
                )
                base_urls["preview_url"] = (
                    f"https://docs.google.com/spreadsheets/d/{file_id}/edit?usp=sharing"
                )
            elif "/presentation/d/" in url:
                base_urls["embed_url"] = (
                    f"https://docs.google.com/presentation/d/{file_id}/edit?usp=sharing&embedded=true"
                )
                base_urls["preview_url"] = (
                    f"https://docs.google.com/presentation/d/{file_id}/edit?usp=sharing"
                )

        return base_urls

    @staticmethod
    def convert_onedrive_urls(url: str, media_type: MediaType) -> dict[str, str]:
        """Convert OneDrive URLs for different purposes"""
        base_urls = {"direct_url": url, "preview_url": url, "embed_url": url}

        if "onedrive.live.com" in url or "1drv.ms" in url:
            # Convert to embed format for Office documents
            if media_type == MediaType.DOCUMENT:
                embed_url = url.replace("/view", "/embed").replace(
                    "?e=", "&embed=true&e="
                )
                base_urls["embed_url"] = embed_url

            # Convert to download format
            if "?resid=" in url:
                params = parse_qs(urlparse(url).query)
                resid = params.get("resid", [None])[0]
                if resid:
                    base_urls["direct_url"] = (
                        f"https://onedrive.live.com/download?resid={resid}"
                    )
            else:
                base_urls["direct_url"] = url.replace("/view", "/download")

        return base_urls

    @staticmethod
    def convert_dropbox_urls(url: str, _media_type: MediaType) -> dict[str, str]:
        """Convert Dropbox URLs for different purposes"""
        base_urls = {
            "direct_url": url.replace("?dl=0", "?dl=1"),
            "preview_url": url.replace("?dl=0", "?dl=0"),
            "embed_url": url.replace("?dl=0", "?embed=1"),
        }

        return base_urls

    @classmethod
    def convert_urls(
        cls, url: str, provider: DocumentPlatform, media_type: MediaType
    ) -> dict[str, str]:
        """Convert URLs based on provider and media type"""
        if provider == DocumentPlatform.GOOGLE_DRIVE:
            return cls.convert_google_drive_urls(url, media_type)
        elif provider == DocumentPlatform.DROPBOX:
            return cls.convert_dropbox_urls(url, media_type)
        else:
            return {"direct_url": url, "preview_url": url, "embed_url": url}


def validate_image(file: UploadFile) -> bool:
    """Validate if the uploaded file is a valid image"""
    try:
        # Check file extension
        file_extension = Path(file.filename or "").suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            return False

        # Verify it's actually an image by trying to open it
        image_data = file.file.read()
        file.file.seek(0)  # Reset file pointer

        Image.open(io.BytesIO(image_data))
        return True
    except Exception:
        return False


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename while preserving the extension"""
    file_extension = Path(original_filename).suffix.lower()
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{file_extension}"
