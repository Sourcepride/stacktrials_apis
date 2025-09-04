import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Form, Query, Request, Response

from app.common.constants import DROPBOX_REDIRECT_URI, GITHUB_REDIRECT_URI
from app.common.utils import encode_state
from app.core.dependencies import CurrentActiveUser, SessionDep, get_current_active_user
from app.core.security import oauth, sign_state
from app.schemas.account import AccessToken, GoogleTokenPayload, RefreshToken, Token

from .service import (
    dropbox_callback_handler,
    github_callback_handler,
    google_callback_handler,
    google_one_tap,
    refresh_token,
)

router = APIRouter()


@router.get("/google/login")
async def google_login(
    request: Request, should_redirect: Annotated[Optional[bool], Query()]
):
    state_data = {}
    if should_redirect:
        state_data["should_redirect"] = "true"

    redirect_uri = request.url_for("google_callback")
    assert oauth.google is not None
    if state_data:
        encoded_state = encode_state(state_data)
        return await oauth.google.authorize_redirect(
            request, redirect_uri, state=encoded_state
        )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", response_model=Token)
async def google_callback(
    request: Request,
    session: SessionDep,
    response: Response,
    state: Annotated[Optional[str], Query()] = None,
):
    return await google_callback_handler(request, response, session, state)


@router.post("/google-one-tap", response_model=Token)
async def google_one_tab(
    token: Annotated[GoogleTokenPayload, Form()],
    response: Response,
    session: SessionDep,
):
    return await google_one_tap(response, token.credential, session)


@router.get("/github/login")
async def github_login(
    request: Request, should_redirect: Annotated[Optional[bool], Query()]
):
    state_data = {}
    if should_redirect:
        state_data["should_redirect"] = "true"

    redirect_uri = GITHUB_REDIRECT_URI or request.url_for("github_callback")
    assert oauth.github is not None
    if state_data:
        encoded_state = encode_state(state_data)
        return await oauth.github.authorize_redirect(
            request, redirect_uri, state=encoded_state
        )
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", response_model=Token)
async def github_callback(
    request: Request,
    response: Response,
    session: SessionDep,
    state: Annotated[Optional[str], Query()] = None,
):
    return await github_callback_handler(request, response, session, state)


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


@router.get("/dropbox/callback")
async def dropbox_callback(request: Request, session: SessionDep):
    return dropbox_callback_handler(request, session)


@router.post("/refresh", response_model=AccessToken)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    data: Annotated[Optional[RefreshToken], Body()] = None,
):
    return await refresh_token(request, response, data, session)


@router.post("/logout")
async def logout(response: Response):
    # Clear the cookie by setting it to expire immediately
    response.delete_cookie(
        key="access_token",  # use the same key you used when setting it
        path="/",  # must match original cookie path
        domain=None,  # set if you had a domain originally
    )
    response.delete_cookie(key="referesh_token", path="/", domain=None)
    return {"message": "Logged out successfully"}
