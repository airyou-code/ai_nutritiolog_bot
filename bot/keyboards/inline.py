from typing import List, Dict, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Мой дневник питания",
            callback_data="view_diary"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Спросить о питании",
            callback_data="nutrition_chat"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings"
        )
    )
    
    return builder.as_markup()


def get_portion_selection_keyboard(portion_options: List[Dict]) -> InlineKeyboardMarkup:
    """Get portion selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    for i, option in enumerate(portion_options):
        text = f"{option['description']} ({option['weight']}г)"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"select_portion:{i}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_nutrition_confirmation_keyboard(food_name: str) -> InlineKeyboardMarkup:
    """Get nutrition confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Добавить в дневник",
            callback_data="confirm_nutrition"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 Изменить порцию",
            callback_data="change_portion"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_diary_keyboard() -> InlineKeyboardMarkup:
    """Get diary view keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📅 Сегодня",
            callback_data="diary_today"
        ),
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="diary_stats"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗓 Выбрать дату",
            callback_data="diary_date"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()


def get_food_entry_actions_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    """Get actions keyboard for specific food entry"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete_entry:{entry_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="diary_today"
        )
    )
    
    return builder.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="👤 Мой профиль",
            callback_data="user_profile"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎯 Цели по БЖУ",
            callback_data="set_goals"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Моя статистика",
            callback_data="my_stats"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="ℹ️ О боте",
            callback_data="about"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Get back to menu keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Get cancel operation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_yes_no_keyboard(yes_callback: str, no_callback: str = "cancel") -> InlineKeyboardMarkup:
    """Get yes/no confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Да",
            callback_data=yes_callback
        ),
        InlineKeyboardButton(
            text="❌ Нет", 
            callback_data=no_callback
        )
    )
    
    return builder.as_markup()


def get_chat_actions_keyboard() -> InlineKeyboardMarkup:
    """Get chat actions keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Мой рацион сегодня",
            callback_data="chat_my_nutrition"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💡 Советы по питанию",
            callback_data="chat_nutrition_tips"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )
    
    return builder.as_markup()


def get_text_input_mode_keyboard() -> InlineKeyboardMarkup:
    """Get text input mode selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🍽 Просто название блюда",
            callback_data="text_mode_simple"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📏 С указанием веса/порции",
            callback_data="text_mode_detailed"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup() 