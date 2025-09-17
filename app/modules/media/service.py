import asyncio
import io
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlmodel import Session, col, select

from app.common.constants import (
    ALLOWED_EXTENSIONS,
    DROPBOX_API,
    DROPBOX_SEARCH_URL,
    GOOGLE_FILES_URL,
)
from app.common.enum import DocumentPlatform, MediaType
from app.core.dependencies import CurrentActiveUser
from app.models.provider_model import Provider
from app.schemas.media import StorageItem


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


async def list_google_files(access_token: str, mime_types: list[str]) -> list[dict]:
    q_parts = [f"mimeType='{m}'" for m in mime_types]
    query = " or ".join(q_parts) + " and trashed=false"

    params = {
        "q": query,
        "fields": "files(id,name,mimeType,webViewLink)",
        "spaces": "drive",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            GOOGLE_FILES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.json())

    files = r.json().get("files", [])
    return [
        {
            "id": f["id"],
            "name": f["name"],
            "mime_type": f["mimeType"],
            "provider": "google",
            "link": f.get("webViewLink"),
        }
        for f in files
    ]


async def list_dropbox_files(access_token: str, extensions: list[str]) -> list[dict]:
    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for ext in extensions:
            body = {
                "query": ext,
                "options": {"filename_only": True, "file_status": "active"},
            }
            r = await client.post(
                DROPBOX_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code != 200:
                raise HTTPException(status_code=400, detail=r.json())

            matches = r.json().get("matches", [])
            for m in matches:
                metadata = m["metadata"]["metadata"]
                results.append(
                    {
                        "id": metadata["id"],
                        "name": metadata["name"],
                        "mime_type": None,  # Dropbox doesn’t provide MIME
                        "provider": "dropbox",
                        "link": metadata.get("path_display"),
                    }
                )

    return results


async def list_active_storage_providers(
    session: Session, current_user: CurrentActiveUser
):
    providers = session.exec(
        select(Provider).where(
            col(Provider.refresh_token_encrypted).is_not(None),
            Provider.account_id == current_user.id,
        )
    ).all()

    return {"items": providers}


async def list_active_providers(session: Session, current_user: CurrentActiveUser):
    providers = session.exec(
        select(Provider).where(
            Provider.account_id == current_user.id,
        )
    ).all()

    return {"items": providers}


class StorageService(ABC):
    @abstractmethod
    async def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
    ):
        raise NotImplementedError()

    @abstractmethod
    async def list_folders(self, access_token: str, folder_id: Optional[str] = None):
        raise NotImplementedError()

    @abstractmethod
    async def create_folder(
        self, access_token: str, name: str, parent_id: Optional[str] = None
    ):
        raise NotImplementedError()

    @abstractmethod
    async def delete_folder(self, access_token: str, folder_id: str):
        raise NotImplementedError()

    @abstractmethod
    async def list_sub_file_folder(
        self, access_token: str, folder_id: str, mime_type: str
    ):
        raise NotImplementedError()


