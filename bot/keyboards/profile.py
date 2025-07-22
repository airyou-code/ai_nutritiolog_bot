from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_profile_menu_keyboard() -> InlineKeyboardMarkup:
    """Get user profile menu keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👤 Показать профиль", callback_data="show_profile")
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Заполнить/изменить профиль", callback_data="edit_profile"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Пересчитать нормы", callback_data="recalculate_norms"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="settings")
    )

    return builder.as_markup()


def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Get profile editing keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age"),
        InlineKeyboardButton(text="⚖️ Вес", callback_data="edit_weight"),
    )
    builder.row(
        InlineKeyboardButton(text="📏 Рост", callback_data="edit_height"),
        InlineKeyboardButton(text="⚧️ Пол", callback_data="edit_gender"),
    )
    builder.row(
        InlineKeyboardButton(text="🏃‍♂️ Активность", callback_data="edit_activity"),
        InlineKeyboardButton(text="🎯 Цель", callback_data="edit_goal"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="user_profile"))

    return builder.as_markup()


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Get gender selection keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
        InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_edit"))

    return builder.as_markup()


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Get activity level selection keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🛋 Малоподвижный", callback_data="activity_sedentary")
    )
    builder.row(
        InlineKeyboardButton(
            text="🚶 Легкая активность", callback_data="activity_lightly_active"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏃 Умеренная активность", callback_data="activity_moderately_active"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💪 Высокая активность", callback_data="activity_very_active"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔥 Экстремальная активность",
            callback_data="activity_extremely_active",
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_edit"))

    return builder.as_markup()


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Get goal selection keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🎯 Похудение", callback_data="goal_weight_loss")
    )
    builder.row(
        InlineKeyboardButton(
            text="⚖️ Поддержание веса", callback_data="goal_maintain_weight"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💪 Набор мышечной массы", callback_data="goal_weight_gain"
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_edit"))

    return builder.as_markup()


def get_back_to_profile_keyboard() -> InlineKeyboardMarkup:
    """Get back to profile keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="◀️ Назад к профилю", callback_data="user_profile")
    )

    return builder.as_markup()
