import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.connection import get_db_session
from bot.database.operations.food_ops import (
    delete_food_entry,
    get_food_entry_by_id,
    get_user_daily_nutrition_summary,
    get_user_food_entries_by_date,
)
from bot.database.operations.user_ops import get_user_by_id
from bot.keyboards.inline import (
    get_diary_keyboard,
    get_food_entry_actions_keyboard,
    get_yes_no_keyboard,
)
from bot.services.nutrition_analyzer import nutrition_analyzer
from bot.utils.helpers import (
    safe_answer_callback,
    safe_edit_callback_message,
)

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "view_diary")
async def show_diary_menu(callback: CallbackQuery, state: FSMContext):
    """Show diary menu"""

    await safe_answer_callback(callback)

    text = """
📊 **Дневник питания**

Выбери что показать:
"""

    await safe_edit_callback_message(
        callback, text, reply_markup=get_diary_keyboard(), parse_mode="Markdown"
    )


@router.callback_query(F.data == "diary_today")
async def show_today_diary(callback: CallbackQuery, user_id: int):
    """Show today's food diary"""

    await safe_answer_callback(callback)

    try:
        async with get_db_session() as session:
            # Get today's entries
            today = date.today()
            entries = await get_user_food_entries_by_date(session, user_id, today)

            # Get daily summary
            daily_summary = await get_user_daily_nutrition_summary(
                session, user_id, today
            )

            # Get user goals
            user = await get_user_by_id(session, user_id)

        if not entries:
            text = f"""
📅 **Дневник за сегодня ({today.strftime("%d.%m.%Y")})**

🤷‍♂️ Пока нет записей о еде на сегодня.

Добавь первое блюдо через главное меню!
"""
            await callback.message.edit_text(
                text, reply_markup=get_diary_keyboard(), parse_mode="Markdown"
            )
        else:
            text = f"""
📅 **Дневник за сегодня ({today.strftime("%d.%m.%Y")})**

"""

            # Add daily summary
            if user:
                goals = {
                    "daily_calories_goal": user.daily_calories_goal,
                    "daily_protein_goal": user.daily_protein_goal,
                    "daily_fat_goal": user.daily_fat_goal,
                    "daily_carbs_goal": user.daily_carbs_goal,
                }
                text += nutrition_analyzer.format_daily_summary(daily_summary, goals)
            else:
                text += nutrition_analyzer.format_daily_summary(daily_summary)

            text += "\n\n🍽 **Записи о еде:**\n_(Нажми на запись для действий)_"

            # Create keyboard with food entries
            builder = InlineKeyboardBuilder()

            for i, entry in enumerate(entries, 1):
                entry_text = f"{i}. {entry.food_name} - {entry.total_calories:.0f} ккал"
                if entry.portion_weight:
                    entry_text += f" ({entry.portion_weight}г)"
                entry_text += f" | {entry.created_at.strftime('%H:%M')}"

                builder.row(
                    InlineKeyboardButton(
                        text=entry_text, callback_data=f"view_entry:{entry.id}"
                    )
                )

            # Add navigation buttons
            builder.row(
                InlineKeyboardButton(text="📊 Статистика", callback_data="diary_stats")
            )
            builder.row(
                InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")
            )

            await callback.message.edit_text(
                text, reply_markup=builder.as_markup(), parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error showing today's diary: {e}")

        await callback.message.edit_text(
            "❌ Ошибка при загрузке дневника", reply_markup=get_diary_keyboard()
        )


@router.callback_query(F.data.startswith("view_entry:"))
async def view_food_entry(callback: CallbackQuery, user_id: int):
    """Show detailed view of a food entry"""

    await safe_answer_callback(callback)

    try:
        entry_id = int(callback.data.split(":")[1])

        async with get_db_session() as session:
            entry = await get_food_entry_by_id(session, entry_id, user_id)

        if not entry:
            await callback.message.edit_text(
                "❌ Запись не найдена", reply_markup=get_diary_keyboard()
            )
            return

        # Format entry details
        text = f"""
🍽 **Детали записи о еде**

**{entry.food_name}**

📊 **Питательная ценность:**
🔥 Калории: {entry.total_calories:.1f} ккал
🥩 Белки: {entry.total_protein:.1f} г
🥑 Жиры: {entry.total_fat:.1f} г  
🍞 Углеводы: {entry.total_carbs:.1f} г

"""

        if entry.portion_weight:
            text += f"⚖️ **Вес порции:** {entry.portion_weight} г\n"

        if entry.portion_size:
            text += f"📏 **Размер порции:** {entry.portion_size}\n"

        if entry.food_description:
            text += f"📝 **Описание:** {entry.food_description}\n"

        text += f"""
🕐 **Время добавления:** {entry.created_at.strftime("%d.%m.%Y %H:%M")}
📝 **Способ ввода:** {"📸 Фото" if entry.input_method == "photo" else "✍️ Текст"}
"""

        await callback.message.edit_text(
            text,
            reply_markup=get_food_entry_actions_keyboard(entry.id),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error viewing food entry: {e}")

        await callback.message.edit_text(
            "❌ Ошибка при загрузке записи", reply_markup=get_diary_keyboard()
        )


@router.callback_query(F.data.startswith("delete_entry:"))
async def confirm_delete_entry(callback: CallbackQuery, user_id: int):
    """Confirm deletion of food entry"""

    await safe_answer_callback(callback)

    try:
        entry_id = int(callback.data.split(":")[1])

        async with get_db_session() as session:
            entry = await get_food_entry_by_id(session, entry_id, user_id)

        if not entry:
            await callback.message.edit_text(
                "❌ Запись не найдена", reply_markup=get_diary_keyboard()
            )
            return

        text = f"""
🗑 **Удаление записи**

Точно хочешь удалить эту запись?

**{entry.food_name}**
🔥 {entry.total_calories:.1f} ккал
🕐 {entry.created_at.strftime("%d.%m.%Y %H:%M")}

⚠️ Это действие нельзя отменить!
"""

        await callback.message.edit_text(
            text,
            reply_markup=get_yes_no_keyboard(
                yes_callback=f"confirm_delete:{entry_id}",
                no_callback=f"view_entry:{entry_id}",
            ),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error confirming delete: {e}")

        await callback.message.edit_text(
            "❌ Ошибка при подготовке к удалению", reply_markup=get_diary_keyboard()
        )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_entry_confirmed(callback: CallbackQuery, user_id: int):
    """Actually delete the food entry"""

    await safe_answer_callback(callback)

    try:
        entry_id = int(callback.data.split(":")[1])

        async with get_db_session() as session:
            # Get entry info before deletion for confirmation message
            entry = await get_food_entry_by_id(session, entry_id, user_id)

            if not entry:
                await callback.message.edit_text(
                    "❌ Запись не найдена", reply_markup=get_diary_keyboard()
                )
                return

            entry_name = entry.food_name
            entry_calories = entry.total_calories

            # Delete the entry
            deleted = await delete_food_entry(session, entry_id, user_id)
            await session.commit()

            if deleted:
                text = f"""
✅ **Запись удалена**

Запись **{entry_name}** ({entry_calories:.1f} ккал) успешно удалена из дневника.

Статистика обновлена автоматически.
"""

                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(
                        text="📅 К дневнику", callback_data="diary_today"
                    )
                )
                builder.row(
                    InlineKeyboardButton(
                        text="◀️ Главное меню", callback_data="main_menu"
                    )
                )

                await callback.message.edit_text(
                    text, reply_markup=builder.as_markup(), parse_mode="Markdown"
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось удалить запись", reply_markup=get_diary_keyboard()
                )

    except Exception as e:
        logger.error(f"Error deleting food entry: {e}")

        await callback.message.edit_text(
            "❌ Ошибка при удалении записи", reply_markup=get_diary_keyboard()
        )


@router.callback_query(F.data == "diary_stats")
async def show_diary_stats(callback: CallbackQuery, user_id: int):
    """Show diary statistics"""

    await safe_answer_callback(callback)

    try:
        async with get_db_session() as session:
            # Get current week (Monday to Sunday)
            today = date.today()
            days_since_monday = today.weekday()  # Monday is 0

            # Calculate week start (Monday) and end (Sunday)
            week_start = today - timedelta(days=days_since_monday)
            week_end = week_start + timedelta(days=6)

            # Calculate averages for the week
            total_calories = 0
            total_protein = 0
            total_fat = 0
            total_carbs = 0
            days_with_data = 0

            # Daily breakdown for the week
            daily_data = []
            week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

            for i in range(7):
                check_date = week_start + timedelta(days=i)
                daily_summary = await get_user_daily_nutrition_summary(
                    session, user_id, check_date
                )

                # Store daily data
                daily_data.append(
                    {
                        "day": week_days[i],
                        "date": check_date,
                        "calories": daily_summary["total_calories"],
                        "entries": daily_summary["entries_count"],
                    }
                )

                if daily_summary["entries_count"] > 0:
                    total_calories += daily_summary["total_calories"]
                    total_protein += daily_summary["total_protein"]
                    total_fat += daily_summary["total_fat"]
                    total_carbs += daily_summary["total_carbs"]
                    days_with_data += 1

            if days_with_data == 0:
                text = f"""
📊 **Статистика за неделю**

📅 {week_start.strftime("%d.%m")} - {week_end.strftime("%d.%m.%Y")} (пн-вс)

📈 Недостаточно данных для статистики.

Добавь несколько записей о еде, чтобы увидеть статистику!
"""
            else:
                avg_calories = total_calories / days_with_data
                avg_protein = total_protein / days_with_data
                avg_fat = total_fat / days_with_data
                avg_carbs = total_carbs / days_with_data

                # Build daily breakdown
                daily_breakdown = "\n📊 **По дням:**\n"
                for day_data in daily_data:
                    status = "✅" if day_data["entries"] > 0 else "⭕"
                    date_str = day_data["date"].strftime("%d.%m")
                    if day_data["entries"] > 0:
                        daily_breakdown += f"{status} {day_data['day']} {date_str}: {day_data['calories']:.0f} ккал\n"
                    else:
                        daily_breakdown += (
                            f"{status} {day_data['day']} {date_str}: нет записей\n"
                        )

                text = f"""
📊 **Статистика за неделю**

📅 {week_start.strftime("%d.%m")} - {week_end.strftime("%d.%m.%Y")} (пн-вс)

📈 **Средние показатели в день:**
🔥 Калории: {avg_calories:.0f} ккал
🥩 Белки: {avg_protein:.1f} г
🥑 Жиры: {avg_fat:.1f} г
🍞 Углеводы: {avg_carbs:.1f} г

📅 Дней с записями: {days_with_data} из 7
{daily_breakdown}
💡 **Рекомендации:**
{"✅ Отлично! Ведешь регулярный учет" if days_with_data >= 5 else "📝 Старайся записывать еду каждый день"}
"""

        await safe_edit_callback_message(
            callback, text, reply_markup=get_diary_keyboard(), parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error showing diary stats: {e}")

        await safe_edit_callback_message(
            callback,
            "❌ Ошибка при загрузке статистики",
            reply_markup=get_diary_keyboard(),
        )