class GoogleDriveStorageService(StorageService):

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.api_url = GOOGLE_FILES_URL

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        mime_type: Optional[list[str] | str] = None,
    ):
        """List files inside a folder, optionally filtered by mimeType."""
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        if mime_type:
            if isinstance(mime_type, (list, tuple, set)):
                # multiple types -> build OR condition
                mime_conditions = " or ".join([f"mimeType='{mt}'" for mt in mime_type])
                query += f" and ({mime_conditions})"
            else:
                # single type
                query += f" and mimeType='{mime_type}'"

        async with httpx.AsyncClient() as client:
            res = await client.get(
                self.api_url,
                params={
                    "q": query,
                    "fields": "files(id,name,mimeType,webViewLink)",
                    "includeItemsFromAllDrives": "true",
                    "supportsAllDrives": "true",
                    "corpora": "allDrives",
                },
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            # print("**|||||||||||||||||||*******", res.text)
            res.raise_for_status()

        return self.normalize_response(res.json())

    async def get_folder_id_by_name(self, folder_name: str):
        """Resolve folder name to its ID."""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        async with httpx.AsyncClient() as client:
            res = await client.get(
                self.api_url,
                params={"q": query, "fields": "files(id,name,webViewLink)"},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            res.raise_for_status()
            data = res.json()

            if data.get("files"):
                file = data["files"][0]["id"]
                return StorageItem(
                    id=file["id"],
                    name=file["name"],
                    mime_type="application/vnd.google-apps.folder",
                    type="folder",
                )

            return None

    async def list_folders(self, *args, **kwargs):
        """List all folders."""
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        async with httpx.AsyncClient() as client:
            res = await client.get(
                self.api_url,
                params={"q": query, "fields": "files(id,name,webViewLink)"},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            res.raise_for_status()
            return self.normalize_response(res.json(), True)

    async def create_folder(self, name: str, parent_id: Optional[str] = None):
        """Create a folder inside Drive."""
        body: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        async with httpx.AsyncClient() as client:
            res = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            res.raise_for_status()
            return self.normalize_response(res.json())

    async def delete_folder(self, folder_id: str):
        """Delete a folder."""
        async with httpx.AsyncClient() as client:
            res = await client.delete(
                f"{self.api_url}/{folder_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            if res.status_code == 204:
                return {"status": "deleted"}
            res.raise_for_status()
            return res.json()

    async def rename_folder(self, folder_id: str, new_name: str):
        """Rename a folder."""
        async with httpx.AsyncClient() as client:
            res = await client.patch(
                f"{self.api_url}/{folder_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"name": new_name},
            )
            res.raise_for_status()
            return self.normalize_response(res.json())

    def normalize_response(
        self, data: dict, is_folder: bool = False
    ) -> list[StorageItem]:
        """
        Normalize Google Drive API response into StorageItem list.
        """
        items = []
        for file in data.get("files", []):
            mime_type = (
                "application/vnd.google-apps.folder"
                if is_folder
                else file.get("mimeType")
            )
            item_type = (
                "folder"
                if mime_type == "application/vnd.google-apps.folder"
                else "file"
            )
            items.append(
                StorageItem(
                    id=file["id"],
                    name=file["name"],
                    type=item_type,
                    mime_type=mime_type,
                    path=None,  # Drive does not use paths
                    url=file.get("webViewLink"),
                )
            )
        return items

    async def list_sub_file_folder(self, folder_id: str, mime_type: list[str] | str):
        [files, folders] = await asyncio.gather(
            self.list_files(folder_id, mime_type),
            self.list_files(folder_id, "application/vnd.google-apps.folder"),
        )

        return folders + files


class DropBoxStorageService(StorageService):
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.api_url = DROPBOX_API

    async def list_files(
        self, path: str = "", mime_type: Optional[list[str] | str] = None
    ):
        """List files inside a Dropbox folder."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.api_url}/list_folder",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": path},
            )
            res.raise_for_status()

            data = self.normalize_response(res.json())
            if mime_type:
                if isinstance(mime_type, (list, tuple)):

                    return [
                        entry
                        for entry in data
                        if DocumentUrlConverter.detect_media_type(
                            entry.name.split(".")[-1]
                        )
                        in mime_type
                    ]
                return [
                    entry
                    for entry in data
                    if DocumentUrlConverter.detect_media_type(mime_type) in mime_type
                ]

            return data

    async def list_folders(self, path: str = ""):
        """List only folders."""
        data = await self.list_files(path)
        return [entry for entry in data if entry.type == "folder"]

    async def create_folder(self, path: str, *args, **kwargs):
        """Create a folder in Dropbox."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.api_url}/create_folder_v2",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": path, "autorename": False},
            )
            res.raise_for_status()
            return self.normalize_response(res.json())

    async def delete_folder(self, path: str):
        """Delete a folder in Dropbox."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.api_url}/delete_v2",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": path},
            )
            res.raise_for_status()
            return res.json()

    async def rename_folder(self, old_path: str, new_path: str):
        """Rename (move) a folder in Dropbox."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.api_url}/move_v2",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"from_path": old_path, "to_path": new_path},
            )
            res.raise_for_status()
            return self.normalize_response(res.json())

    def normalize_response(self, data: dict) -> list[StorageItem]:
        """
        Normalize Dropbox API response into StorageItem list.
        """
        items = []
        for entry in data.get("entries", []):
            item_type = "folder" if entry[".tag"] == "folder" else "file"
            items.append(
                StorageItem(
                    id=entry["id"],
                    name=entry["name"],
                    type=item_type,
                    mime_type=None,  # Dropbox does not expose MIME type here
                    path=entry.get("path_display"),
                    url=None,  # must be fetched via /sharing/create_shared_link_with_settings
                )
            )
        return items

    async def list_sub_file_folder(self, path: str, mime_type: list[str] | str):
        [files, folders] = await asyncio.gather(
            self.list_files(path, mime_type),
            self.list_folders(path),
        )

        return folders + files
