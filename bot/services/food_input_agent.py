import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph

from bot.config.settings import settings
from bot.services.langgraph_service import langgraph_service

logger = logging.getLogger(__name__)


class FoodInputAnalysisState(MessagesState):
    """State for food input analysis"""

    user_input: str = ""
    is_food_related: bool = False
    analysis_type: str = ""  # "exact", "approximate", "need_clarification", "not_food"
    food_description: str = ""
    portion_info: str | None = None
    analysis_confidence: float = 0.0


class FoodInputAgent:
    """Smart agent for analyzing user food input and determining response strategy"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,  # Lower temperature for more consistent analysis
        )
        self._input_analyzer = None

    async def get_input_analyzer(self):
        """Get or create food input analyzer"""
        if self._input_analyzer is None:
            self._input_analyzer = await self._create_input_analyzer()
            logger.info("Created food input analyzer agent")

        return self._input_analyzer

    async def _create_input_analyzer(self):
        """Create specialized agent for analyzing food input"""

        async def analyze_input_node(state: FoodInputAnalysisState):
            """Analyze user input to determine if it's food-related and extract info"""
            user_input = state.get("user_input", "")

            system_prompt = self._get_input_analysis_prompt()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Пользователь написал: '{user_input}'"),
            ]

            response = await self.llm.ainvoke(messages)
            analysis = self._parse_input_analysis(response.content)

            return {
                **state,
                "is_food_related": analysis["is_food_related"],
                "analysis_type": analysis["analysis_type"],
                "food_description": analysis["food_description"],
                "portion_info": analysis.get("portion_info"),
                "analysis_confidence": analysis["confidence"],
            }

        # Build the graph
        workflow = StateGraph(FoodInputAnalysisState)
        workflow.add_node("analyzer", analyze_input_node)
        workflow.add_edge(START, "analyzer")
        workflow.add_edge("analyzer", END)

        return workflow.compile()

    def _get_input_analysis_prompt(self) -> str:
        """Get prompt for input analysis"""
        return """
        Ты строгий анализатор пользовательского ввода для приложения учета питания.
        
        ЗАДАЧА: Определить, описывает ли пользователь КОНКРЕТНУЮ ЕДУ или БЛЮДО.
        
        ОЧЕНЬ ВАЖНО: Отклоняй ВСЕ что НЕ является едой:
        - Приветствия: "привет", "здравствуй", "добрый день"
        - Вопросы: "как дела", "что делать", "помоги"
        - Общие фразы: "спасибо", "пока", "да", "нет"
        - Эмоции: "классно", "плохо", "хорошо"
        
        ПРИНИМАЙ только еду:
        - Названия блюд: "борщ", "салат цезарь", "куриная грудка"
        - Продукты: "банан", "молоко", "хлеб"
        - С количеством: "2 яблока", "стакан воды", "тарелка супа"
        
        Формат ответа JSON:
        {
            "is_food_related": true/false,
            "analysis_type": "exact"/"approximate"/"need_clarification"/"not_food",
            "food_description": "название еды или пустая строка",
            "portion_info": "информация о порции или null",
            "confidence": 0.0-1.0,
            "reasoning": "почему это еда или не еда"
        }
        
        Типы анализа:
        - "exact": точные измерения (200г курицы, 2 банана, стакан молока)
        - "approximate": нечеткие описания (большая порция, салат цезарь)
        - "need_clarification": слишком неясно (просто "еда", "что-то вкусное")
        - "not_food": НЕ связано с едой (привет, как дела, спасибо)
        
        ВНИМАНИЕ: Будь очень строгим! Лучше отклонить сомнительный случай.
        """

    def _parse_input_analysis(self, content: str) -> dict[str, Any]:
        """Parse input analysis response"""
        try:
            import json

            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found")

            json_str = content[start_idx:end_idx]
            result = json.loads(json_str)

            return {
                "is_food_related": result.get("is_food_related", False),
                "analysis_type": result.get("analysis_type", "not_food"),
                "food_description": result.get("food_description", ""),
                "portion_info": result.get("portion_info"),
                "confidence": result.get("confidence", 0.0),
            }

        except Exception as e:
            logger.error(f"Error parsing input analysis: {e}")
            # Fallback to regex-based analysis
            text = content.lower()
            is_food = any(word in text for word in ["еда", "блюдо", "съел", "поел"])

            return {
                "is_food_related": is_food,
                "analysis_type": "approximate" if is_food else "not_food",
                "food_description": content[:100],
                "portion_info": None,
                "confidence": 0.3,
            }

    async def analyze_user_input(self, user_input: str) -> dict[str, Any]:
        """Analyze user input and determine response strategy"""

        try:
            analyzer = await self.get_input_analyzer()

            # Create input state
            input_state = {"messages": [], "user_input": user_input.strip()}

            # Analyze input
            result = await analyzer.ainvoke(input_state)

            return {
                "is_food_related": result["is_food_related"],
                "analysis_type": result["analysis_type"],
                "food_description": result["food_description"],
                "portion_info": result["portion_info"],
                "confidence": result["analysis_confidence"],
                "original_input": user_input,
            }

        except Exception as e:
            logger.error(f"Error analyzing user input: {e}")

            # Fallback analysis
            return {
                "is_food_related": False,
                "analysis_type": "not_food",
                "food_description": "",
                "portion_info": None,
                "confidence": 0.0,
                "original_input": user_input,
            }

    async def process_food_input(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Process food input based on analysis type"""

        analysis_type = analysis["analysis_type"]
        food_description = analysis["food_description"]
        portion_info = analysis["portion_info"]

        try:
            if analysis_type == "exact":
                # For exact portions, analyze and create single option
                food_analysis = (
                    await langgraph_service.analyze_food_text_with_langgraph(
                        food_description, portion_info
                    )
                )
                # Ensure we have all required fields
                self._validate_food_analysis(food_analysis)
                return food_analysis

            elif analysis_type == "approximate":
                # For approximate descriptions, let AI generate multiple options
                food_analysis = (
                    await langgraph_service.analyze_food_text_with_langgraph(
                        food_description, portion_info
                    )
                )
                # Ensure we have all required fields
                self._validate_food_analysis(food_analysis)
                return food_analysis

            elif analysis_type == "need_clarification":
                # Ask for more details
                return {
                    "needs_clarification": True,
                    "food_name": "Неопределенное блюдо",
                    "description": f"На основе: '{analysis['original_input']}'",
                    "portion_options": [],
                    "clarification_message": self._get_clarification_message(
                        analysis["original_input"]
                    ),
                }

            else:  # not_food
                return {
                    "not_food": True,
                    "message": "Я не смог определить блюдо в твоем сообщении. Попробуй описать что ты ел более конкретно.",
                }

        except Exception as e:
            logger.error(f"Error processing food input: {e}")

            # Return not_food response on error
            return {
                "not_food": True,
                "message": f"Не удалось проанализировать '{food_description}' как еду. Попробуй описать конкретное блюдо.",
            }

    def _validate_food_analysis(self, analysis: dict[str, Any]) -> None:
        """Validate that food analysis has all required fields"""

        # Check if AI determined this is not food
        if not analysis.get("is_food"):
            raise ValueError("AI determined this is not food")

        required_fields = [
            "food_name",
            "description",
            "portion_options",
            "nutrition_per_100g",
        ]

        for field in required_fields:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")

        # Check if food_name is empty or generic
        food_name = analysis.get("food_name", "").strip()
        if not food_name or food_name.lower() in [
            "неизвестное блюдо",
            "неопределенное блюдо",
            "",
            "как дела",
        ]:
            raise ValueError("Invalid or empty food name")

        # Validate nutrition_per_100g structure
        nutrition = analysis["nutrition_per_100g"]
        required_nutrition_fields = ["calories", "protein", "fat", "carbs"]

        for field in required_nutrition_fields:
            if field not in nutrition:
                raise ValueError(f"Missing nutrition field: {field}")

        # Check if nutrition values are reasonable (not all zeros)
        total_nutrition = sum(
            nutrition.get(field, 0) for field in required_nutrition_fields
        )
        if total_nutrition == 0:
            raise ValueError("All nutrition values are zero - likely not food")

        # Validate portion_options structure
        if (
            not isinstance(analysis["portion_options"], list)
            or len(analysis["portion_options"]) == 0
        ):
            raise ValueError("portion_options must be a non-empty list")

    def _get_clarification_message(self, original_input: str) -> str:
        """Get clarification message for unclear input"""
        return f"""
🤔 Мне нужно больше деталей!

Ты написал: "{original_input}"

Попробуй описать более конкретно:
• Что именно ты ел?
• Какая была порция?

**Примеры хорошего описания:**
• "2 банана"
• "тарелка борща"
• "кусочек хлеба"
• "стакан молока"
• "салат цезарь большая порция"
"""


# Global service instance
food_input_agent = FoodInputAgent()
