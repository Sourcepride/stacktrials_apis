import secrets
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
)
from sqlmodel import select

from app.common.constants import DROPBOX_REDIRECT_URI, GITHUB_REDIRECT_URI
from app.common.enum import Providers
from app.common.utils import encode_state
from app.core.dependencies import (
    CurrentActiveUser,
    CurrentActiveUserSilent,
    RedisDep,
    SessionDep,
)
from app.core.security import create_jwt_token, oauth, sign_state
from app.models.provider_model import Provider
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
    get_scopes_from_refresh_token,
    github_callback_handler,
    google_callback_handler,
    google_incremental_auth,
    google_one_tap,
    refresh_token,
    replace_provider,
)

router = APIRouter()


@router.post("/replace-provider")
async def replace_provider_call(
    temp_id: str, session: SessionDep, current_user: CurrentActiveUser, redis: RedisDep
):
    return await replace_provider(temp_id, session, redis, current_user)


@router.get("/google/login")
async def google_login(
    request: Request, redirect: Annotated[Optional[str], Query()] = None
):
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
    user: CurrentActiveUserSilent,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    state: Annotated[Optional[str], Query()] = None,
):
    return await google_callback_handler(
        request, session, state, user, redis, background_tasks
    )


@router.post("/google-one-tap", response_model=Token)
async def google_one_tab(
    token: Annotated[GoogleTokenPayload, Form()],
    session: SessionDep,
    background_tasks: BackgroundTasks,
):

    return await google_one_tap(
        token.credential, session, background_tasks, token.redirect
    )


@router.get("/github/login")
async def github_login(request: Request, redirect: Annotated[Optional[str], Query()]):
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
    session: SessionDep,
    user: CurrentActiveUserSilent,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    state: Annotated[Optional[str], Query()] = None,
):
    return await github_callback_handler(
        request, session, state, user, redis, background_tasks
    )


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
    return await oauth.dropbox.authorize_redirect(
        request,
        redirect_uri,
        state=state,
        token_access_type="offline",  # ✅ ask for refresh token
        force_reapprove="true",  # ✅ force re-consent every time
    )


@router.get("/dropbox/callback")
async def dropbox_callback(request: Request, session: SessionDep, redis: RedisDep):
    return await dropbox_callback_handler(request, session, redis)


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


@router.get(
    "/github/connect", description="connect github account to existing accouunt"
)
async def github_connect(
    request: Request,
    current_user: CurrentActiveUser,
    redirect: Annotated[Optional[bool], Query()],
):
    state_data = {}
    if redirect:
        state_data["redirect"] = redirect

    redirect_uri = GITHUB_REDIRECT_URI or request.url_for("github_callback")
    state_data["user_id"] = str(current_user.id)

    assert oauth.github is not None
    encoded_state = encode_state(state_data)
    return await oauth.github.authorize_redirect(
        request, redirect_uri, state=encoded_state
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


@router.get("/ws-shortlived", response_model=ShortLived)
async def ws_shortlived_token(session: SessionDep, current_user: CurrentActiveUser):
    token = create_jwt_token(str(current_user.id), current_user.email, "access", 1)
    return {"access_token": token, "expires_in": 1}


@router.get("/verify-scopes")
async def verify_google_scopes(
    current_user: CurrentActiveUser,
    session: SessionDep,
    scopes: str = Query(..., description="Comma-separated scopes to check"),
):
    """
    Verify if the user's stored Google refresh token still includes the required scopes.
    """
    required_scopes = set(scopes.split(","))

    google_provider = session.exec(
        select(Provider).where(
            Provider.provider == Providers.GOOGLE,
            Provider.account_id == current_user.id,
        )
    ).first()

    if not google_provider or not google_provider.refresh_token:
        return {
            "ok": True,
            "valid": False,
            "missing_scopes": list(required_scopes),
            "reason": "No Google provider or refresh token",
        }

    try:
        current_scopes = await get_scopes_from_refresh_token(
            google_provider.refresh_token
        )
    except HTTPException as e:
        return {
            "ok": False,
            "valid": False,
            "missing_scopes": list(required_scopes),
            "reason": f"Token refresh failed: {e.detail}",
        }

    missing = required_scopes - current_scopes

    return {
        "ok": True,
        "valid": len(missing) == 0,
        "current_scopes": list(current_scopes),
        "missing_scopes": list(missing),
    }
