from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.transport import requests
from google.oauth2 import id_token
from requests import request
from sqlmodel import Session, select

from app.common.constants import (
    ACCESS_TOKEN_MINUTES,
    FRONTEND_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    IS_DEV,
)
from app.common.enum import Providers
from app.common.utils import (
    decode_state,
    encode_state,
    extract_redirect_uri,
    generate_random_username,
)
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
        session,
        email,
        Providers.GOOGLE,
        sub,
        "openid email profile",
        {"redirect": "/"},
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
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    scopes = token.get("scopes")

    state_data = {}
    if state:
        state_data = decode_state(state)

    return authorize_or_register(
        session,
        email,
        Providers.GOOGLE,
        sub,
        scopes,
        state_data,
        access_token,
        refresh_token,
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
        session,
        email,
        Providers.GITHUB,
        provider_id,
        "read:user user:email",
        state_data,
    )


async def dropbox_callback_handler(request: Request, session: Session):

    [account, payload] = get_account_from_state(request, session)

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
        account_id=account.id,
    )

    set_provider_tokens(provider_obj, access_token, refresh_token, scopes, provider_id)

    session.add(provider_obj)
    session.commit()

    if payload.get("redirect"):
        return RedirectResponse(
            extract_redirect_uri(payload.get("redirect"), FRONTEND_URL)
        )

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


async def google_incremental_auth(
    request: Request,
    required_scopes: str,
    session: Session,
    current_user: Account,
    redirect: Optional[str],
):

    google_provider = session.exec(
        select(Provider).where(
            Provider.provider == Providers.GOOGLE,
            Provider.account_id == current_user.id,
        )
    ).first()

    user_scopes = set((google_provider.scopes or "").split()) if google_provider else {}
    needed_scopes = set(required_scopes.split())

    if needed_scopes.issubset(user_scopes):
        # Already has scopes, just return token
        token_data = await get_google_access_token_from_refresh(current_user, session)
        if redirect:
            return RedirectResponse(extract_redirect_uri(redirect, FRONTEND_URL))
        return JSONResponse(
            {
                "access_token": token_data["access_token"],
                "expires_in": token_data["expires_in"],
            }
        )

    encoded_state = encode_state({"redirect": redirect or ""})

    # Missing scopes → redirect to Google OAuth (incremental consent)
    scope_str = "".join(needed_scopes)
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={request.url_for("google_callback")}"
        f"&response_type=code"
        f"&state={encoded_state}"
        f"&scope={scope_str}"
        f"&access_type=offline"
        f"&include_granted_scopes=true"
    )
    return RedirectResponse(auth_url)


async def get_google_access_token_from_refresh(
    current_user: Account, session: Session
) -> dict[str, str]:
    google_provider = session.exec(
        select(Provider).where(
            Provider.provider == Providers.GOOGLE,
            Provider.account_id == current_user.id,
        )
    ).first()

    if not google_provider:
        raise HTTPException(status_code=404, detail="Provider does not exist")

    refresh_token = google_provider.refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token stored")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(token_url, data=data)

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.json())

    token_data = r.json()
    return {
        "access_token": token_data["access_token"],
        "expires_in": token_data["expires_in"],
    }


# -------- HELPER FUNCTIONS ---------


def authorize_or_register(
    session: Session,
    email: str,
    provider: Providers,
    provider_id: str,
    scopes: Optional[str] = None,
    state: dict = {},
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
):
    # Upsert user
    statement = select(Provider).where(
        Provider.provider == provider, Provider.provider_id == provider_id
    )
    existing = session.exec(statement).first()

    if existing:
        user = existing.account
        set_provider_tokens(existing, access_token, refresh_token, scopes, provider_id)
        session.add(existing)
        session.commit()
    else:
        user = create_account(session, email, provider.value, provider_id, scopes)
    access, refresh = (
        create_jwt_token(str(user.id), email),
        create_jwt_token(str(user.id), email, "refresh"),
    )

    if state.get("redirect"):
        secure = not IS_DEV
        samesite = "lax"
        cookie_domain = "localhost" if IS_DEV else None

        redirect_response = RedirectResponse(
            url=extract_redirect_uri(state.get("redirect", ""), FRONTEND_URL),
            status_code=302,
        )

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
    access_token=None,
    refresh_token=None,
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

    provider_obj = Provider(provider=provider, account=account)  # type:  ignore

    set_provider_tokens(provider_obj, access_token, refresh_token, scopes, provider_id)

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

    return [account, payload]


def set_provider_tokens(
    provider: Provider,
    access_token: str | None,
    refresh_token: str | None,
    scopes: str | None,
    provider_id: str,
):
    if refresh_token:  # only overwrite if new refresh_token is issued
        provider.refresh_token = refresh_token
    if access_token:
        provider.access_token = access_token
    if scopes:
        provider.scopes = " ".join(
            set((provider.scopes or "").split()) | set(scopes.split())
        )  # merge scopes
    provider.provider_id = provider_id
