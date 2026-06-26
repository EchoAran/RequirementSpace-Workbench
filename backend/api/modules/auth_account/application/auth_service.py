from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import ADMIN_INVITE_CODE_HASH, AUTH_SESSION_EXPIRE_DAYS
from backend.core.security import hash_password, verify_password, generate_session_token, hash_session_token
from backend.database.model import UserModel, AuthSessionModel, UserRole, beijing_now
from backend.api.modules.auth_account.schemas.auth import RegisterRequest, LoginRequest


class AuthService:
    @staticmethod
    async def register_user(request: RegisterRequest, session: AsyncSession) -> UserModel:
        email = request.email.strip().lower()

        # Check uniqueness
        res = await session.execute(select(UserModel).where(UserModel.email == email))
        if res.scalar() is not None:
            raise HTTPException(status_code=400, detail="email_already_registered")

        role = UserRole.USER.value

        if request.invite_code is not None:
            invite_hash = ADMIN_INVITE_CODE_HASH
            if not invite_hash:
                raise HTTPException(status_code=400, detail="invalid_invite_code")
            if not verify_password(request.invite_code, invite_hash):
                raise HTTPException(status_code=400, detail="invalid_invite_code")
            role = UserRole.ADMIN.value

        from sqlalchemy.exc import IntegrityError

        pwd_hash = hash_password(request.password)
        new_user = UserModel(
            email=email,
            password_hash=pwd_hash,
            role=role,
            is_active=True
        )
        session.add(new_user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="email_already_registered")

        await session.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(request: LoginRequest, session: AsyncSession) -> UserModel:
        email = request.email.strip().lower()
        res = await session.execute(select(UserModel).where(UserModel.email == email))
        user = res.scalar()
        if user is None:
            # Prevent email enumeration by executing verification with identical cost
            verify_password(
                request.password,
                "$argon2id$v=19$m=65536,t=3,p=4$XENGAaVzTsQhMn6bjfXOGw$oax5ZVYYqD1fRVDV7+nxUvCJzoP3nADl+NO9huttT3w"
            )
            raise HTTPException(status_code=400, detail="invalid_credentials")

        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=400, detail="invalid_credentials")

        if not user.is_active:
            raise HTTPException(status_code=400, detail="account_disabled")

        return user

    @staticmethod
    async def create_session(user_id: int, session: AsyncSession) -> str:
        token = generate_session_token()
        token_hash = hash_session_token(token)
        expiry = beijing_now() + timedelta(days=AUTH_SESSION_EXPIRE_DAYS)

        new_session = AuthSessionModel(
            user_id=user_id,
            session_token_hash=token_hash,
            expires_at=expiry
        )
        session.add(new_session)
        await session.commit()
        return token

    @staticmethod
    async def revoke_session(token: str, session: AsyncSession) -> None:
        if not token:
            return
        token_hash = hash_session_token(token)
        res = await session.execute(
            select(AuthSessionModel).where(
                AuthSessionModel.session_token_hash == token_hash,
                AuthSessionModel.revoked_at == None
            )
        )
        db_session = res.scalar()
        if db_session is not None:
            db_session.revoked_at = beijing_now()
            await session.commit()

    @staticmethod
    async def cleanup_expired_sessions(session: AsyncSession) -> int:
        from sqlalchemy import delete
        stmt = delete(AuthSessionModel).where(
            (AuthSessionModel.expires_at <= beijing_now()) | (AuthSessionModel.revoked_at != None)
        )
        res = await session.execute(stmt)
        await session.commit()
        return res.rowcount

