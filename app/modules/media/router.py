import io
from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response

from app.common.constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_IMAGE_ORIGIN,
    DROPBOX_EXT_GROUPS,
    MAX_FILE_SIZE,
    MIME_TYPE_GROUPS,
    UPLOAD_DIR,
)
from app.common.enum import DocumentPlatform, MediaType
from app.common.utils import safe_json_loads
from app.core.dependencies import CurrentActiveUser, SessionDep
from app.modules.auth.service import (
    get_dropbox_access_token_from_refresh,
    get_google_access_token_from_refresh,
)
from app.modules.media.service import (
    DocumentUrlConverter,
    DropBoxStorageService,
    GoogleDriveStorageService,
    generate_unique_filename,
    list_active_providers,
    list_dropbox_files,
    list_google_files,
    validate_image,
)
from app.schemas.media import (
    DocumentItem,
    DocumentValidationResponse,
    ProvidersResp,
    RetrivedFiles,
    StorageItem,
)

media_routes = APIRouter()


async def get_storage_service(
    provider: DocumentPlatform, session: SessionDep, current_user: CurrentActiveUser
) -> GoogleDriveStorageService | DropBoxStorageService:
    access_token = await get_google_access_token_from_refresh(current_user, session)
    if provider == DocumentPlatform.GOOGLE_DRIVE:
        return GoogleDriveStorageService(access_token["access_token"])
    elif provider == DocumentPlatform.DROPBOX:
        return DropBoxStorageService(access_token["access_token"])
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")


# Whitelisted hostnames for external images
ALLOWED_HOSTS = set(safe_json_loads(ALLOWED_IMAGE_ORIGIN, []))


@media_routes.get("/media/proxy")
async def proxy_image(
    url: Annotated[str, Query(description="External document URL")],
    format: str = Query("direct", description="URL format: direct, preview, or embed"),
):
    """
    Proxy documents and return appropriate URLs for viewing
    """

    async def _fetch_image():
        try:
            converter = DocumentUrlConverter()

            # Detect provider and media type
            provider = DocumentPlatform.DIRECT_LINK
            if "drive.google.com" in url or "docs.google.com" in url:
                provider = DocumentPlatform.GOOGLE_DRIVE
            elif "onedrive.live.com" in url or "1drv.ms" in url:
                provider = DocumentPlatform.ONEDRIVE
            elif "dropbox.com" in url:
                provider = DocumentPlatform.DROPBOX

            # For now, assume document type - in real implementation, you'd detect this
            media_type = MediaType.DOCUMENT
            if ".pdf" in url.lower():
                media_type = MediaType.PDF
            elif any(ext in url.lower() for ext in [".jpg", ".png", ".gif"]):
                media_type = MediaType.IMAGE

            urls = converter.convert_urls(url, provider, media_type)

            # Return the requested format
            target_url = urls.get(f"{format}_url", urls["direct_url"])

            # For embed format, return the URL directly (for iframe usage)
            if format == "embed":
                return JSONResponse(
                    {
                        "embed_url": target_url,
                        "provider": provider.value,
                        "media_type": media_type.value,
                    }
                )

            # For direct/preview, proxy the content
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(target_url)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch document: {response.status_code}",
                )

            content_type = response.headers.get(
                "content-type", "application/octet-stream"
            )

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "X-Proxy-Source": provider.value,
                    "X-Media-Type": media_type.value,
                },
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error proxying document: {str(e)}"
            )

    value = await _fetch_image()
    if isinstance(value, HTTPException):
        raise value
    return value


@media_routes.post("/upload/image")
async def upload_single_image(file: UploadFile = File(...)):
    """Upload a single image file"""

    # Check if file is provided
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
        )

    # Check file size
    file_size = 0
    chunk_size = 1024
    chunks = []

    while chunk := await file.read(chunk_size):
        file_size += len(chunk)
        chunks.append(chunk)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE / 1024 / 1024:.1f}MB",
            )

    # Reconstruct file content
    file_content = b"".join(chunks)

    # Create a new UploadFile-like object for validation
    temp_file = UploadFile(filename=file.filename, file=io.BytesIO(file_content))

    # Validate image
    if not validate_image(temp_file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Allowed formats: "
            + ", ".join(ALLOWED_EXTENSIONS),
        )

    try:
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename)
        file_path = Path(UPLOAD_DIR) / unique_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Image uploaded successfully",
                "filename": unique_filename,
                "original_filename": file.filename,
                "file_path": str(file_path),
                "file_size": file_size,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}",
        )


