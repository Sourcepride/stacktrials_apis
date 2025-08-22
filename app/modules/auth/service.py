from typing import Optional

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlmodel import Session, select

from app.common.constants import ACCESS_TOKEN_MINUTES, GOOGLE_CLIENT_ID
from app.common.enum import Providers
from app.common.utils import generate_random_username
from app.core.security import create_jwt_token, oauth
from app.models.provider_model import Provider
from app.models.user_model import Account, Profile


async def google_callback_handler(request: Request, session: Session):
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

    return authorize_or_register(
        session, email, Providers.GOOGLE, sub, "openid email profile"
    )


async def github_callback_handler(request: Request, session: Session):
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

    return authorize_or_register(
        session, email, Providers.GITHUB, provider_id, "read:user user:email"
    )


def authorize_or_register(
    session: Session,
    email: str,
    provider: Providers,
    provider_id: str,
    scopes: Optional[str] = None,
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
