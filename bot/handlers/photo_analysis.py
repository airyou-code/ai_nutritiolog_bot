import logging
from typing import Dict, Any
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.inline import (
    get_portion_selection_keyboard, 
    get_nutrition_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from bot.services.nutrition_analyzer import nutrition_analyzer
from bot.services.redis_service import redis_service
from bot.database.connection import get_db_session
from bot.database.operations.food_ops import create_food_entry
from bot.utils.helpers import safe_answer_callback, safe_delete_message
from bot.config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


class PhotoAnalysisStates(StatesGroup):
    waiting_for_photo = State()
    selecting_portion = State()
    confirming_nutrition = State()


# OLD: Deprecated - now handled by universal_food_input.py
@router.callback_query(F.data == "add_food_photo")
async def start_photo_analysis(callback: CallbackQuery, state: FSMContext):
    """Redirect to universal photo input (backward compatibility)"""
    
    await safe_answer_callback(callback)
    
    text = """
📸 **Анализ фотографии еды**

Просто отправь фотографию блюда! Я автоматически проанализирую её.

📝 **Подсказка:** Можешь добавить описание к фото (в подписи)! 
Например: "домашний борщ со сметаной" или "салат без майонеза"

💡 **Советы для лучшего результата:**
• Сфотографируй блюдо целиком
• Обеспечь хорошее освещение  
• Покажи размер порции
• Избегай размытых фото
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.clear()


# OLD: Deprecated - now handled by universal_food_input.py
@router.message(PhotoAnalysisStates.waiting_for_photo, F.photo)
async def handle_food_photo(message: Message, state: FSMContext, bot: Bot, user_id: int):
    """Handle received food photo - DEPRECATED"""
    
    try:
        # Get the largest photo
        photo: PhotoSize = message.photo[-1]
        
        # Check photo size
        if photo.file_size and photo.file_size > settings.max_photo_size:
            await message.answer(
                "❌ Фото слишком большое! Максимальный размер: 20 МБ",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Show processing message
        processing_msg = await message.answer(
            "🔄 Анализирую фотографию...\n\n"
            "⏳ Это может занять несколько секунд"
        )
        
        # Download photo
        file_info = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file_info.file_path)
        image_bytes = photo_data.read()
        
        # Get description from photo caption if provided
        user_description = message.caption.strip() if message.caption else ""
        
        # Analyze photo with optional description
        analysis = await nutrition_analyzer.analyze_food_from_photo(image_bytes, user_description)
        
        # Store analysis data in state
        await state.update_data(
            analysis=analysis,
            photo_file_id=photo.file_id,
            input_method="photo",
            user_description=user_description
        )
        
        # Delete processing message
        await safe_delete_message(bot, message.chat.id, processing_msg.message_id)
        
        # Show analysis result and portion options directly
        await show_portion_selection(message, analysis, state)
        
    except Exception as e:
        logger.error(f"Error analyzing food photo: {e}")
        
        await message.answer(
            "❌ Ошибка при анализе фотографии. Попробуй еще раз с другим фото.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# Обработчик описания удален - теперь используем подпись к фото


@router.callback_query(PhotoAnalysisStates.selecting_portion, F.data.startswith("select_portion:"))
async def handle_portion_selection(callback: CallbackQuery, state: FSMContext):
    """Handle portion selection"""
    
    await safe_answer_callback(callback)
    
    portion_index = int(callback.data.split(":")[1])
    data = await state.get_data()
    analysis = data.get("analysis", {})
    
    if portion_index >= len(analysis.get("portion_options", [])):
        await callback.answer("❌ Неверный выбор порции")
        return
    
    selected_portion = analysis["portion_options"][portion_index]
    
    # Calculate nutrition for selected portion
    nutrition = nutrition_analyzer.calculate_nutrition_for_portion(
        analysis["nutrition_per_100g"],
        selected_portion["weight"]
    )
    
    # Store selected data
    await state.update_data(
        selected_portion=selected_portion,
        nutrition=nutrition
    )
    
    # Show nutrition confirmation
    await show_nutrition_confirmation(callback.message, analysis, selected_portion, nutrition, state)


@router.callback_query(PhotoAnalysisStates.confirming_nutrition, F.data == "confirm_nutrition")
async def confirm_nutrition_entry(callback: CallbackQuery, state: FSMContext, user_id: int):
    """Confirm and save nutrition entry to database"""
    
    await safe_answer_callback(callback, "Сохраняю...")
    
    try:
        data = await state.get_data()
        analysis = data.get("analysis", {})
        selected_portion = data.get("selected_portion", {})
        nutrition = data.get("nutrition", {})
        
        async with get_db_session() as session:
            food_entry = await create_food_entry(
                session=session,
                user_id=user_id,
                food_name=analysis["food_name"],
                food_description=analysis.get("description"),
                portion_size=selected_portion["size"],
                portion_weight=selected_portion["weight"],
                calories_per_100g=analysis["nutrition_per_100g"]["calories"],
                protein_per_100g=analysis["nutrition_per_100g"]["protein"],
                fat_per_100g=analysis["nutrition_per_100g"]["fat"],
                carbs_per_100g=analysis["nutrition_per_100g"]["carbs"],
                total_calories=nutrition["total_calories"],
                total_protein=nutrition["total_protein"],
                total_fat=nutrition["total_fat"],
                total_carbs=nutrition["total_carbs"],
                photo_file_id=data.get("photo_file_id"),
                input_method=data.get("input_method", "photo"),
                ai_analysis=str(analysis)
            )
        
        success_text = f"""
✅ **Блюдо добавлено в дневник!**

🍽 **{food_entry.food_name}**
⚖️ Порция: {selected_portion['description']} ({selected_portion['weight']}г)

{nutrition_analyzer.format_nutrition_summary(nutrition)}

🕐 Время: сейчас
📊 Запись #{food_entry.id}
"""
        
        await callback.message.edit_text(
            success_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error saving food entry: {e}")
        
        await callback.message.edit_text(
            "❌ Ошибка при сохранении записи. Попробуй еще раз.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


@router.callback_query(PhotoAnalysisStates.confirming_nutrition, F.data == "change_portion")
async def change_portion_selection(callback: CallbackQuery, state: FSMContext):
    """Allow user to change portion selection"""
    
    await safe_answer_callback(callback)
    
    data = await state.get_data()
    analysis = data.get("analysis", {})
    
    await show_portion_selection(callback.message, analysis, state, edit=True)


async def show_portion_selection(message: Message, analysis: Dict, state: FSMContext, edit: bool = False):
    """Show portion selection interface"""
    
    # Get state data to check for user description
    data = await state.get_data()
    user_description = data.get('user_description', '')
    
    # Combine AI description with user description if available
    ai_description = analysis.get('description', '')
    
    if user_description and ai_description:
        full_description = f"{ai_description}\n👤 Заметка: {user_description}"
    elif user_description:
        full_description = f"👤 {user_description}"
    elif ai_description:
        full_description = ai_description
    else:
        full_description = "Описание недоступно"
    
    text = f"""
🍽 **{analysis['food_name']}**

📝 _{full_description}_

Выбери размер порции:
"""
    
    # Add portion options with nutrition info
    portion_options_with_nutrition = nutrition_analyzer.create_portion_options_with_nutrition(analysis)
    
    for i, option in enumerate(portion_options_with_nutrition):
        nutrition = option["nutrition"]
        text += f"\n**{option['description']}** ({option['weight']}г):\n"
        text += f"🔥 {nutrition['total_calories']:.0f} ккал, "
        text += f"🥩 {nutrition['total_protein']:.1f}г, "
        text += f"🥑 {nutrition['total_fat']:.1f}г, "
        text += f"🍞 {nutrition['total_carbs']:.1f}г\n"
    
    keyboard = get_portion_selection_keyboard(analysis["portion_options"])
    
    if edit:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    await state.set_state(PhotoAnalysisStates.selecting_portion)


async def show_nutrition_confirmation(
    message: Message, 
    analysis: Dict, 
    selected_portion: Dict, 
    nutrition: Dict, 
    state: FSMContext
):
    """Show nutrition confirmation interface"""
    
    text = f"""
✅ **Подтверждение данных**

🍽 **{analysis['food_name']}**
📏 **Порция:** {selected_portion['description']} ({selected_portion['weight']}г)

**Питательная ценность:**
{nutrition_analyzer.format_nutrition_summary(nutrition)}

📊 **На 100г продукта:**
🔥 {analysis['nutrition_per_100g']['calories']:.0f} ккал
🥩 {analysis['nutrition_per_100g']['protein']:.1f}г белков  
🥑 {analysis['nutrition_per_100g']['fat']:.1f}г жиров
🍞 {analysis['nutrition_per_100g']['carbs']:.1f}г углеводов

Добавить в дневник питания?
"""
    
    await message.edit_text(
        text,
        reply_markup=get_nutrition_confirmation_keyboard(analysis['food_name']),
        parse_mode="Markdown"
    )
    
    await state.set_state(PhotoAnalysisStates.confirming_nutrition)


@router.message(PhotoAnalysisStates.waiting_for_photo, ~F.photo)
async def handle_non_photo_in_photo_state(message: Message):
    """Handle non-photo messages when expecting photo"""
    
    await message.answer(
        "📸 Пожалуйста, отправь фотографию блюда или нажми 'Отменить'",
        reply_markup=get_cancel_keyboard()
    ) 