@media_routes.post("/documents/validate", response_model=DocumentValidationResponse)
async def validate_document_url(document: DocumentItem):
    """
    Validate that a document URL is accessible and get metadata
    """
    try:
        converter = DocumentUrlConverter()

        # Get different URL formats
        urls = converter.convert_urls(
            str(document.url), document.provider, document.media_type
        )

        # Test accessibility with HEAD request first
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                response = await client.head(urls["direct_url"])
            except:
                # If HEAD fails, try GET with range
                try:
                    headers = {"Range": "bytes=0-1024"}
                    response = await client.get(urls["direct_url"], headers=headers)
                except:
                    # Last resort - just check if preview URL is accessible
                    response = await client.head(urls["preview_url"])

        if response.status_code not in [
            200,
            206,
            416,
            403,
        ]:  # 403 might be OK for some providers
            return DocumentValidationResponse(
                is_valid=False,
                provider=document.provider,
                media_type=document.media_type,
                error_message=f"Document not accessible (HTTP {response.status_code})",
            )

        # Extract metadata
        content_type = response.headers.get("content-type", "unknown")
        content_length = response.headers.get("content-length")
        file_size = int(content_length) if content_length else None

        # Detect actual media type from response
        detected_type = converter.detect_media_type(str(document.url), content_type)

        # Extract filename from URL or headers
        filename = None
        content_disposition = response.headers.get("content-disposition")
        if content_disposition and "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1].strip('"')
        else:
            filename = urlparse(str(document.url)).path.split("/")[-1]

        return DocumentValidationResponse(
            is_valid=True,
            provider=document.provider,
            media_type=detected_type,
            direct_url=urls["direct_url"],
            preview_url=urls["preview_url"],
            embed_url=urls["embed_url"],
            file_size=file_size,
            content_type=content_type,
            file_name=filename,
        )

    except Exception as e:
        return DocumentValidationResponse(
            is_valid=False,
            provider=document.provider,
            media_type=document.media_type,
            error_message=f"Validation failed: {str(e)}",
        )


@media_routes.get("/google/files", response_model=RetrivedFiles)
async def google_files_endpoint(
    media_type: Annotated[MediaType, Query()],
    current_user: CurrentActiveUser,
    session: SessionDep,
):
    type_ = (
        media_type.value.lower()
        if media_type.value.lower() in ["video", "image", "document"]
        else "document"
    )
    mimes = MIME_TYPE_GROUPS[type_]
    access_token = await get_google_access_token_from_refresh(current_user, session)
    return await list_google_files(access_token["access_token"], mimes)


@media_routes.get("/dropbox/files", response_model=RetrivedFiles)
async def dropbox_files_endpoint(
    media_type: Annotated[MediaType, Query()],
    current_user: CurrentActiveUser,
    session: SessionDep,
):
    type_ = (
        media_type.value.lower()
        if media_type.value.lower() in ["video", "image", "document"]
        else "document"
    )
    mimes = DROPBOX_EXT_GROUPS[type_]
    access_token = await get_dropbox_access_token_from_refresh(current_user, session)
    return await list_dropbox_files(access_token["access_token"], mimes)


@media_routes.get("/list-active-providers", response_model=ProvidersResp)
async def active_providers(
    current_user: CurrentActiveUser,
    session: SessionDep,
):
    return await list_active_providers(session, current_user)


ServiceDep = Annotated[
    GoogleDriveStorageService | DropBoxStorageService, Depends(get_storage_service)
]


# -------------------------
# LIST FILES
# -------------------------
@media_routes.get("/files", response_model=list[StorageItem])
async def list_files(
    service: ServiceDep,
    folder: Optional[str] = None,
    mime_type: Optional[MediaType] = Query(None),
):
    """
    List files in a folder (Google Drive) or path (Dropbox).
    """
    m_type = None
    if mime_type:
        if isinstance(service, GoogleDriveStorageService):
            m_type = MIME_TYPE_GROUPS.get(mime_type.value)
        else:
            m_type = DROPBOX_EXT_GROUPS.get(mime_type.value)

    return await service.list_files(folder or "", m_type)


# -------------------------
# LIST FOLDERS
# -------------------------
@media_routes.get("/folders", response_model=list[StorageItem])
async def list_folders(
    service: ServiceDep,
    path: Optional[str] = None,
):
    """
    List folders in provider.
    """
    return await service.list_folders(path or "")


# -------------------------
# CREATE FOLDER
# -------------------------
@media_routes.post("/folders", response_model=StorageItem)
async def create_folder(
    service: ServiceDep,
    name: str = Body(None, description="Folder name (Google Drive)/path (Dropbox)"),
    parent_id: Optional[str] = Body(
        None, description="Parent folder ID (Google Drive)"
    ),
):
    """
    Create a folder in Google Drive or Dropbox.
    """
    return await service.create_folder(name, parent_id)


# -------------------------
# DELETE FOLDER
# -------------------------
@media_routes.delete("/folders/{folder_id_or_path}")
async def delete_folder(folder_id_or_path: str, service: ServiceDep):
    """
    Delete a folder in Google Drive (by ID) or Dropbox (by path).
    """
    return await service.delete_folder(folder_id_or_path)


# -------------------------
# RENAME FOLDER
# -------------------------
@media_routes.patch("/folders/{folder_id_or_path}", response_model=StorageItem)
async def rename_folder(
    folder_id_or_path: str,
    service: ServiceDep,
    new_name: str = Body(
        ..., embed=True, description="New path for Dropbox |  new name Drive"
    ),
):
    """
    Rename a folder in Google Drive (by ID) or Dropbox (move by path).
    """

    return await service.rename_folder(folder_id_or_path, new_name)


# -------------------------
# LIST SUB FILE + FOLDER
# -------------------------
@media_routes.get("/subitems", response_model=list[StorageItem])
async def list_sub_file_folder(
    service: ServiceDep,
    folder: Optional[str],
    mime_type: MediaType = Query(),
):
    """
    List both sub-files and folders in a folder/path.
    """

    if isinstance(service, GoogleDriveStorageService):
        m_type = MIME_TYPE_GROUPS.get(mime_type.value)
    else:
        m_type = DROPBOX_EXT_GROUPS.get(mime_type.value)

    return await service.list_sub_file_folder(folder or "", m_type or [])
