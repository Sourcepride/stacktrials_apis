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

    print("++++++++++++++++", userinfo)

    if not userinfo:
        # Fallback: some providers place claims in id_token
        id_token = token.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="No user info from Google")
        userinfo = verify_google_auth_token(id_token)

    email = userinfo["email"]
    sub = userinfo["sub"]

    # Upsert user
    statement = select(Provider).where(
        Provider.provider == Providers.GOOGLE, Provider.provider_id == sub
    )
    existing = session.exec(statement).first()

    if existing:
        user = existing.account
    else:
        user = register_account(
            session, email, Providers.GOOGLE.value, sub, scopes="openid email profile"
        )
    access, refresh = (
        create_jwt_token(str(user.id), email),
        create_jwt_token(str(user.id), email, "refresh"),
    )

    # Return tokens as JSON (or set HttpOnly cookies if you prefer)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "account": jsonable_encoder(user),
    }


def register_account(
    session: Session,
    email: str,
    provider: str,
    provider_id: str,
    scopes: Optional[str] = None,
) -> Account:
    account = Account(
        username=generate_random_username(session, email.split("@")[0]),
        email=email,
        profile=Profile(),  # type: ignore
    )

    provider = Provider(provider=provider, provider_id=provider_id, account=account, scopes=scopes)  # type: ignore
    session.add(provider)
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
