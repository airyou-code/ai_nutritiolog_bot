from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.food_entry import FoodEntry


async def create_food_entry(
    session: AsyncSession,
    user_id: int,
    food_name: str,
    food_description: str | None,
    portion_size: str | None,
    portion_weight: float | None,
    calories_per_100g: float,
    protein_per_100g: float,
    fat_per_100g: float,
    carbs_per_100g: float,
    total_calories: float,
    total_protein: float,
    total_fat: float,
    total_carbs: float,
    photo_file_id: str | None = None,
    input_method: str = "text",
    ai_analysis: str | None = None,
    entry_date: date | None = None,
) -> FoodEntry:
    """Create new food entry"""

    if entry_date is None:
        entry_date = date.today()

    food_entry = FoodEntry(
        user_id=user_id,
        food_name=food_name,
        food_description=food_description,
        portion_size=portion_size,
        portion_weight=portion_weight,
        calories_per_100g=calories_per_100g,
        protein_per_100g=protein_per_100g,
        fat_per_100g=fat_per_100g,
        carbs_per_100g=carbs_per_100g,
        total_calories=total_calories,
        total_protein=total_protein,
        total_fat=total_fat,
        total_carbs=total_carbs,
        photo_file_id=photo_file_id,
        input_method=input_method,
        ai_analysis=ai_analysis,
        entry_date=entry_date,
    )

    session.add(food_entry)
    await session.flush()
    await session.refresh(food_entry)

    return food_entry


async def get_user_food_entries_by_date(
    session: AsyncSession, user_id: int, entry_date: date | None = None
) -> list[FoodEntry]:
    """Get user's food entries for specific date"""

    if entry_date is None:
        entry_date = date.today()

    result = await session.execute(
        select(FoodEntry)
        .where(and_(FoodEntry.user_id == user_id, FoodEntry.entry_date == entry_date))
        .order_by(FoodEntry.created_at.desc())
    )

    return result.scalars().all()


async def get_user_daily_nutrition_summary(
    session: AsyncSession, user_id: int, entry_date: date | None = None
) -> dict:
    """Get user's daily nutrition summary"""

    if entry_date is None:
        entry_date = date.today()

    result = await session.execute(
        select(
            func.sum(FoodEntry.total_calories).label("total_calories"),
            func.sum(FoodEntry.total_protein).label("total_protein"),
            func.sum(FoodEntry.total_fat).label("total_fat"),
            func.sum(FoodEntry.total_carbs).label("total_carbs"),
            func.count(FoodEntry.id).label("entries_count"),
        ).where(and_(FoodEntry.user_id == user_id, FoodEntry.entry_date == entry_date))
    )

    summary = result.first()

    return {
        "date": entry_date,
        "total_calories": float(summary.total_calories or 0),
        "total_protein": float(summary.total_protein or 0),
        "total_fat": float(summary.total_fat or 0),
        "total_carbs": float(summary.total_carbs or 0),
        "entries_count": summary.entries_count,
    }


async def get_user_food_entries_period(
    session: AsyncSession, user_id: int, start_date: date, end_date: date
) -> list[FoodEntry]:
    """Get user's food entries for a period"""

    result = await session.execute(
        select(FoodEntry)
        .where(
            and_(
                FoodEntry.user_id == user_id,
                FoodEntry.entry_date >= start_date,
                FoodEntry.entry_date <= end_date,
            )
        )
        .order_by(FoodEntry.entry_date.desc(), FoodEntry.created_at.desc())
    )

    return result.scalars().all()


async def delete_food_entry(session: AsyncSession, entry_id: int, user_id: int) -> bool:
    """Delete food entry (only if belongs to user)"""

    result = await session.execute(
        select(FoodEntry).where(
            and_(FoodEntry.id == entry_id, FoodEntry.user_id == user_id)
        )
    )

    entry = result.scalar_one_or_none()
    if entry:
        await session.delete(entry)
        return True

    return False


async def get_food_entry_by_id(
    session: AsyncSession, entry_id: int, user_id: int | None = None
) -> FoodEntry | None:
    """Get food entry by ID, optionally filtered by user"""

    query = select(FoodEntry).where(FoodEntry.id == entry_id)

    if user_id is not None:
        query = query.where(FoodEntry.user_id == user_id)

    result = await session.execute(query)
    return result.scalar_one_or_none()
