import logging
from typing import Dict, Any

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.inline import (
    get_text_input_mode_keyboard,
    get_portion_selection_keyboard,
    get_nutrition_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from bot.services.nutrition_analyzer import nutrition_analyzer
from bot.database.connection import get_db_session
from bot.database.operations.food_ops import create_food_entry
from bot.utils.helpers import safe_answer_callback, extract_numbers_from_text, estimate_portion_weight

logger = logging.getLogger(__name__)

router = Router()


class TextInputStates(StatesGroup):
    selecting_mode = State()
    waiting_for_simple_text = State()
    waiting_for_detailed_text = State()
    selecting_portion = State()
    confirming_nutrition = State()


@router.callback_query(F.data == "add_food_text")
async def start_text_input(callback: CallbackQuery, state: FSMContext):
    """Start text input process"""
    
    await safe_answer_callback(callback)
    
    text = """
✍️ **Добавление блюда текстом**

Выбери способ ввода:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_text_input_mode_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(TextInputStates.selecting_mode)


@router.callback_query(TextInputStates.selecting_mode, F.data == "text_mode_simple")
async def start_simple_text_input(callback: CallbackQuery, state: FSMContext):
    """Start simple text input mode"""
    
    await safe_answer_callback(callback)
    
    text = """
🍽 **Простой ввод блюда**

Напиши название блюда, которое ты съел.

📝 **Примеры:**
• Гречка с курицей
• Салат цезарь
• Борщ с мясом
• Яблоко
• Творог с медом

ИИ сам определит приблизительный размер порции и рассчитает БЖУ.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(TextInputStates.waiting_for_simple_text)


@router.callback_query(TextInputStates.selecting_mode, F.data == "text_mode_detailed")
async def start_detailed_text_input(callback: CallbackQuery, state: FSMContext):
    """Start detailed text input mode"""
    
    await safe_answer_callback(callback)
    
    text = """
📏 **Детальный ввод блюда**

Напиши название блюда и укажи вес или размер порции.

📝 **Примеры:**
• Гречка с курицей 300г
• Салат цезарь большая порция
• Борщ 2 половника
• Яблоко среднее
• Творог 200г с медом 1 ложка

Чем подробнее опишешь, тем точнее будет расчет БЖУ!
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(TextInputStates.waiting_for_detailed_text)


@router.message(TextInputStates.waiting_for_simple_text, F.text)
async def handle_simple_text_input(message: Message, state: FSMContext, user_id: int):
    """Handle simple text input"""
    
    food_description = message.text.strip()
    
    if len(food_description) < 2:
        await message.answer(
            "❌ Слишком короткое описание. Попробуй еще раз:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await process_text_input(message, state, food_description, None)


@router.message(TextInputStates.waiting_for_detailed_text, F.text)
async def handle_detailed_text_input(message: Message, state: FSMContext, user_id: int):
    """Handle detailed text input"""
    
    food_description = message.text.strip()
    
    if len(food_description) < 2:
        await message.answer(
            "❌ Слишком короткое описание. Попробуй еще раз:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Extract portion information from text
    numbers = extract_numbers_from_text(food_description)
    portion_info = None
    
    if numbers:
        # Build portion info string
        portions = []
        for unit, value in numbers.items():
            if unit == 'grams':
                portions.append(f"{value}г")
            elif unit == 'kg':
                portions.append(f"{value}кг")
            elif unit == 'pieces':
                portions.append(f"{value} штук")
            # Add more unit mappings as needed
        
        if portions:
            portion_info = ", ".join(portions)
    
    await process_text_input(message, state, food_description, portion_info)


async def process_text_input(message: Message, state: FSMContext, food_description: str, portion_info: str):
    """Process text input and analyze food"""
    
    try:
        # Show processing message
        processing_msg = await message.answer(
            "🔄 Анализирую описание блюда...\n\n"
            "⏳ Это может занять несколько секунд"
        )
        
        # Analyze food from text
        analysis = await nutrition_analyzer.analyze_food_from_text(food_description, portion_info)
        
        # Store analysis data
        await state.update_data(
            analysis=analysis,
            input_method="text",
            original_description=food_description
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Show portion selection
        await show_text_portion_selection(message, analysis, state)
        
    except Exception as e:
        logger.error(f"Error analyzing text input: {e}")
        
        await message.answer(
            "❌ Ошибка при анализе описания. Попробуй переформулировать или выбери другой способ ввода.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


async def show_text_portion_selection(message: Message, analysis: Dict, state: FSMContext):
    """Show portion selection for text input"""
    
    text = f"""
🍽 **{analysis['food_name']}**

📝 _{analysis.get('description', 'Описание недоступно')}_

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
    
    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await state.set_state(TextInputStates.selecting_portion)


# Reuse portion selection and confirmation handlers from photo_analysis
# by importing and registering them with this router

from bot.handlers.photo_analysis import (
    handle_portion_selection as photo_handle_portion_selection,
    confirm_nutrition_entry as photo_confirm_nutrition_entry,
    change_portion_selection as photo_change_portion_selection,
    show_nutrition_confirmation
)


@router.callback_query(TextInputStates.selecting_portion, F.data.startswith("select_portion:"))
async def handle_text_portion_selection(callback: CallbackQuery, state: FSMContext):
    """Handle portion selection for text input"""
    
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
    await state.set_state(TextInputStates.confirming_nutrition)


@router.callback_query(TextInputStates.confirming_nutrition, F.data == "confirm_nutrition")
async def confirm_text_nutrition_entry(callback: CallbackQuery, state: FSMContext, user_id: int):
    """Confirm and save nutrition entry from text input"""
    
    await safe_answer_callback(callback, "Сохраняю...")
    
    try:
        data = await state.get_data()
        analysis = data.get("analysis", {})
        selected_portion = data.get("selected_portion", {})
        nutrition = data.get("nutrition", {})
        original_description = data.get("original_description", "")
        
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
                input_method="text",
                ai_analysis=f"Original: {original_description}\nAnalysis: {str(analysis)}"
            )
        
        success_text = f"""
✅ **Блюдо добавлено в дневник!**

🍽 **{food_entry.food_name}**
⚖️ Порция: {selected_portion['description']} ({selected_portion['weight']}г)

{nutrition_analyzer.format_nutrition_summary(nutrition)}

📝 Исходное описание: _{original_description}_
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
        logger.error(f"Error saving text food entry: {e}")
        
        await callback.message.edit_text(
            "❌ Ошибка при сохранении записи. Попробуй еще раз.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


@router.callback_query(TextInputStates.confirming_nutrition, F.data == "change_portion")
async def change_text_portion_selection(callback: CallbackQuery, state: FSMContext):
    """Allow user to change portion selection for text input"""
    
    await safe_answer_callback(callback)
    
    data = await state.get_data()
    analysis = data.get("analysis", {})
    
    # Show portion selection again
    text = f"""
🍽 **{analysis['food_name']}**

📝 _{analysis.get('description', 'Описание недоступно')}_

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
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await state.set_state(TextInputStates.selecting_portion) 