import secrets

from fastapi import APIRouter, Request

from app.common.constants import DROPBOX_REDIRECT_URI, GITHUB_REDIRECT_URI
from app.core.dependencies import CurrentActiveUser, SessionDep, get_current_active_user
from app.core.security import oauth, sign_state
from app.schemas.account import Token

from .service import (
    dropbox_callback_handler,
    github_callback_handler,
    google_callback_handler,
)

router = APIRouter()


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    assert oauth.google is not None
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", response_model=Token)
async def google_callback(request: Request, session: SessionDep):
    return await google_callback_handler(request, session)


@router.get("/github/login")
async def github_login(request: Request):
    redirect_uri = GITHUB_REDIRECT_URI or request.url_for("github_callback")
    assert oauth.github is not None
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", response_model=Token)
async def github_callback(request: Request, session: SessionDep):
    return await github_callback_handler(request, session)


@router.get("/providers/dropbox/login", description="add dropbox storage")
async def login_dropbox(request: Request, current_user: CurrentActiveUser):
    redirect_uri = DROPBOX_REDIRECT_URI or request.url_for("dropbox_callback")

    state_payload = {
        "user_id": str(current_user.id),
        "nonce": secrets.token_urlsafe(16),
    }
    state = sign_state(state_payload, expires_seconds=300)
    assert oauth.dropbox is not None
    return await oauth.dropbox.authorize_redirect(request, redirect_uri, state=state)


@router.get("/auth/dropbox/callback")
async def dropbox_callback(request: Request, session: SessionDep):
    return await dropbox_callback_handler(request, session)
