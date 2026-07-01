import logging

from fastapi import APIRouter, Depends, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import (
    AUTH_COOKIE_SECURE,
    AUTH_SESSION_EXPIRE_DAYS,
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_DOMAIN,
)
from backend.database.database import get_session
from backend.database.model import UserModel
from backend.api.modules.auth_account.schemas.auth import RegisterRequest, LoginRequest, UserResponse
from backend.api.modules.auth_account.application.auth_service import AuthService
from backend.api.dependencies.auth import get_current_user
from backend.core.logging import get_logger, log_event, sanitize_message
from backend.core.logging.events import AUTH_LOGIN_FAILED, AUTH_LOGIN_SUCCEEDED

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)


def set_session_cookie(response: Response, token: str) -> None:
    cookie_kwargs = {
        "key": "auth_session",
        "value": token,
        "httponly": True,
        "secure": AUTH_COOKIE_SECURE,
        "samesite": AUTH_COOKIE_SAMESITE,
        "max_age": AUTH_SESSION_EXPIRE_DAYS * 24 * 3600
    }
    if AUTH_COOKIE_DOMAIN:
        cookie_kwargs["domain"] = AUTH_COOKIE_DOMAIN
    response.set_cookie(**cookie_kwargs)


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    user = await AuthService.register_user(request, session)
    token = await AuthService.create_session(user.id, session)
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    try:
        user = await AuthService.authenticate_user(request, session)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "auth",
            AUTH_LOGIN_FAILED,
            "Auth login failed",
            error_type=type(exc).__name__,
            error_message=sanitize_message(str(exc)),
        )
        raise
    token = await AuthService.create_session(user.id, session)
    set_session_cookie(response, token)
    log_event(
        logger,
        logging.INFO,
        "auth",
        AUTH_LOGIN_SUCCEEDED,
        "Auth login succeeded",
        user_id=user.id,
    )
    return user


@router.post("/logout")
async def logout(
    response: Response,
    auth_session: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
):
    if auth_session:
        await AuthService.revoke_session(auth_session, session)
    cookie_kwargs = {
        "key": "auth_session",
        "httponly": True,
        "secure": AUTH_COOKIE_SECURE,
        "samesite": AUTH_COOKIE_SAMESITE
    }
    if AUTH_COOKIE_DOMAIN:
        cookie_kwargs["domain"] = AUTH_COOKIE_DOMAIN
    response.delete_cookie(**cookie_kwargs)
    return {"status": "success", "message": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserModel = Depends(get_current_user)):
    return user
