from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.user import TelegramUser


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
) -> TelegramUser:
    """Get existing user or create new one"""

    # Try to get existing user
    result = await session.execute(
        select(TelegramUser).where(TelegramUser.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user
        user = TelegramUser(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    else:
        # Update user info if provided
        updates = {}
        if username is not None and user.username != username:
            updates["username"] = username
        if first_name is not None and user.first_name != first_name:
            updates["first_name"] = first_name
        if last_name is not None and user.last_name != last_name:
            updates["last_name"] = last_name
        if language_code is not None and user.language_code != language_code:
            updates["language_code"] = language_code

        if updates:
            updates["updated_at"] = datetime.utcnow()
            await session.execute(
                update(TelegramUser).where(TelegramUser.id == user_id).values(**updates)
            )
            await session.flush()

            # Refresh user object
            await session.refresh(user)

    return user


async def update_user_activity(session: AsyncSession, user_id: int) -> None:
    """Update user's last activity timestamp"""
    await session.execute(
        update(TelegramUser)
        .where(TelegramUser.id == user_id)
        .values(last_activity=datetime.utcnow())
    )


async def set_user_goals(
    session: AsyncSession,
    user_id: int,
    calories_goal: float | None = None,
    protein_goal: float | None = None,
    fat_goal: float | None = None,
    carbs_goal: float | None = None,
) -> bool:
    """Set user's daily nutrition goals"""

    updates = {}
    if calories_goal is not None:
        updates["daily_calories_goal"] = calories_goal
    if protein_goal is not None:
        updates["daily_protein_goal"] = protein_goal
    if fat_goal is not None:
        updates["daily_fat_goal"] = fat_goal
    if carbs_goal is not None:
        updates["daily_carbs_goal"] = carbs_goal

    if not updates:
        return False

    updates["updated_at"] = datetime.utcnow()

    result = await session.execute(
        update(TelegramUser).where(TelegramUser.id == user_id).values(**updates)
    )

    return result.rowcount > 0


async def get_user_by_id(session: AsyncSession, user_id: int) -> TelegramUser | None:
    """Get user by ID"""
    result = await session.execute(
        select(TelegramUser).where(TelegramUser.id == user_id)
    )
    return result.scalar_one_or_none()


async def deactivate_user(session: AsyncSession, user_id: int) -> bool:
    """Deactivate user"""
    result = await session.execute(
        update(TelegramUser)
        .where(TelegramUser.id == user_id)
        .values(is_active=False, updated_at=datetime.utcnow())
    )
    return result.rowcount > 0


async def update_user_profile(
    session: AsyncSession,
    user_id: int,
    age: int | None = None,
    weight: float | None = None,
    height: int | None = None,
    gender: str | None = None,
    activity_level: str | None = None,
    goal: str | None = None,
) -> bool:
    """Update user's personal profile parameters"""

    updates = {}
    if age is not None:
        updates["age"] = age
    if weight is not None:
        updates["weight"] = weight
    if height is not None:
        updates["height"] = height
    if gender is not None:
        updates["gender"] = gender
    if activity_level is not None:
        updates["activity_level"] = activity_level
    if goal is not None:
        updates["goal"] = goal

    if not updates:
        return False

    updates["updated_at"] = datetime.utcnow()

    result = await session.execute(
        update(TelegramUser).where(TelegramUser.id == user_id).values(**updates)
    )

    return result.rowcount > 0


async def update_user_goals_from_profile(
    session: AsyncSession,
    user_id: int,
    calories_goal: float,
    protein_goal: float,
    fat_goal: float,
    carbs_goal: float,
) -> bool:
    """Update user's calculated nutrition goals based on profile"""

    result = await session.execute(
        update(TelegramUser)
        .where(TelegramUser.id == user_id)
        .values(
            daily_calories_goal=calories_goal,
            daily_protein_goal=protein_goal,
            daily_fat_goal=fat_goal,
            daily_carbs_goal=carbs_goal,
            updated_at=datetime.utcnow(),
        )
    )

    return result.rowcount > 0
