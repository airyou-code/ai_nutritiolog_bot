from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.database.connection import Base

if TYPE_CHECKING:
    from bot.database.models.food_entry import FoodEntry


class TelegramUser(Base):
    """Telegram user model"""

    __tablename__ = "telegram_users"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user ID

    # User information
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # User settings and preferences
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_calories_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_protein_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_fat_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_carbs_goal: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Personal parameters for nutrition calculation
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)  # in kg
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in cm
    gender: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # 'male' or 'female'
    activity_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # sedentary, lightly_active, etc.
    goal: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # weight_loss, weight_gain, maintain_weight

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    food_entries: Mapped[list["FoodEntry"]] = relationship(
        "FoodEntry", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TelegramUser(id={self.id}, username={self.username})>"

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else self.username or f"User {self.id}"

    @property
    def has_complete_profile(self) -> bool:
        """Check if user has all required parameters for nutrition calculation"""
        return all(
            [
                self.age is not None,
                self.weight is not None,
                self.height is not None,
                self.gender is not None,
                self.activity_level is not None,
                self.goal is not None,
            ]
        )

    @property
    def bmi(self) -> float | None:
        """Calculate BMI (Body Mass Index)"""
        if self.weight and self.height:
            return round(self.weight / ((self.height / 100) ** 2), 1)
        return None
