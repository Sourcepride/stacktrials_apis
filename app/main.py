from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.sessions import SessionMiddleware

from app.common.constants import (
    ALLOWED_IMAGE_ORIGIN,
    ALLOWED_ORIGINS,
    IS_DEV,
    SECRET_KEY,
)
from app.common.utils import safe_json_loads

from .modules import account, auth, course

app = FastAPI()

version_1 = "/api/v1"
app.include_router(auth.router.router, prefix=f"{version_1}/auth", tags=["auth"])
app.include_router(
    account.router.router, prefix=f"{version_1}/account", tags=["account"]
)
app.include_router(
    course.router.router, prefix=f"{version_1}/courses", tags=["courses"]
)


assert ALLOWED_ORIGINS is not None
assert SECRET_KEY is not None

# middlewares
origins = safe_json_loads(ALLOWED_ORIGINS, [])


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="trails",
    max_age=86400,
    same_site="lax",
    https_only=False,  # TODO: set True in production with HTTPS
)


@app.get("/")
async def index():
    return {"ok": True}


# Whitelisted hostnames for external images
ALLOWED_HOSTS = set(safe_json_loads(ALLOWED_IMAGE_ORIGIN, []))


@app.get("/media/proxy")
async def proxy_image(url: Annotated[str, Query(description="External image URL")]):
    async def _fetch_image():
        try:
            parsed = urlparse(url)
            if parsed.hostname not in ALLOWED_HOSTS:
                return HTTPException(status_code=403, detail="Host not allowed")

            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url)

            if r.status_code != 200:
                return HTTPException(
                    status_code=r.status_code, detail="Failed to fetch image"
                )

            content_type = r.headers.get("content-type", "application/octet-stream")
            return Response(
                content=r.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},  # Cache for 1 day
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching image: {str(e)}"
            )

    value = await _fetch_image()
    if isinstance(value, HTTPException):
        raise value
    return value
