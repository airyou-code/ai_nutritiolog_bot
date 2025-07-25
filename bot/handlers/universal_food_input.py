import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, PhotoSize

from bot.config.settings import settings
from bot.database.connection import get_db_session
from bot.database.operations.food_ops import create_food_entry
from bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_nutrition_confirmation_keyboard,
    get_portion_selection_keyboard,
)
from bot.services.food_input_agent import food_input_agent
from bot.services.nutrition_analyzer import nutrition_analyzer
from bot.utils.helpers import safe_answer_callback

logger = logging.getLogger(__name__)

router = Router()


class UniversalFoodStates(StatesGroup):
    selecting_portion = State()
    confirming_nutrition = State()
    awaiting_clarification = State()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_universal_text_input(
    message: Message, state: FSMContext, user_id: int
):
    """Universal handler for any text input - checks if it's food related"""

    # Skip if user is in specific states that should handle text differently
    current_state = await state.get_state()
    if current_state and current_state in [
        "ChatStates:waiting_for_question",
        "ProfileStates:waiting_for_name",
        "ProfileStates:waiting_for_age",
        "ProfileStates:waiting_for_weight",
        "ProfileStates:waiting_for_height",
        # Add other states that need text input
    ]:
        return

    user_input = message.text.strip()

    if len(user_input) < 2:
        return

    try:
        # Show processing message
        processing_msg = await message.answer(
            "🔄 Анализирую описание блюда...\n\n⏳ Это может занять несколько секунд"
        )

        # Analyze user input with smart agent
        input_analysis = await food_input_agent.analyze_user_input(user_input)

        if not input_analysis["is_food_related"]:
            # Not food related - suggest what user can do
            try:
                await processing_msg.edit_text(
                    "🤔 Я не понял, что это за блюдо.\n\n"
                    "💡 **Что я умею:**\n"
                    "📸 Анализировать фото еды\n"
                    "📝 Записывать описания блюд\n"
                    "💬 Отвечать на вопросы о питании\n\n"
                    "Попробуй описать блюдо конкретнее или воспользуйся меню!",
                    reply_markup=get_main_menu_keyboard(),
                )
            except Exception:
                await message.answer(
                    "🤔 Я не понял, что это за блюдо.\n\n"
                    "💡 **Что я умею:**\n"
                    "📸 Анализировать фото еды\n"
                    "📝 Записывать описания блюд\n"
                    "💬 Отвечать на вопросы о питании\n\n"
                    "Попробуй описать блюдо конкретнее или воспользуйся меню!",
                    reply_markup=get_main_menu_keyboard(),
                )
            return

        # Process food input
        food_analysis = await food_input_agent.process_food_input(input_analysis)

        if food_analysis.get("not_food"):
            not_food_message = f"""
🤔 **Это не похоже на еду!**

{food_analysis.get("message", "Я не смог определить блюдо в твоем сообщении.")}

💡 **Попробуй написать конкретнее:**
• "2 банана"
• "тарелка супа"
• "кусочек хлеба"
• "стакан молока"

Или отправь фото блюда! 📸
"""
            try:
                await processing_msg.edit_text(
                    not_food_message,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                await message.answer(
                    not_food_message,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="Markdown",
                )
            return

        if food_analysis.get("needs_clarification"):
            try:
                await processing_msg.edit_text(
                    food_analysis["clarification_message"], parse_mode="Markdown"
                )
            except Exception:
                await message.answer(
                    food_analysis["clarification_message"], parse_mode="Markdown"
                )
            await state.set_state(UniversalFoodStates.awaiting_clarification)
            return

        # Store analysis and show portion selection
        await state.update_data(
            analysis=food_analysis,
            input_method="text_universal",
            original_input=user_input,
            input_analysis=input_analysis,
        )

        await show_portion_selection(message, food_analysis, state, processing_msg)

    except Exception as e:
        logger.error(f"Error in universal food input: {e}")
        try:
            await processing_msg.edit_text(
                "❌ Произошла ошибка при анализе. Попробуй еще раз или воспользуйся фото.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception:
            await message.answer(
                "❌ Произошла ошибка при анализе. Попробуй еще раз или воспользуйся фото.",
                reply_markup=get_main_menu_keyboard(),
            )


@router.message(F.photo & ~F.text.startswith("/"))
async def handle_universal_photo_input(
    message: Message, state: FSMContext, bot: Bot, user_id: int
):
    """Universal handler for photo input - analyzes food photos"""

    # Skip if user is in specific states that should handle photos differently
    current_state = await state.get_state()
    if (
        current_state
        and current_state
        in [
            # Add other states that might need different photo handling
        ]
    ):
        return

    try:
        # Get the largest photo
        photo: PhotoSize = message.photo[-1]

        # Check photo size
        if photo.file_size and photo.file_size > settings.max_photo_size:
            await message.answer(
                "❌ Фото слишком большое! Максимальный размер: 20 МБ",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        # Show processing message
        processing_msg = await message.answer(
            "🔄 Анализирую фотографию еды...\n\n⏳ Это может занять несколько секунд"
        )

        # Download photo
        file_info = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file_info.file_path)
        image_bytes = photo_data.read()

        # Get description from photo caption if provided
        user_description = message.caption.strip() if message.caption else ""

        # Analyze photo
        food_analysis = await nutrition_analyzer.analyze_food_from_photo(
            image_bytes, user_description
        )

        # Check if AI determined this is not food
        if not food_analysis.get("is_food"):
            not_food_message = f"""
🤔 **На фото не видно еды!**

{food_analysis.get("description", "Я не смог найти блюда на этом изображении.")}

💡 **Попробуй:**
• Сфотографировать блюдо крупнее
• Убедиться что на фото видна еда
• Или написать описание блюда текстом

Примеры: "2 банана", "тарелка супа", "кусочек торта"
"""
            try:
                await processing_msg.edit_text(
                    not_food_message,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                await message.answer(
                    not_food_message,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="Markdown",
                )
            return

        # Store analysis data in state
        await state.update_data(
            analysis=food_analysis,
            input_method="photo_universal",
            original_input=f"📸 Фото{f' с описанием: {user_description}' if user_description else ''}",
            photo_file_id=photo.file_id,
            user_description=user_description,
        )

        # Show portion selection using the same logic as text
        await show_portion_selection(message, food_analysis, state, processing_msg)

    except Exception as e:
        logger.error(f"Error in universal photo input: {e}")
        try:
            await processing_msg.edit_text(
                "❌ Ошибка при анализе фотографии. Попробуй еще раз с другим фото.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception:
            await message.answer(
                "❌ Ошибка при анализе фотографии. Попробуй еще раз с другим фото.",
                reply_markup=get_main_menu_keyboard(),
            )


@router.message(UniversalFoodStates.awaiting_clarification, F.text)
async def handle_clarification_input(message: Message, state: FSMContext, user_id: int):
    """Handle clarification input after unclear food description"""

    user_input = message.text.strip()

    if len(user_input) < 2:
        await message.answer("Попробуй описать подробнее...")
        return

    try:
        # Show processing message
        processing_msg = await message.answer(
            "🔄 Анализирую уточненное описание...\n\n"
            "⏳ Это может занять несколько секунд"
        )

        # Re-analyze with clarification
        input_analysis = await food_input_agent.analyze_user_input(user_input)

        if (
            not input_analysis["is_food_related"]
            or input_analysis["analysis_type"] == "need_clarification"
        ):
            try:
                await processing_msg.edit_text(
                    "🤔 Все еще не очень понятно. Попробуй описать конкретнее:\n\n"
                    "**Хорошие примеры:**\n"
                    "• 2 банана\n"
                    "• тарелка борща\n"
                    "• кусочек хлеба\n"
                    "• 200г курицы\n"
                    "• стакан молока"
                )
            except Exception:
                await message.answer(
                    "🤔 Все еще не очень понятно. Попробуй описать конкретнее:\n\n"
                    "**Хорошие примеры:**\n"
                    "• 2 банана\n"
                    "• тарелка борща\n"
                    "• кусочек хлеба\n"
                    "• 200г курицы\n"
                    "• стакан молока"
                )
            return

        # Process food input
        food_analysis = await food_input_agent.process_food_input(input_analysis)

        # Store analysis and show portion selection
        await state.update_data(
            analysis=food_analysis,
            input_method="text_universal",
            original_input=user_input,
            input_analysis=input_analysis,
        )

        await show_portion_selection(message, food_analysis, state, processing_msg)

    except Exception as e:
        logger.error(f"Error in clarification input: {e}")
        try:
            await processing_msg.edit_text(
                "❌ Произошла ошибка. Попробуй еще раз.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception:
            await message.answer(
                "❌ Произошла ошибка. Попробуй еще раз.",
                reply_markup=get_main_menu_keyboard(),
            )


async def show_portion_selection(
    message: Message,
    analysis: dict,
    state: FSMContext,
    processing_msg: Message | None = None,
):
    """Show portion selection interface"""

    # Check if we have portion options
    portion_options = analysis.get("portion_options", [])

    if not portion_options:
        error_text = "❌ Не удалось определить варианты порций. Попробуй описать блюдо подробнее."
        if processing_msg:
            try:
                await processing_msg.edit_text(
                    error_text, reply_markup=get_main_menu_keyboard()
                )
            except Exception:
                await message.answer(error_text, reply_markup=get_main_menu_keyboard())
        else:
            await message.answer(error_text, reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    # If only one portion option (exact measurement), auto-select it
    if len(portion_options) == 1 and portion_options[0].get("size") == "exact":
        selected_portion = portion_options[0]

        # Calculate nutrition for selected portion
        nutrition = nutrition_analyzer.calculate_nutrition_for_portion(
            analysis["nutrition_per_100g"], selected_portion["weight"]
        )

        # Store selected data
        await state.update_data(selected_portion=selected_portion, nutrition=nutrition)

        # Show nutrition confirmation directly
        await show_nutrition_confirmation(
            message, analysis, selected_portion, nutrition, state, processing_msg
        )
        await state.set_state(UniversalFoodStates.confirming_nutrition)
        return

    # Multiple options - show selection
    text = f"""
🍽 **{analysis["food_name"]}**

📝 _{analysis.get("description", "Описание недоступно")}_

Выбери размер порции:
"""

    # Add portion options with nutrition info
    portion_options_with_nutrition = (
        nutrition_analyzer.create_portion_options_with_nutrition(analysis)
    )

    for _, option in enumerate(portion_options_with_nutrition):
        nutrition = option["nutrition"]
        text += f"\n**{option['description']}** ({option['weight']}г):\n"
        text += f"🔥 {nutrition['total_calories']:.0f} ккал, "
        text += f"🥩 {nutrition['total_protein']:.1f}г, "
        text += f"🥑 {nutrition['total_fat']:.1f}г, "
        text += f"🍞 {nutrition['total_carbs']:.1f}г\n"

    keyboard = get_portion_selection_keyboard(analysis["portion_options"])

    if processing_msg:
        try:
            await processing_msg.edit_text(
                text, reply_markup=keyboard, parse_mode="Markdown"
            )
        except Exception:
            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    await state.set_state(UniversalFoodStates.selecting_portion)


@router.callback_query(
    UniversalFoodStates.selecting_portion, F.data.startswith("select_portion:")
)
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
        analysis["nutrition_per_100g"], selected_portion["weight"]
    )

    # Store selected data
    await state.update_data(selected_portion=selected_portion, nutrition=nutrition)

    # Show nutrition confirmation
    await show_nutrition_confirmation(
        callback.message, analysis, selected_portion, nutrition, state
    )
    await state.set_state(UniversalFoodStates.confirming_nutrition)


async def show_nutrition_confirmation(
    message: Message,
    analysis: dict,
    selected_portion: dict,
    nutrition: dict,
    state: FSMContext,
    processing_msg: Message | None = None,
):
    """Show nutrition confirmation with detailed breakdown"""

    data = await state.get_data()
    original_input = data.get("original_input", "")

    # Prepare confirmation text
    text = f"""
✅ **Готово к добавлению!**

🍽 **{analysis["food_name"]}**
📝 _{analysis.get("description", "")}_

⚖️ **Выбранная порция:** {selected_portion["description"]} ({selected_portion["weight"]}г)

**Пищевая ценность:**
{nutrition_analyzer.format_nutrition_summary(nutrition)}

📝 **Твое описание:** _{original_input}_

Добавить в дневник питания?
"""

    keyboard = get_nutrition_confirmation_keyboard(analysis["food_name"])

    if processing_msg:
        try:
            await processing_msg.edit_text(
                text, reply_markup=keyboard, parse_mode="Markdown"
            )
        except Exception:
            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        try:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            # If edit fails, send new message
            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(
    UniversalFoodStates.confirming_nutrition, F.data == "confirm_nutrition"
)
async def confirm_nutrition_entry(
    callback: CallbackQuery, state: FSMContext, user_id: int
):
    """Confirm and save nutrition entry to database"""

    await safe_answer_callback(callback, "Сохраняю...")

    try:
        data = await state.get_data()
        analysis = data.get("analysis", {})
        selected_portion = data.get("selected_portion", {})
        nutrition = data.get("nutrition", {})
        original_input = data.get("original_input", "")

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
                photo_file_id=data.get(
                    "photo_file_id"
                ),  # Include photo if it was photo input
                input_method=data.get("input_method", "text_universal"),
                ai_analysis=str(analysis),
            )

        # Format input method for display
        input_icon = "📸" if data.get("input_method") == "photo_universal" else "📝"

        success_text = f"""
✅ **Блюдо добавлено в дневник!**

🍽 **{food_entry.food_name}**
⚖️ Порция: {selected_portion["description"]} ({selected_portion["weight"]}г)

{nutrition_analyzer.format_nutrition_summary(nutrition)}

{input_icon} Источник: _{original_input}_
🕐 Время: сейчас
📊 Запись #{food_entry.id}
"""

        try:
            await callback.message.edit_text(
                success_text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown",
            )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                success_text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown",
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Error saving universal food entry: {e}")

        try:
            await callback.message.edit_text(
                "❌ Ошибка при сохранении записи. Попробуй еще раз.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                "❌ Ошибка при сохранении записи. Попробуй еще раз.",
                reply_markup=get_main_menu_keyboard(),
            )

        await state.clear()


@router.callback_query(
    UniversalFoodStates.confirming_nutrition, F.data == "change_portion"
)
async def change_portion_selection(callback: CallbackQuery, state: FSMContext):
    """Allow user to change portion selection"""

    await safe_answer_callback(callback)

    data = await state.get_data()
    analysis = data.get("analysis", {})

    # Show portion selection again
    await show_portion_selection_edit(callback.message, analysis, state)


async def show_portion_selection_edit(
    message: Message, analysis: dict, state: FSMContext
):
    """Show portion selection interface for editing"""

    text = f"""
🍽 **{analysis["food_name"]}**

📝 _{analysis.get("description", "Описание недоступно")}_

Выбери размер порции:
"""

    # Add portion options with nutrition info
    portion_options_with_nutrition = (
        nutrition_analyzer.create_portion_options_with_nutrition(analysis)
    )

    for _, option in enumerate(portion_options_with_nutrition):
        nutrition = option["nutrition"]
        text += f"\n**{option['description']}** ({option['weight']}г):\n"
        text += f"🔥 {nutrition['total_calories']:.0f} ккал, "
        text += f"🥩 {nutrition['total_protein']:.1f}г, "
        text += f"🥑 {nutrition['total_fat']:.1f}г, "
        text += f"🍞 {nutrition['total_carbs']:.1f}г\n"

    keyboard = get_portion_selection_keyboard(analysis["portion_options"])

    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        # If edit fails, send new message
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    await state.set_state(UniversalFoodStates.selecting_portion)
