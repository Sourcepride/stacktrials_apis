import base64
import json
from typing import Optional

from fastapi import HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlmodel import Session, select

from app.common.constants import (
    ACCESS_TOKEN_MINUTES,
    FRONTEND_URL,
    GOOGLE_CLIENT_ID,
    IS_DEV,
)
from app.common.enum import Providers
from app.common.utils import decode_state, generate_random_username
from app.core.dependencies import SessionDep
from app.core.security import create_jwt_token, decode_token, oauth, verify_state
from app.models.provider_model import Provider
from app.models.user_model import Account, Profile
from app.schemas.account import AccessToken, RefreshToken


async def google_one_tap(response: Response, id_token: str, session: Session):
    userinfo = verify_google_auth_token(id_token)
    email = userinfo["email"]
    sub = userinfo["sub"]

    return authorize_or_register(
        response,
        session,
        email,
        Providers.GOOGLE,
        sub,
        "openid email profile",
        {"should_redirect": "true"},
    )


async def google_callback_handler(
    request: Request, response: Response, session: Session, state: str | None
):
    assert oauth.google is not None
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")

    if not userinfo:
        # Fallback: some providers place claims in id_token
        id_token = token.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="No user info from Google")
        userinfo = verify_google_auth_token(id_token)

    email = userinfo["email"]
    sub = userinfo["sub"]

    state_data = {}
    if state:
        state_data = decode_state(state)

    return authorize_or_register(
        response,
        session,
        email,
        Providers.GOOGLE,
        sub,
        "openid email profile",
        state_data,
    )


async def github_callback_handler(
    request: Request, response: Response, session: Session, state: str | None
):
    assert oauth.github is not None
    token = await oauth.github.authorize_access_token(request)

    resp = await oauth.github.get("user", token=token)
    profile = resp.json()

    provider_id = str(profile["id"])
    email = profile.get("email")

    # If email not available, fetch from /user/emails
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        verified_emails = [e for e in emails if e.get("verified")]
        if verified_emails:
            # Prefer primary verified email
            primary = next(
                (e for e in verified_emails if e.get("primary")), verified_emails[0]
            )
            email = primary["email"]

    state_data = {}
    if state:
        state_data = decode_state(state)

    return authorize_or_register(
        response,
        session,
        email,
        Providers.GITHUB,
        provider_id,
        "read:user user:email",
        state_data,
    )


async def dropbox_callback_handler(request: Request, session: Session):

    account = get_account_from_state(request, session)

    assert oauth.dropbox is not None
    token = await oauth.dropbox.authorize_access_token(request)

    if not token:
        raise HTTPException(status_code=400, detail="Failed to obtain token")

    # token contains access_token, refresh_token, expires_at, etc.
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    scopes = token.get("scope")

    # Get Dropbox account info
    resp = await oauth.dropbox.post("users/get_current_account", token=token)
    user_info = resp.json()
    provider_id = user_info["account_id"]

    provider_obj = Provider(
        provider=Providers.DROP_BOX,
        provider_id=provider_id,
        scopes=scopes,
        account_id=account.id,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    session.add(provider_obj)
    session.commit()

    return {"ok": True}


async def refresh_token(
    request: Request,
    response: Response,
    data: Optional[RefreshToken],
    session: Session,
):
    refresh_token = request.cookies.get("refresh_token")

    # if cookies already have token you shouldn't access data.refresh_token even if it exists
    if not refresh_token and data and data.refresh_token:
        refresh_token = data.refresh_token

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    token = decode_token(refresh_token)

    if token.get("type") != "refresh":
        raise HTTPException(400, "Not a refresh token")

    user = session.get(Account, token.get("user_id"))

    if not user:
        raise HTTPException(400, "User does not exists")

    access_token = create_jwt_token(str(user.id), user.email)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not IS_DEV,
        samesite="lax",
        max_age=3600,
    )
    return AccessToken(access_token=access_token)


# -------- HELPER FUNCTIONS ---------


def authorize_or_register(
    response: Response,
    session: Session,
    email: str,
    provider: Providers,
    provider_id: str,
    scopes: Optional[str] = None,
    state: dict = {},
):
    # Upsert user
    statement = select(Provider).where(
        Provider.provider == provider, Provider.provider_id == provider_id
    )
    existing = session.exec(statement).first()

    if existing:
        user = existing.account
    else:
        user = create_account(session, email, provider.value, provider_id, scopes)
    access, refresh = (
        create_jwt_token(str(user.id), email),
        create_jwt_token(str(user.id), email, "refresh"),
    )

    if state.get("should_redirect") == "true":
        secure = not IS_DEV
        samesite = "lax"
        cookie_domain = "localhost" if IS_DEV else None
        redirect_response = RedirectResponse(url=FRONTEND_URL, status_code=302)

        redirect_response.set_cookie(
            key="access_token",
            value=access,
            domain=cookie_domain,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=3600,
        )
        redirect_response.set_cookie(
            key="refresh_token",
            value=refresh,
            domain=cookie_domain,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=3600 * 7,
        )

        return redirect_response

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "account": jsonable_encoder(user),
    }


def create_account(
    session: Session,
    email: str,
    provider: str,
    provider_id: str,
    scopes: Optional[str] = None,
) -> Account:

    account = session.exec(select(Account).where(Account.email == email)).first()

    if not account:
        profile = Profile()  # type: ignore
        account = Account(
            username=generate_random_username(session, email.split("@")[0]),
            email=email,
            profile=profile,
        )
        session.add(account)

    provider_obj = Provider(
        provider=provider, provider_id=provider_id, scopes=scopes, account=account
    )  # type:  ignore

    session.add(provider_obj)
    session.commit()

    session.refresh(account)
    return account


def verify_google_auth_token(id_token_str: str) -> dict:
    try:
        # Verify the JWT with Google's public keys
        claims = id_token.verify_oauth2_token(
            id_token_str,
            requests.Request(),
            GOOGLE_CLIENT_ID,  # must match your app's client_id
        )
        return {
            "sub": claims["sub"],  # unique Google user ID
            "email": claims.get("email"),
            "name": claims.get("name"),
            "picture": claims.get("picture"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ID token: {e}")


def get_account_from_state(request: Request, session: Session):
    raw_state = request.query_params.get("state", "")

    if not raw_state:
        HTTPException(status_code=400, detail="A mandatory signed state is required")

    payload = verify_state(raw_state)

    if not payload:
        # invalid/expired state — reject or treat as anonymous
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    user_id = payload.get("user_id")

    account = session.get(Account, user_id)

    if not account:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    return account
