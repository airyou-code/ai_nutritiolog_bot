import logging
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.profile import (
    get_profile_menu_keyboard,
    get_profile_edit_keyboard, 
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_back_to_profile_keyboard
)
from bot.keyboards.inline import get_settings_keyboard
from bot.database.connection import get_db_session
from bot.database.operations.user_ops import (
    get_user_by_id,
    update_user_profile,
    update_user_goals_from_profile
)
from bot.services.nutrition_calculator import nutrition_calculator
from bot.utils.helpers import safe_answer_callback

logger = logging.getLogger(__name__)

router = Router()


class ProfileStates(StatesGroup):
    waiting_for_age = State()
    waiting_for_weight = State()
    waiting_for_height = State()


@router.callback_query(F.data == "user_profile")
async def show_profile_menu(callback: CallbackQuery, user_id: int):
    """Show user profile menu"""
    
    await safe_answer_callback(callback)
    
    text = """
👤 **Профиль пользователя**

Здесь ты можешь настроить свои параметры для персонального расчета норм питания:

• Возраст, вес, рост
• Пол и уровень активности  
• Цели (похудение, набор массы, поддержание)

На основе этих данных я рассчитаю твои индивидуальные нормы калорий и БЖУ.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_profile_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "show_profile")
async def show_user_profile(callback: CallbackQuery, user_id: int):
    """Show user profile information"""
    
    await safe_answer_callback(callback)
    
    try:
        async with get_db_session() as session:
            user = await get_user_by_id(session, user_id)
            
            if not user:
                await callback.message.edit_text(
                    "❌ Пользователь не найден",
                    reply_markup=get_back_to_profile_keyboard()
                )
                return
            
            profile_text = nutrition_calculator.format_user_profile(user)
            
            await callback.message.edit_text(
                profile_text,
                reply_markup=get_back_to_profile_keyboard(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error showing user profile: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке профиля",
            reply_markup=get_back_to_profile_keyboard()
        )


@router.callback_query(F.data == "edit_profile")
async def show_profile_edit_menu(callback: CallbackQuery):
    """Show profile editing menu"""
    
    await safe_answer_callback(callback)
    
    text = """
✏️ **Редактирование профиля**

Выбери параметр для изменения:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_profile_edit_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "edit_age")
async def edit_age(callback: CallbackQuery, state: FSMContext):
    """Start editing age"""
    
    await safe_answer_callback(callback)
    
    text = """
🎂 **Укажи свой возраст**

Введи число от 15 до 80 лет:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_profile_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(ProfileStates.waiting_for_age)


@router.message(ProfileStates.waiting_for_age, F.text)
async def handle_age_input(message: Message, state: FSMContext, user_id: int):
    """Handle age input"""
    
    try:
        age = int(message.text.strip())
        
        if not (15 <= age <= 80):
            await message.answer(
                "❌ Возраст должен быть от 15 до 80 лет. Попробуй еще раз:",
                reply_markup=get_back_to_profile_keyboard()
            )
            return
        
        # Update database
        async with get_db_session() as session:
            await update_user_profile(session, user_id, age=age)
        
        await message.answer(
            f"✅ Возраст обновлен: {age} лет",
            reply_markup=get_profile_edit_keyboard()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введи корректное число (возраст в годах):",
            reply_markup=get_back_to_profile_keyboard()
        )


@router.callback_query(F.data == "edit_weight")
async def edit_weight(callback: CallbackQuery, state: FSMContext):
    """Start editing weight"""
    
    await safe_answer_callback(callback)
    
    text = """
⚖️ **Укажи свой вес**

Введи вес в килограммах (например: 70.5):
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_profile_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(ProfileStates.waiting_for_weight)


@router.message(ProfileStates.waiting_for_weight, F.text)
async def handle_weight_input(message: Message, state: FSMContext, user_id: int):
    """Handle weight input"""
    
    try:
        weight = float(message.text.strip().replace(",", "."))
        
        if not (30 <= weight <= 300):
            await message.answer(
                "❌ Вес должен быть от 30 до 300 кг. Попробуй еще раз:",
                reply_markup=get_back_to_profile_keyboard()
            )
            return
        
        # Update database
        async with get_db_session() as session:
            await update_user_profile(session, user_id, weight=weight)
        
        await message.answer(
            f"✅ Вес обновлен: {weight} кг",
            reply_markup=get_profile_edit_keyboard()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введи корректное число (вес в килограммах):",
            reply_markup=get_back_to_profile_keyboard()
        )


@router.callback_query(F.data == "edit_height")
async def edit_height(callback: CallbackQuery, state: FSMContext):
    """Start editing height"""
    
    await safe_answer_callback(callback)
    
    text = """
📏 **Укажи свой рост**

Введи рост в сантиметрах (например: 175):
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_profile_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(ProfileStates.waiting_for_height)


@router.message(ProfileStates.waiting_for_height, F.text)
async def handle_height_input(message: Message, state: FSMContext, user_id: int):
    """Handle height input"""
    
    try:
        height = int(message.text.strip())
        
        if not (140 <= height <= 220):
            await message.answer(
                "❌ Рост должен быть от 140 до 220 см. Попробуй еще раз:",
                reply_markup=get_back_to_profile_keyboard()
            )
            return
        
        # Update database
        async with get_db_session() as session:
            await update_user_profile(session, user_id, height=height)
        
        await message.answer(
            f"✅ Рост обновлен: {height} см",
            reply_markup=get_profile_edit_keyboard()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введи корректное число (рост в сантиметрах):",
            reply_markup=get_back_to_profile_keyboard()
        )


@router.callback_query(F.data == "edit_gender")
async def edit_gender(callback: CallbackQuery):
    """Show gender selection"""
    
    await safe_answer_callback(callback)
    
    text = """
