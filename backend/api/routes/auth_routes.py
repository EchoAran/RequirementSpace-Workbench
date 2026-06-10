from fastapi import APIRouter, Depends, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import AUTH_COOKIE_SECURE, AUTH_SESSION_EXPIRE_DAYS
from backend.database.database import get_session
from backend.database.model import UserModel
from backend.api.schemas.auth_schema import RegisterRequest, LoginRequest, UserResponse
from backend.api.services.auth_service import AuthService
from backend.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="auth_session",
        value=token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=AUTH_SESSION_EXPIRE_DAYS * 24 * 3600
    )


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
    user = await AuthService.authenticate_user(request, session)
    token = await AuthService.create_session(user.id, session)
    set_session_cookie(response, token)
    return user


@router.post("/logout")
async def logout(
    response: Response,
    auth_session: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
):
    if auth_session:
        await AuthService.revoke_session(auth_session, session)
    response.delete_cookie(
        key="auth_session",
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax"
    )
    return {"status": "success", "message": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserModel = Depends(get_current_user)):
    return user
