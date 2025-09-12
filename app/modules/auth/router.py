import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Form, Query, Request, Response

from app.common.constants import (
    DROPBOX_REDIRECT_URI,
    GITHUB_REDIRECT_URI,
    GOOGLE_CLIENT_ID,
)
from app.common.utils import encode_state
from app.core.dependencies import CurrentActiveUser, SessionDep, get_current_active_user
from app.core.security import oauth, sign_state
from app.schemas.account import (
    AccessToken,
    GoogleTokenPayload,
    RefreshToken,
    ShortLived,
    Token,
)

from .service import (
    dropbox_callback_handler,
    get_dropbox_access_token_from_refresh,
    get_google_access_token_from_refresh,
    github_callback_handler,
    google_callback_handler,
    google_incremental_auth,
    google_one_tap,
    refresh_token,
)

router = APIRouter()


@router.get("/google/login")
async def google_login(request: Request, redirect: Annotated[Optional[str], Query()]):
    state_data = {}
    if redirect:
        state_data["redirect"] = redirect

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
async def github_login(request: Request, redirect: Annotated[Optional[bool], Query()]):
    state_data = {}
    if redirect:
        state_data["redirect"] = redirect

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
async def login_dropbox(
    request: Request,
    redirect: Annotated[str | None, Query()],
    current_user: CurrentActiveUser,
):
    redirect_uri = DROPBOX_REDIRECT_URI or request.url_for("dropbox_callback")

    state_payload = {
        "user_id": str(current_user.id),
        "nonce": secrets.token_urlsafe(16),
    }
    if redirect:
        state_payload["redirect"] = redirect
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
    response.delete_cookie(key="refresh_token", path="/", domain=None)
    return {"message": "Logged out successfully"}


@router.get("/google/increment")
async def auth_google(
    request: Request,
    required_scopes: str,
    session: SessionDep,
    current_user: CurrentActiveUser,
    redirect: Annotated[Optional[str], Query()] = None,
):
    """
    required_scopes: space-separated scopes e.g.
      'openid email profile https://www.googleapis.com/auth/drive.file'
    """
    return await google_incremental_auth(
        request, required_scopes, session, current_user, redirect
    )


@router.get("/google/shortlived", response_model=ShortLived)
async def google_access_token(
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await get_google_access_token_from_refresh(current_user, session)


@router.get("/drobox/shortlived", response_model=ShortLived)
async def dropbox_access_token(
    session: SessionDep,
    current_user: CurrentActiveUser,
):
    return await get_dropbox_access_token_from_refresh(current_user, session)