⚧️ **Выбери свой пол**

Это важно для точного расчета калорий:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_gender_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("gender_"))
async def handle_gender_selection(callback: CallbackQuery, user_id: int):
    """Handle gender selection"""
    
    await safe_answer_callback(callback)
    
    gender = callback.data.split("_")[1]  # male or female
    gender_text = "Мужской" if gender == "male" else "Женский"
    
    try:
        async with get_db_session() as session:
            await update_user_profile(session, user_id, gender=gender)
        
        await callback.message.edit_text(
            f"✅ Пол обновлен: {gender_text}",
            reply_markup=get_profile_edit_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error updating gender: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при обновлении пола",
            reply_markup=get_profile_edit_keyboard()
        )


@router.callback_query(F.data == "edit_activity")
async def edit_activity(callback: CallbackQuery):
    """Show activity level selection"""
    
    await safe_answer_callback(callback)
    
    text = """
🏃‍♂️ **Выбери уровень активности**

Как часто ты занимаешься спортом или физической активностью?
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_activity_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("activity_"))
async def handle_activity_selection(callback: CallbackQuery, user_id: int):
    """Handle activity level selection"""
    
    await safe_answer_callback(callback)
    
    activity_level = callback.data.replace("activity_", "")
    activity_levels = nutrition_calculator.get_activity_levels()
    activity_text = activity_levels.get(activity_level, activity_level)
    
    try:
        async with get_db_session() as session:
            await update_user_profile(session, user_id, activity_level=activity_level)
        
        await callback.message.edit_text(
            f"✅ Уровень активности обновлен:\n{activity_text}",
            reply_markup=get_profile_edit_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error updating activity level: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при обновлении уровня активности",
            reply_markup=get_profile_edit_keyboard()
        )


@router.callback_query(F.data == "edit_goal")
async def edit_goal(callback: CallbackQuery):
    """Show goal selection"""
    
    await safe_answer_callback(callback)
    
    text = """
🎯 **Выбери свою цель**

Что ты хочешь достичь с помощью питания?
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_goal_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("goal_"))
async def handle_goal_selection(callback: CallbackQuery, user_id: int):
    """Handle goal selection"""
    
    await safe_answer_callback(callback)
    
    goal = callback.data.replace("goal_", "")
    goals = nutrition_calculator.get_goals()
    goal_text = goals.get(goal, goal)
    
    try:
        async with get_db_session() as session:
            await update_user_profile(session, user_id, goal=goal)
        
        await callback.message.edit_text(
            f"✅ Цель обновлена:\n{goal_text}",
            reply_markup=get_profile_edit_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error updating goal: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при обновлении цели",
            reply_markup=get_profile_edit_keyboard()
        )


@router.callback_query(F.data == "recalculate_norms")
async def recalculate_norms(callback: CallbackQuery, user_id: int):
    """Recalculate nutrition norms based on profile"""
    
    await safe_answer_callback(callback)
    
    try:
        async with get_db_session() as session:
            user = await get_user_by_id(session, user_id)
            
            if not user:
                await callback.message.edit_text(
                    "❌ Пользователь не найден",
                    reply_markup=get_back_to_profile_keyboard()
                )
                return
            
            if not user.has_complete_profile:
                await callback.message.edit_text(
                    "❌ **Профиль не заполнен полностью**\n\n"
                    "Для расчета норм нужно указать все параметры:\n"
                    "• Возраст\n"
                    "• Вес\n"
                    "• Рост\n"
                    "• Пол\n"
                    "• Уровень активности\n"
                    "• Цель",
                    reply_markup=get_profile_edit_keyboard(),
                    parse_mode="Markdown"
                )
                return
            
            # Calculate macros
            macros = nutrition_calculator.calculate_macros(user)
            
            if not macros:
                await callback.message.edit_text(
                    "❌ Не удалось рассчитать нормы питания",
                    reply_markup=get_back_to_profile_keyboard()
                )
                return
            
            # Update user goals in database
            await update_user_goals_from_profile(
                session,
                user_id,
                macros["calories"],
                macros["protein"],
                macros["fat"],
                macros["carbs"]
            )
            
            # Show results
            text = f"""
✅ **Нормы питания пересчитаны!**

🔥 **Калории:** {macros['calories']:.0f} ккал
🥩 **Белки:** {macros['protein']:.1f}г ({macros['protein_percent']:.1f}%)
🥑 **Жиры:** {macros['fat']:.1f}г ({macros['fat_percent']:.1f}%)
🍞 **Углеводы:** {macros['carbs']:.1f}г ({macros['carbs_percent']:.1f}%)

Эти значения сохранены как твои новые дневные цели!
"""
            
            await callback.message.edit_text(
                text,
                reply_markup=get_back_to_profile_keyboard(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error recalculating norms: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при пересчете норм питания",
            reply_markup=get_back_to_profile_keyboard()
        )


@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Cancel editing and return to profile edit menu"""
    
    await safe_answer_callback(callback)
    await state.clear()
    
    await callback.message.edit_text(
        "❌ Редактирование отменено",
        reply_markup=get_profile_edit_keyboard()
    )


@router.callback_query(F.data == "settings")
async def back_to_settings(callback: CallbackQuery, state: FSMContext):
    """Return to settings menu"""
    
    await safe_answer_callback(callback)
    await state.clear()
    
    text = """
⚙️ **Настройки**

Здесь ты можешь настроить бота под себя:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_settings_keyboard(),
        parse_mode="Markdown"
    ) 