import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.common.constants import ALLOWED_ORIGINS, SECRET_KEY
from app.common.utils import safe_json_loads

from .modules import auth

app = FastAPI()


app.include_router(auth.router.router, prefix="/auth", tags=["auth"])


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
