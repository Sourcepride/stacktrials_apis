from datetime import datetime, timedelta, timezone

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException

from app.common.constants import (
    ACCESS_TOKEN_MINUTES,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    JWT_ALG,
    JWT_SECRET,
    REFRESH_TOKEN_DAYS,
)

oauth = OAuth()

oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)


def decode_token(token: str) -> dict:
    if JWT_SECRET is None:
        raise ValueError("JWT SECRET NOT SET")

    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_jwt_token(user_id: str, email: str, kind: str = "access"):
    if JWT_SECRET is None:
        raise ValueError("JWT SECRET NOT SET")

    iat = datetime.now(tz=timezone.utc)
    payload = {"user_id": user_id, "iat": iat}

    if kind == "access":
        payload.update(
            {
                "type": "access",
                "email": email,
                "exp": iat + timedelta(minutes=ACCESS_TOKEN_MINUTES),
            }
        )
    else:
        payload.update(
            {
                "type": "refresh",
                "exp": iat + timedelta(days=REFRESH_TOKEN_DAYS),
            }
        )

    encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return encoded_jwt
