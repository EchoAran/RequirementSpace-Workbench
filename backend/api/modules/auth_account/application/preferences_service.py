from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.locale import is_valid_locale
from backend.database.model import UserModel


class UserPreferencesService:
    async def update_locale(
        self,
        user: UserModel,
        preferred_locale: str,
        session: AsyncSession,
    ) -> str:
        if not is_valid_locale(preferred_locale):
            raise ValueError("invalid_preferred_locale")
        user.preferred_locale = preferred_locale
        session.add(user)
        await session.flush()
        return preferred_locale
