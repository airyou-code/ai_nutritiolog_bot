import logging
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Safely delete message, handle errors gracefully"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        logger.debug(f"Failed to delete message {message_id}: {e}")
        return False


async def safe_edit_message(
    message: Message, text: str, reply_markup=None, parse_mode: str | None = None
) -> bool:
    """Safely edit message, handle errors gracefully"""
    try:
        await message.edit_text(
            text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.debug(f"Failed to edit message: {e}")
        return False


async def safe_answer_callback(callback: CallbackQuery, text: str = "✅") -> bool:
    """Safely answer callback query"""
    try:
        await callback.answer(text)
        return True
    except Exception as e:
        logger.debug(f"Failed to answer callback: {e}")
        return False


async def safe_edit_callback_message(
    callback: CallbackQuery, text: str, reply_markup=None, parse_mode: str | None = None
) -> bool:
    """Safely edit callback message, handle 'message not modified' errors"""
    try:
        await callback.message.edit_text(
            text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return True
    except Exception as e:
        if "message is not modified" in str(e).lower():
            # Message content is the same - just answer callback without error
            logger.debug(f"Message not modified, skipping edit: {e}")
            return True
        else:
            logger.error(f"Failed to edit callback message: {e}")
            return False


def format_datetime(dt: datetime) -> str:
    """Format datetime for display"""
    now = datetime.now()

    if dt.date() == now.date():
        return f"сегодня в {dt.strftime('%H:%M')}"
    elif dt.date() == (now - timedelta(days=1)).date():
        return f"вчера в {dt.strftime('%H:%M')}"
    elif (now - dt).days < 7:
        days_ago = (now - dt).days
        return f"{days_ago} дн. назад в {dt.strftime('%H:%M')}"
    else:
        return dt.strftime("%d.%m.%Y %H:%M")


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def validate_nutrition_values(nutrition: dict[str, float]) -> dict[str, float]:
    """Validate and sanitize nutrition values"""

    validated = {}

    # Define reasonable ranges
    ranges = {
        "calories": (0, 2000),  # per portion
        "protein": (0, 200),  # per portion
        "fat": (0, 200),  # per portion
        "carbs": (0, 300),  # per portion
        "calories_per_100g": (0, 900),
        "protein_per_100g": (0, 100),
        "fat_per_100g": (0, 100),
        "carbs_per_100g": (0, 100),
    }

    for key, value in nutrition.items():
        if key in ranges:
            min_val, max_val = ranges[key]
            validated[key] = max(min_val, min(value, max_val))
        else:
            validated[key] = value

    return validated


def generate_food_entry_summary(entry: Any) -> str:
    """Generate summary text for food entry"""

    summary = f"🍽 **{entry.food_name}**\n"

    if entry.food_description:
        desc = truncate_text(entry.food_description, 80)
        summary += f"📝 _{desc}_\n"

    summary += f"\n{entry.nutrition_summary}\n"

    if entry.portion_weight:
        summary += f"⚖️ Вес: {entry.portion_weight}г\n"
    elif entry.portion_size:
        summary += f"📏 Порция: {entry.portion_size}\n"

    summary += f"🕐 {format_datetime(entry.created_at)}"

    return summary
