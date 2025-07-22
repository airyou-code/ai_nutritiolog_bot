import logging
import re
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


def extract_numbers_from_text(text: str) -> dict[str, float]:
    """Extract weight/portion numbers from text"""

    # Common patterns for weight/portion
    patterns = {
        "grams": r"(\d+(?:\.\d+)?)\s*(?:г|гр|грам|gram)",
        "kg": r"(\d+(?:\.\d+)?)\s*(?:кг|kg|килогрм)",
        "ml": r"(\d+(?:\.\d+)?)\s*(?:мл|ml|миллилитр)",
        "l": r"(\d+(?:\.\d+)?)\s*(?:л|l|литр)",
        "pieces": r"(\d+(?:\.\d+)?)\s*(?:шт|штук|piece)",
        "portions": r"(\d+(?:\.\d+)?)\s*(?:порц|порция)",
        "spoons": r"(\d+(?:\.\d+)?)\s*(?:ложк|столов|чайн)",
        "cups": r"(\d+(?:\.\d+)?)\s*(?:стакан|чашк|cup)",
    }

    results = {}
    text_lower = text.lower()

    for unit_type, pattern in patterns.items():
        matches = re.findall(pattern, text_lower)
        if matches:
            # Take the first match
            try:
                results[unit_type] = float(matches[0])
            except ValueError:
                continue

    # Also look for standalone numbers that might be weight
    number_pattern = r"\b(\d+(?:\.\d+)?)\b"
    numbers = re.findall(number_pattern, text)

    # If we found numbers but no specific units, assume first number is grams
    if numbers and not results:
        try:
            first_number = float(numbers[0])
            if 10 <= first_number <= 2000:  # Reasonable weight range
                results["grams"] = first_number
        except ValueError:
            pass

    return results


def estimate_portion_weight(food_name: str, portion_info: str | None = None) -> float:
    """Estimate portion weight based on food name and description"""

    food_lower = food_name.lower()

    # Default weights for common foods (in grams)
    food_weights = {
        "яблоко": 150,
        "банан": 120,
        "апельсин": 200,
        "картофель": 100,
        "морковь": 80,
        "огурец": 100,
        "помидор": 150,
        "хлеб": 30,  # slice
        "булочка": 60,
        "яйцо": 60,
        "курица": 150,  # piece
        "говядина": 150,
        "свинина": 150,
        "рыба": 150,
        "рис": 200,  # cooked portion
        "гречка": 200,
        "макароны": 200,
        "салат": 150,
        "суп": 300,
        "борщ": 300,
        "каша": 200,
        "творог": 200,
        "йогурт": 150,
        "молоко": 250,  # glass
        "кефир": 250,
        "сыр": 50,  # slice
        "масло": 10,  # spoon
        "сахар": 15,  # spoon
        "мед": 20,  # spoon
    }

    # Check if any food keywords match
    for food_key, weight in food_weights.items():
        if food_key in food_lower:
            base_weight = weight
            break
    else:
        # Default portion weight
        base_weight = 200

    # Adjust based on portion description
    if portion_info:
        portion_lower = portion_info.lower()

        # Size modifiers
        if any(word in portion_lower for word in ["маленьк", "мал", "small"]):
            base_weight *= 0.7
        elif any(word in portion_lower for word in ["больш", "large", "огромн"]):
            base_weight *= 1.5
        elif any(word in portion_lower for word in ["средн", "medium"]):
            base_weight *= 1.0

        # Extract specific numbers
        numbers = extract_numbers_from_text(portion_info)
        if "grams" in numbers:
            return numbers["grams"]
        elif "kg" in numbers:
            return numbers["kg"] * 1000

    return round(base_weight)


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


def is_food_related_message(text: str) -> bool:
    """Check if message is likely food-related"""

    food_keywords = [
        "еда",
        "пища",
        "блюдо",
        "завтрак",
        "обед",
        "ужин",
        "перекус",
        "калории",
        "белки",
        "жиры",
        "углеводы",
        "бжу",
        "диета",
        "питание",
        "рацион",
        "продукт",
        "готовить",
        "есть",
        "кушать",
        "съел",
        "поел",
    ]

    text_lower = text.lower()

    return any(keyword in text_lower for keyword in food_keywords)
