import logging
import asyncio
from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.inline import (
    get_chat_actions_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from bot.services.langgraph_service import langgraph_service
from bot.database.connection import get_db_session
from bot.database.operations.food_ops import get_user_daily_nutrition_summary
from bot.utils.helpers import safe_answer_callback, is_food_related_message

logger = logging.getLogger(__name__)

router = Router()


class ChatStates(StatesGroup):
    waiting_for_question = State()
    streaming_response = State()


def should_use_langgraph(question: str, nutrition_data: dict = None) -> bool:
    """Determine if we should use LangGraph for this question"""
    
    question_lower = question.lower()
    
    # Use LangGraph for complex conversations
    complex_indicators = [
        # Multi-step reasoning
        'как', 'почему', 'что делать', 'посоветуй', 'рекомендуй',
        # Personal advice
        'мой', 'мне', 'я ем', 'моя диета', 'мой рацион',
        # Analysis requests
        'проанализируй', 'оцени', 'что думаешь', 'как улучшить',
        # Planning
        'план', 'составь', 'разработай', 'спланируй',
        # Context-dependent questions
        'сегодня', 'сейчас', 'в данный момент', 'учитывая'
    ]
    
    # Use simple streaming for basic questions
    simple_indicators = [
        'привет', 'здравствуй', 'спасибо', 'пока',
        'что это', 'что значит', 'определение'
    ]
    
    # Check for simple questions first
    if any(indicator in question_lower for indicator in simple_indicators):
        return False
    
    # Check for complex questions
    if any(indicator in question_lower for indicator in complex_indicators):
        return True
    
    # Use LangGraph if we have nutrition data (context-aware conversations)
    if nutrition_data and nutrition_data.get('entries_count', 0) > 0:
        return True
    
    # Use LangGraph for longer questions (likely more complex)
    if len(question.split()) > 10:
        return True
    
    # Default to simple streaming for short, basic questions
    return False


@router.callback_query(F.data == "nutrition_chat")
async def start_nutrition_chat(callback: CallbackQuery, state: FSMContext):
    """Start nutrition chat"""
    
    await safe_answer_callback(callback)
    
    text = """
💬 **Чат с ИИ Нутрициологом**

Задай мне любой вопрос о питании, здоровье или спорте!

💡 **Примеры вопросов:**
• Сколько белка нужно в день?
• Как правильно худеть?
• Что съесть перед тренировкой?
• Полезны ли углеводы?
• Проанализируй мой рацион за сегодня
• Дай совет по моему питанию

Можешь также воспользоваться быстрыми действиями ниже:
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=get_chat_actions_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(ChatStates.waiting_for_question)


@router.callback_query(ChatStates.waiting_for_question, F.data == "chat_my_nutrition")
async def analyze_user_nutrition(callback: CallbackQuery, user_id: int):
    """Analyze user's daily nutrition and provide advice"""
    
    await safe_answer_callback(callback, "Анализирую...")
    
    try:
        async with get_db_session() as session:
            # Get today's nutrition summary
            today = date.today()
            nutrition_data = await get_user_daily_nutrition_summary(session, user_id, today)
        
        if nutrition_data['entries_count'] == 0:
            text = """
📊 **Анализ рациона**

🤷‍♂️ У тебя пока нет записей о еде на сегодня.

Добавь несколько блюд в дневник, и я смогу проанализировать твой рацион и дать персональные советы!
"""
            
            await callback.message.edit_text(
                text,
                reply_markup=get_chat_actions_keyboard(),
                parse_mode="Markdown"
            )
            return
        
        # Show current nutrition and start streaming advice
        nutrition_summary = f"""
📊 **Твой рацион сегодня:**

🔥 Калории: {nutrition_data['total_calories']:.0f} ккал
🥩 Белки: {nutrition_data['total_protein']:.1f} г  
🥑 Жиры: {nutrition_data['total_fat']:.1f} г
🍞 Углеводы: {nutrition_data['total_carbs']:.1f} г
🍽 Приемов пищи: {nutrition_data['entries_count']}

💭 **ИИ анализирует твой рацион...**
"""
        
        # Show nutrition data first
        await callback.message.edit_text(
            nutrition_summary,
            parse_mode="Markdown"
        )
        
        # Generate streaming advice
        question = "Проанализируй мой рацион за сегодня и дай советы по улучшению питания"
        await stream_ai_response(callback.message, question, nutrition_data)
        
    except Exception as e:
        logger.error(f"Error analyzing user nutrition: {e}")
        
        await callback.message.edit_text(
            "❌ Ошибка при анализе рациона",
            reply_markup=get_chat_actions_keyboard()
        )


@router.callback_query(ChatStates.waiting_for_question, F.data == "chat_nutrition_tips")
async def get_nutrition_tips(callback: CallbackQuery):
    """Get general nutrition tips"""
    
    await safe_answer_callback(callback, "Готовлю советы...")
    
    question = "Дай 5 важных советов по здоровому питанию и поддержанию хорошей формы"
    await stream_ai_response(callback.message, question)


@router.message(ChatStates.waiting_for_question, F.text)
async def handle_nutrition_question(message: Message, state: FSMContext, user_id: int):
    """Handle user's nutrition question"""
    
    question = message.text.strip()
    
    if len(question) < 3:
        await message.answer(
            "❓ Вопрос слишком короткий. Попробуй сформулировать подробнее:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    try:
        # Check if question is food-related and user wants personal advice
        nutrition_data = None
        
        if is_food_related_message(question) and any(word in question.lower() for word in 
            ['мой', 'мне', 'я', 'сегодня', 'рацион', 'дневник']):
            
            # Get user's nutrition data for context
            async with get_db_session() as session:
                today = date.today()
                nutrition_data = await get_user_daily_nutrition_summary(session, user_id, today)
                
                if nutrition_data['entries_count'] == 0:
                    nutrition_data = None
        
        # Stream AI response
        await stream_ai_response(message, question, nutrition_data, user_id)
        
    except Exception as e:
        logger.error(f"Error handling nutrition question: {e}")
        
        await message.answer(
            "❌ Произошла ошибка при обработке вопроса. Попробуй еще раз.",
            reply_markup=get_chat_actions_keyboard()
        )


async def stream_ai_response(message: Message, question: str, nutrition_data: dict = None, user_id: int = None):
    """Stream AI response with real-time updates using LangGraph"""
    
    try:
        # Start with thinking message
        response_msg = await message.answer("🤔 Думаю...")
        
        response_text = ""
        last_update_length = 0
        
        # Determine which service to use based on question complexity
        use_langgraph = should_use_langgraph(question, nutrition_data)
        
        if use_langgraph and user_id:
            # Use LangGraph for complex conversations
            stream_generator = langgraph_service.chat_with_nutrition_agent(
                user_message=question,
                user_id=user_id,
                thread_id=f"chat_session_{user_id}"
            )
        else:
            # Use simple streaming for basic questions
            stream_generator = langgraph_service.simple_chat_stream(
                user_message=question,
                nutrition_data=nutrition_data
            )
        
        # Stream response from LangGraph or simple chat
        async for chunk in stream_generator:
            response_text += chunk
            
            # Update message every 50 characters or on sentence end
            if (len(response_text) - last_update_length >= 50 or 
                chunk.endswith('.') or chunk.endswith('!') or chunk.endswith('?')):
                
                try:
                    # Add typing indicator
                    display_text = response_text + " ⌨️"
                    
                    await response_msg.edit_text(
                        display_text,
                        parse_mode="Markdown" if "*" in display_text or "_" in display_text else None
                    )
                    
                    last_update_length = len(response_text)
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    # Continue streaming even if edit fails
                    logger.debug(f"Error updating message during streaming: {e}")
                    pass
        
        # Final update without typing indicator
        if response_text:
            try:
                await response_msg.edit_text(
                    response_text,
                    parse_mode="Markdown" if "*" in response_text or "_" in response_text else None
                )
            except Exception:
                # If final edit fails, send new message
                await message.answer(response_text)
        
        # Add action buttons after response
        await message.answer(
            "💬 Задай еще вопрос или выбери действие:",
            reply_markup=get_chat_actions_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error streaming AI response: {e}")
        
        error_message = "❌ Произошла ошибка при получении ответа. Попробуй переформулировать вопрос."
        
        try:
            await response_msg.edit_text(error_message)
        except:
            await message.answer(error_message)
        
        await message.answer(
            "💬 Попробуй еще раз:",
            reply_markup=get_chat_actions_keyboard()
        )


@router.message(ChatStates.waiting_for_question, ~F.text)
async def handle_non_text_in_chat(message: Message):
    """Handle non-text messages in chat state"""
    
    await message.answer(
        "💬 Пожалуйста, напиши текстовый вопрос о питании или выбери действие из меню:",
        reply_markup=get_chat_actions_keyboard()
    ) 