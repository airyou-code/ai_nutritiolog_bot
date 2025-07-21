import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import get_main_menu_keyboard, get_back_to_menu_keyboard
from bot.utils.helpers import safe_answer_callback, safe_edit_callback_message

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, db_user, user_id: int):
    """Handle /start command"""
    
    welcome_text = f"""
🍎 **Добро пожаловать в ИИ Нутрициолог!**

Привет, {db_user.full_name if db_user else 'пользователь'}! 👋

Я помогу тебе:
• 📸 Анализировать фотографии еды
• 📊 Отслеживать БЖУ и калории  
• 📝 Вести дневник питания
• 💡 Давать советы по питанию

**Что умею:**
🔍 Распознаю еду по фото и рассчитываю БЖУ
📏 Умно определяю размеры порций
💾 Сохраняю все в твой личный дневник
🤖 Отвечаю на вопросы о питании и здоровье

**💡 Просто напиши что ты ел или отправь фото!**

📝 **Текст:** "2 банана", "тарелка борща", "кусочек хлеба"  
📸 **Фото:** Отправь фотографию блюда (можешь добавить описание к фото)

Я сам пойму что это за блюдо и предложу варианты порций.

Или выбери действие в меню ниже! 👇
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Show main menu"""
    
    await safe_answer_callback(callback)
    
    # Clear any existing state
    await state.clear()
    
    menu_text = """
🏠 **Главное меню**

Выберите действие:
"""
    
    await safe_edit_callback_message(
        callback,
        menu_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "about")
async def show_about(callback: CallbackQuery):
    """Show information about the bot"""
    
    await safe_answer_callback(callback)
    
    about_text = """
ℹ️ **О боте**

**ИИ Нутрициолог** - твой персональный помощник по питанию!

🔬 **Технологии:**
• OpenAI GPT-4o для анализа еды
• Распознавание изображений
• Расчет БЖУ и калорий
• База данных PostgreSQL

👨‍💻 **Возможности:**
• Анализ фотографий еды
• Ввод блюд текстом
• Отслеживание дневного рациона  
• Персональные советы по питанию
• Установка целей по БЖУ

⚡ **Быстро и точно:**
• Мгновенный анализ фото
• Умные алгоритмы распознавания
• Точные расчеты питательности

📊 **Статистика:**
• Дневник питания
• Прогресс к целям
• История потребления

Версия: 1.0.0
"""
    
    await safe_edit_callback_message(
        callback,
        about_text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action and return to main menu"""
    
    await safe_answer_callback(callback, "Отменено")
    
    # Clear state
    await state.clear()
    
    # Show main menu
    await show_main_menu(callback, state)


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext):
    """Handle /menu command"""
    
    # Clear any existing state
    await state.clear()
    
    menu_text = """
🏠 **Главное меню**

Выберите действие:
"""
    
    await message.answer(
        menu_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command"""
    
    help_text = """
❓ **Помощь**

**Основные команды:**
/start - Запустить бота
/menu - Показать главное меню
/help - Показать эту справку

**Как пользоваться:**

📸 **Анализ фото:**
1. Нажми "Сфотографировать еду"
2. Отправь фото блюда
3. Выбери размер порции
4. Подтверди добавление в дневник

✍️ **Ввод текстом:**
1. Нажми "Описать блюдо текстом"
2. Напиши название блюда и вес
3. Выбери размер порции
4. Подтверди данные

📊 **Дневник питания:**
- Смотри съеденное за день
- Отслеживай прогресс к целям
- Удаляй неверные записи

💬 **Чат с ИИ:**
- Задавай вопросы о питании
- Получай персональные советы
- Узнавай о своем рационе

Нужна помощь? Напиши в поддержку!
"""
    
    await message.answer(
        help_text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode="Markdown"
    ) 