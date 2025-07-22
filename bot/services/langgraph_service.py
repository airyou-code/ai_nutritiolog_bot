import logging
import asyncio
import json
import base64
from io import BytesIO
from typing import Dict, Any, AsyncGenerator, Optional, List, Callable
from datetime import date

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
# TODO: Add Redis checkpointer when properly configured
# from langgraph_checkpoint_redis import RedisCheckpointer
from langgraph.prebuilt import create_react_agent
from PIL import Image

from bot.config.settings import settings
from bot.services.redis_service import redis_service
from bot.database.connection import get_db_session
from bot.database.operations.food_ops import get_user_daily_nutrition_summary

logger = logging.getLogger(__name__)


class LangGraphService:
    """Service for LangGraph-based AI conversations and agents"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            streaming=True
        )
        self._checkpointer = None
        self._nutrition_agent = None
        self._food_analysis_agent = None
    
    async def get_checkpointer(self):
        """Get checkpointer for conversation memory"""
        if self._checkpointer is None:
            try:
                # TODO: Implement Redis checkpointer when properly configured
                # For now, use memory-based checkpointer
                logger.info("Using in-memory checkpointer for LangGraph conversations")
                self._checkpointer = MemorySaver()
            except Exception as e:
                logger.error(f"Error creating checkpointer: {e}")
                self._checkpointer = MemorySaver()
        
        return self._checkpointer
    
    async def save_important_conversation_data(
        self,
        user_id: int,
        conversation_summary: str,
        insights: Dict[str, Any],
        nutrition_goals: Optional[Dict] = None
    ):
        """Save important conversation insights to PostgreSQL for long-term storage"""
        
        try:
            # This would be implemented to save key insights to database
            # For example: dietary preferences, allergies, goals, etc.
            
            logger.info(f"Saving conversation insights for user {user_id}")
            
            # Example structure for future implementation:
            conversation_data = {
                "user_id": user_id,
                "summary": conversation_summary,
                "insights": insights,
                "nutrition_goals": nutrition_goals,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # TODO: Implement database storage
            # await save_conversation_insights(conversation_data)
            
        except Exception as e:
            logger.error(f"Error saving conversation data: {e}")
    
    async def get_user_conversation_context(self, user_id: int) -> Dict[str, Any]:
        """Get user's conversation context from both Redis and PostgreSQL"""
        
        context = {
            "recent_topics": [],
            "preferences": {},
            "long_term_goals": {},
            "conversation_style": "friendly"
        }
        
        try:
            # Get recent conversation topics from Redis
            recent_data = await redis_service.get_temp_data(user_id, "recent_topics")
            if recent_data:
                context["recent_topics"] = recent_data
            
            # TODO: Get long-term preferences from PostgreSQL
            # long_term_data = await get_user_conversation_preferences(user_id)
            # context.update(long_term_data)
            
        except Exception as e:
            logger.error(f"Error loading conversation context: {e}")
        
        return context
    
    async def get_nutrition_agent(self):
        """Get or create nutrition consultant agent"""
        if self._nutrition_agent is None:
            checkpointer = await self.get_checkpointer()
            
            # Create specialized nutrition agent
            self._nutrition_agent = await self._create_nutrition_agent(checkpointer)
            logger.info("Created nutrition consultant agent")
        
        return self._nutrition_agent
    
    async def _create_nutrition_agent(self, checkpointer):
        """Create a specialized nutrition consultant agent"""
        
        # Define the agent's state and behavior
        class NutritionState(MessagesState):
            user_id: Optional[int] = None
            nutrition_data: Optional[Dict] = None
            context_loaded: bool = False
        
        async def load_user_context(state: NutritionState):
            """Load user's nutrition data for context"""
            if state.get("context_loaded", False):
                return state
            
            user_id = state.get("user_id")
            if not user_id:
                return {**state, "context_loaded": True}
            
            try:
                async with get_db_session() as session:
                    today = date.today()
                    nutrition_data = await get_user_daily_nutrition_summary(session, user_id, today)
                    
                    return {
                        **state, 
                        "nutrition_data": nutrition_data,
                        "context_loaded": True
                    }
            except Exception as e:
                logger.error(f"Error loading user context: {e}")
                return {**state, "context_loaded": True}
        
        async def nutrition_consultant(state: NutritionState):
            """Main nutrition consultant node"""
            messages = state["messages"]
            nutrition_data = state.get("nutrition_data")
            
            # Build system prompt with user context
            system_prompt = self._build_nutrition_system_prompt(nutrition_data)
            
            # Prepare messages for LLM
            llm_messages = [SystemMessage(content=system_prompt)]
            llm_messages.extend(messages)
            
            # Get response from LLM
            response = await self.llm.ainvoke(llm_messages)
            
            return {"messages": [response]}
        
        # Build the graph
        workflow = StateGraph(NutritionState)
        
        # Add nodes
        workflow.add_node("load_context", load_user_context)
        workflow.add_node("consultant", nutrition_consultant)
        
        # Define flow
        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "consultant")
        workflow.add_edge("consultant", END)
        
        # Compile with checkpointer
        return workflow.compile(checkpointer=checkpointer)
    
    def _build_nutrition_system_prompt(self, nutrition_data: Optional[Dict] = None) -> str:
        """Build system prompt for nutrition consultant"""
        
        base_prompt = """
        Ты профессиональный нутрициолог и консультант по питанию. 
        
        Твои основные принципы:
        - Давай научно обоснованные советы
        - Отвечай на русском языке
        - Будь доброжелательным и поддерживающим
        - Учитывай индивидуальные особенности пользователя
        - При необходимости рекомендуй обратиться к врачу
        
        Ты можешь помочь с:
        - Анализом рациона питания
        - Рекомендациями по улучшению питания
        - Ответами на вопросы о БЖУ и калориях
        - Составлением планов питания
        - Советами по здоровому образу жизни
        """
        
        if nutrition_data and nutrition_data.get('entries_count', 0) > 0:
            base_prompt += f"""
            
        Данные о питании пользователя сегодня:
        - Общие калории: {nutrition_data.get('total_calories', 0):.1f} ккал
        - Белки: {nutrition_data.get('total_protein', 0):.1f} г
        - Жиры: {nutrition_data.get('total_fat', 0):.1f} г
        - Углеводы: {nutrition_data.get('total_carbs', 0):.1f} г
        - Количество приемов пищи: {nutrition_data.get('entries_count', 0)}
        
        Учитывай эти данные при формировании ответов и рекомендаций.
        """
        
        return base_prompt
    
    async def chat_with_nutrition_agent(
        self,
        user_message: str,
        user_id: int,
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Chat with nutrition agent and stream response"""
        
        try:
            agent = await self.get_nutrition_agent()
            
            # Prepare config for conversation thread
            config = {
                "configurable": {
                    "thread_id": thread_id or f"user_{user_id}_{int(asyncio.get_event_loop().time())}"
                }
            }
            
            # Create input state
            input_state = {
                "messages": [HumanMessage(content=user_message)],
                "user_id": user_id,
                "context_loaded": False
            }
            
            # Stream response from agent
            async for event in agent.astream(input_state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == "consultant" and "messages" in node_output:
                        message = node_output["messages"][-1]
                        if hasattr(message, 'content'):
                            # Yield content in chunks for streaming effect
                            content = message.content
                            chunk_size = 50
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i + chunk_size]
                                yield chunk
                                await asyncio.sleep(0.1)  # Small delay for streaming effect
                            break
                    
        except Exception as e:
            logger.error(f"Error in nutrition agent chat: {e}")
            yield f"Извините, произошла ошибка при обработке запроса: {str(e)}"
    
    async def simple_chat_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        nutrition_data: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """Simple streaming chat without complex agent logic"""
        
        try:
            # Build messages
            messages = []
            
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            else:
                messages.append(SystemMessage(content=self._build_nutrition_system_prompt(nutrition_data)))
            
            messages.append(HumanMessage(content=user_message))
            
            # Stream response
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"Error in simple chat stream: {e}")
            yield f"Извините, произошла ошибка: {str(e)}"
    
    async def analyze_conversation_context(
        self,
        messages: List[BaseMessage],
        user_id: int
    ) -> Dict[str, Any]:
        """Analyze conversation context to determine best response strategy"""
        
        # Simple context analysis - can be extended with more sophisticated logic
        last_message = messages[-1].content.lower() if messages else ""
        
        context = {
            "is_food_related": any(word in last_message for word in [
                'еда', 'блюдо', 'калории', 'белки', 'жиры', 'углеводы', 
                'рацион', 'питание', 'диета', 'вес', 'похудеть'
            ]),
            "is_personal_question": any(word in last_message for word in [
                'мой', 'мне', 'я', 'мои', 'меня'
            ]),
            "needs_nutrition_data": any(word in last_message for word in [
                'сегодня', 'дневник', 'статистика', 'прогресс'
            ]),
            "is_greeting": any(word in last_message for word in [
                'привет', 'здравствуй', 'добро', 'начать'
            ])
        }
        
        return context
    
    async def analyze_food_photo_with_langgraph(
        self,
        image_data: bytes,
        user_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze food photo using LangGraph agent"""
        
        try:
            # Create specialized food analysis agent
            food_agent = await self._create_food_analysis_agent()
            
            # Convert image to base64
            image = Image.open(BytesIO(image_data))
            
            # Resize image if too large to save tokens
            max_size = (1024, 1024)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to base64
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Create prompt for food analysis
            prompt = self._get_food_analysis_prompt(user_description)
            
            # Create input with image
            input_state = {
                "messages": [HumanMessage(content=[
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ])],
                "image_data": image_base64,
                "user_description": user_description
            }
            
            # Process with agent
            result = await food_agent.ainvoke(input_state)
            
            # Parse the response
            response_content = result["messages"][-1].content
            return self._parse_food_analysis_response(response_content)
            
        except Exception as e:
            logger.error(f"Error analyzing food photo with LangGraph: {e}")
            raise
    
    async def analyze_food_text_with_langgraph(
        self,
        food_description: str,
        portion_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze food text using LangGraph agent"""
        
        try:
            # Create specialized food analysis agent
            food_agent = await self._create_food_analysis_agent()
            
            # Create prompt for text analysis
            prompt = self._get_text_analysis_prompt(food_description, portion_info)
            
            # Create input
            input_state = {
                "messages": [HumanMessage(content=prompt)],
                "food_description": food_description,
                "portion_info": portion_info
            }
            
            # Process with agent
            result = await food_agent.ainvoke(input_state)
            
            # Parse the response
            response_content = result["messages"][-1].content
            return self._parse_food_analysis_response(response_content)
            
        except Exception as e:
            logger.error(f"Error analyzing food text with LangGraph: {e}")
            raise
    
    async def _create_food_analysis_agent(self):
        """Create specialized food analysis agent"""
        
        if self._food_analysis_agent is None:
            # Define specialized state for food analysis
            class FoodAnalysisState(MessagesState):
                image_data: Optional[str] = None
                user_description: Optional[str] = None
                food_description: Optional[str] = None
                portion_info: Optional[str] = None
            
            async def food_analyzer_node(state: FoodAnalysisState):
                """Specialized node for food analysis"""
                messages = state["messages"]
                
                # Create specialized LLM for food analysis with specific temperature
                food_llm = ChatOpenAI(
                    model=settings.openai_model,
                    api_key=settings.openai_api_key,
                    temperature=0.3,  # Lower temperature for more consistent analysis
                    max_tokens=1000
                )
                
                # Get response from LLM
                response = await food_llm.ainvoke(messages)
                
                return {"messages": [response]}
            
            # Build the graph
            workflow = StateGraph(FoodAnalysisState)
            workflow.add_node("analyzer", food_analyzer_node)
            workflow.add_edge(START, "analyzer")
            workflow.add_edge("analyzer", END)
            
            # Compile without checkpointer (stateless for food analysis)
            self._food_analysis_agent = workflow.compile()
            logger.info("Created specialized food analysis agent")
        
        return self._food_analysis_agent
    
    def _get_food_analysis_prompt(self, user_description: Optional[str] = None) -> str:
        """Get prompt for food photo analysis"""
        
        base_prompt = """
        Ты анализируешь изображение для приложения учета питания.
        
        ЗАДАЧА: Определить еду на фото и проанализировать её.
        
        ЕСЛИ НА ФОТО ОЧЕВИДНО НЕ ЕДА (люди, пейзажи, мебель, животные без еды), верни:
        {
            "is_food": false,
            "food_name": "",
            "description": "На изображении не обнаружена еда",
            "portion_options": [],
            "nutrition_per_100g": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        }
        
        ЕСЛИ НА ФОТО ЕСТЬ ЕДА (фрукты, овощи, блюда, напитки), проанализируй:
        {
            "is_food": true,
            "food_name": "название блюда",
            "description": "краткое описание состава",
            "portion_options": [
                {"size": "exact", "weight": вес_в_граммах, "description": "точное описание порции"}
            ],
            "nutrition_per_100g": {
                "calories": калории_на_100г,
                "protein": белки_на_100г,
                "fat": жиры_на_100г,
                "carbs": углеводы_на_100г
            }
        }
        
        Логика для portion_options:
        - Если ТОЧНО видно количество (2 банана, 1 яблоко, конкретная тарелка) → ОДИН вариант
        - Если количество НЕОПРЕДЕЛЕННО → 2-3 варианта по размерам
        
        ВАЖНО: Банан, яблоко, овощи - это ЕДА! Отклоняй только если точно НЕ еда.
        """
        
        if user_description:
            base_prompt += f"\n\nДополнительное описание от пользователя: {user_description}"
        
        return base_prompt
    
    def _get_text_analysis_prompt(self, food_description: str, portion_info: Optional[str] = None) -> str:
        """Get prompt for text food analysis"""
        
        prompt = f"""
        Проанализируй описание блюда и верни результат в формате JSON:

        Блюдо: {food_description}
        """
        
        if portion_info:
            prompt += f"\nПорция: {portion_info}"
        
        prompt += """

        СНАЧАЛА проверь - это описание ЕДЫ?
        
        ЕСЛИ НЕ ЕДА (общие фразы, приветствия, вопросы), верни:
        {
            "is_food": false,
            "food_name": "",
            "description": "Это не описание еды",
            "portion_options": [],
            "nutrition_per_100g": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        }
        
        ЕСЛИ ЭТО ЕДА, верни:
        {
            "is_food": true,
            "food_name": "название блюда",
            "description": "краткое описание состава",
            "portion_options": [
                {"size": "exact", "weight": вес_в_граммах, "description": "точное описание"}
            ],
            "nutrition_per_100g": {
                "calories": калории_на_100г,
                "protein": белки_на_100г,
                "fat": жиры_на_100г,
                "carbs": углеводы_на_100г
            }
        }
        
        ЛОГИКА для portion_options:
        
        🎯 ТОЧНОЕ КОЛИЧЕСТВО (дай 1 вариант):
        - "2 банана" → [{"size": "exact", "weight": 240, "description": "2 банана"}]
        - "3 яблока" → [{"size": "exact", "weight": 450, "description": "3 средних яблока"}]
        - "тарелка супа" → [{"size": "exact", "weight": 300, "description": "тарелка супа"}]
        - "стакан молока" → [{"size": "exact", "weight": 250, "description": "стакан молока"}]
        - "кусочек хлеба" → [{"size": "exact", "weight": 30, "description": "кусочек хлеба"}]
        
        ❓ НЕОПРЕДЕЛЕННОЕ КОЛИЧЕСТВО (дай 2-3 варианта):
        - "банан" → [
            {"size": "small", "weight": 120, "description": "1 банан"},
            {"size": "medium", "weight": 240, "description": "2 банана"},
            {"size": "large", "weight": 360, "description": "3 банана"}
          ]
        - "яблоко" → варианты по размеру (маленькое/среднее/большое)
        - "суп" → варианты по количеству (полтарелки/тарелка/большая порция)
        - "торт" → варианты по размеру куска
        
        ВНИМАНИЕ: Строго фильтруй НЕ-ЕДУ. Лучше отклонить сомнительное.
        """
        
        return prompt
    
    def _parse_food_analysis_response(self, content: str) -> Dict[str, Any]:
        """Parse food analysis response"""
        
        try:
            # Try to extract JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = content[start_idx:end_idx]
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing food analysis response: {e}")
            logger.error(f"Response content: {content}")
            
            # Return default structure if parsing fails  
            return {
                "is_food": False,
                "food_name": "",
                "description": "Ошибка анализа - не удалось определить блюдо",
                "portion_options": [],
                "nutrition_per_100g": {
                    "calories": 0,
                    "protein": 0,
                    "fat": 0,
                    "carbs": 0
                }
            }


# Global service instance
langgraph_service = LangGraphService()
