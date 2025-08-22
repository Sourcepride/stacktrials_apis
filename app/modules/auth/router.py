from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlmodel import select

from app.common.constants import ACCESS_TOKEN_MINUTES, GITHUB_REDIRECT_URI
from app.common.enum import Providers
from app.core.dependencies import SessionDep
from app.core.security import create_jwt_token, oauth
from app.models.provider_model import Provider
from app.models.user_model import Account
from app.schemas.account import AccountRead, Token

from .service import github_callback_handler, google_callback_handler

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
