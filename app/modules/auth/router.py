from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlmodel import select

from app.common.constants import ACCESS_TOKEN_MINUTES
from app.common.enum import Providers
from app.core.dependencies import SessionDep
from app.core.security import create_jwt_token, oauth
from app.models.provider_model import Provider
from app.models.user_model import Account
from app.schemas.account import AccountRead, Token

from .service import google_callback_handler, register_account

router = APIRouter()


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    assert oauth.google is not None
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", response_model=Token)
async def google_callback(request: Request, session: SessionDep):
    return await google_callback_handler(request, session)
