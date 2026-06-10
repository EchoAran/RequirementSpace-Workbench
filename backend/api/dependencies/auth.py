from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import hash_session_token
from backend.database.database import get_session
from backend.database.model import UserModel, AuthSessionModel, UserRole, beijing_now


async def get_optional_user(
    request: Request,
    auth_session: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
) -> UserModel | None:
    if not auth_session:
        return None

    token_hash = hash_session_token(auth_session)
    query = (
        select(AuthSessionModel)
        .where(
            AuthSessionModel.session_token_hash == token_hash,
            AuthSessionModel.revoked_at == None,
            AuthSessionModel.expires_at > beijing_now()
        )
        .options(selectinload(AuthSessionModel.user))
    )
    res = await session.execute(query)
    db_session = res.scalar()
    if db_session is None:
        return None

    return db_session.user


async def get_current_user(
    user: UserModel | None = Depends(get_optional_user)
) -> UserModel:
    if user is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="account_disabled")
    return user


async def require_admin(
    user: UserModel = Depends(get_current_user)
) -> UserModel:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="forbidden")
    return user
