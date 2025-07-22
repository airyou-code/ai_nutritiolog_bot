from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.database.connection import Base

if TYPE_CHECKING:
    from bot.database.models.user import TelegramUser


class FoodEntry(Base):
    """Food entry model for tracking nutrition"""

    __tablename__ = "food_entries"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False
    )

    # Food information
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    food_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    portion_size: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g., "medium", "large", "small"
    portion_weight: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # in grams

    # Nutrition information (per 100g)
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)

    # Total nutrition (for actual portion)
    total_calories: Mapped[float] = mapped_column(Float, nullable=False)
    total_protein: Mapped[float] = mapped_column(Float, nullable=False)
    total_fat: Mapped[float] = mapped_column(Float, nullable=False)
    total_carbs: Mapped[float] = mapped_column(Float, nullable=False)

    # Metadata
    photo_file_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Telegram photo file ID
    input_method: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "photo" or "text"
    ai_analysis: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # AI analysis result

    # Timestamps
    entry_date: Mapped[date] = mapped_column(
        Date, nullable=False, default=func.current_date()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["TelegramUser"] = relationship(
        "TelegramUser", back_populates="food_entries"
    )

    def __repr__(self) -> str:
        return f"<FoodEntry(id={self.id}, food_name={self.food_name}, user_id={self.user_id})>"

    @property
    def nutrition_summary(self) -> str:
        """Get nutrition summary as string"""
        return (
            f"Калории: {self.total_calories:.1f} ккал\n"
            f"Белки: {self.total_protein:.1f} г\n"
            f"Жиры: {self.total_fat:.1f} г\n"
            f"Углеводы: {self.total_carbs:.1f} г"
        )
