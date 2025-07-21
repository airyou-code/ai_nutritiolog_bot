import logging
import re
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END

from bot.config.settings import settings
from bot.services.langgraph_service import langgraph_service

logger = logging.getLogger(__name__)


class FoodInputAnalysisState(MessagesState):
    """State for food input analysis"""
    user_input: str = ""
    is_food_related: bool = False
    analysis_type: str = ""  # "exact", "approximate", "need_clarification", "not_food"
    food_description: str = ""
    portion_info: Optional[str] = None
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
            
            # First, quick regex check for obvious food patterns
            is_food_likely = self._quick_food_detection(user_input)
            
            if not is_food_likely:
                # Ask LLM for deeper analysis
                system_prompt = self._get_input_analysis_prompt()
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Пользователь написал: '{user_input}'")
                ]
                
                response = await self.llm.ainvoke(messages)
                analysis = self._parse_input_analysis(response.content)
            else:
                # Skip LLM call for obvious food input
                analysis = {
                    "is_food_related": True,
                    "analysis_type": self._determine_portion_type(user_input),
                    "food_description": user_input,
                    "portion_info": self._extract_portion_info(user_input),
                    "confidence": 0.9
                }
            
            return {
                **state,
                "is_food_related": analysis["is_food_related"],
                "analysis_type": analysis["analysis_type"],
                "food_description": analysis["food_description"],
                "portion_info": analysis.get("portion_info"),
                "analysis_confidence": analysis["confidence"]
            }
        
        # Build the graph
        workflow = StateGraph(FoodInputAnalysisState)
        workflow.add_node("analyzer", analyze_input_node)
        workflow.add_edge(START, "analyzer")
        workflow.add_edge("analyzer", END)
        
        return workflow.compile()
    
    def _quick_food_detection(self, text: str) -> bool:
        """Quick regex-based food detection"""
        text_lower = text.lower().strip()
        
        # First check for obvious NON-food patterns (reject immediately)
        non_food_patterns = [
            r'^(привет|здравствуй|добрый день|доброе утро|добрый вечер|hi|hello).*',
            r'^(как дела|что делаешь|как поживаешь|как жизнь|что нового).*',
            r'^(спасибо|благодарю|thanks|пасиб).*',
            r'^(пока|до свидания|увидимся|bye).*',
            r'^(да|нет|не знаю|может быть|возможно)$',
            r'^(хорошо|плохо|нормально|отлично|классно|ужасно)$',
            r'^(помоги|помощь|что делать|не понимаю).*',
            r'^[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]*$',  # только символы
        ]
        
        for pattern in non_food_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # Common food-related keywords
        food_keywords = [
            # Meals
            'завтрак', 'обед', 'ужин', 'перекус', 'съел', 'ел', 'поел',
            # Food types
            'суп', 'борщ', 'каша', 'салат', 'мясо', 'курица', 'рыба', 'хлеб', 
            'молоко', 'творог', 'сыр', 'яйцо', 'картофель', 'рис', 'гречка',
            'макароны', 'паста', 'пицца', 'бургер', 'шаурма', 'роллы',
            # Fruits/vegetables
            'банан', 'яблок', 'апельсин', 'груш', 'помидор', 'огурец', 'морковь',
            # Drinks
            'чай', 'кофе', 'сок', 'молоко', 'кефир', 'компот',
            # Quantities
            'грамм', 'килограмм', 'литр', 'миллилитр', 'штук', 'кусочек', 'тарелка',
            'стакан', 'чашка', 'ложка', 'порция'
        ]
        
        # Check for food keywords
        for keyword in food_keywords:
            if keyword in text_lower:
                return True
        
        # Check for numbers + unit patterns (likely food with measurements)
        number_patterns = [
            r'\d+\s*г\b',  # граммы
            r'\d+\s*кг\b',  # килограммы 
            r'\d+\s*мл\b',  # миллилитры
            r'\d+\s*л\b',   # литры
            r'\d+\s*шт\b',  # штуки
            r'\d+\s*(банан|яблок|огурц|помидор)',  # количество фруктов/овощей
        ]
        
        for pattern in number_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _determine_portion_type(self, text: str) -> str:
        """Determine if portion is exact, approximate, or needs clarification"""
        text_lower = text.lower()
        
        # Exact portion indicators
        exact_patterns = [
            r'\d+\s*г\b',  # точный вес в граммах
            r'\d+\s*кг\b',  # точный вес в килограммах
            r'\d+\s*мл\b',  # точный объем в мл
            r'\d+\s*л\b',   # точный объем в литрах
            r'\d+\s*(банан|яблок|огурц|помидор|кусочек|штук)',  # точное количество
            r'(стакан|чашка|тарелка|кружка|бутылка)\s+(молока|воды|сока|чая|кофе|супа|борща)',  # конкретная емкость с жидкостью
        ]
        
        # Check for exact patterns
        for pattern in exact_patterns:
            if re.search(pattern, text_lower):
                return "exact"
        
        # Size indicators that are approximate
        size_indicators = ['маленьк', 'средн', 'больш', 'огромн', 'крошечн']
        for indicator in size_indicators:
            if indicator in text_lower:
                return "approximate"
        
        # Very vague descriptions need clarification
        vague_patterns = [
            r'^(еда|блюдо|что-то|немного|чуть-чуть)$',
            r'^[а-яё]{1,3}$',  # very short words
        ]
        
        for pattern in vague_patterns:
            if re.search(pattern, text_lower.strip()):
                return "need_clarification"
        
        # Default to approximate if it seems like food but no clear portion
        return "approximate"
    
    def _extract_portion_info(self, text: str) -> Optional[str]:
        """Extract portion information from text"""
        text_lower = text.lower()
        
        # Extract numbers with units
        patterns = {
            'weight': r'(\d+(?:\.\d+)?)\s*(г|грам|гр|кг|килограмм)',
            'volume': r'(\d+(?:\.\d+)?)\s*(мл|миллилитр|л|литр)',
            'pieces': r'(\d+(?:\.\d+)?)\s*(шт|штук|штуки|банан|яблок|огурц|помидор|кусочек|кусочка)',
            'containers': r'(стакан|чашка|тарелка|кружка|бутылка|миска)',
            'sizes': r'(маленьк|средн|больш|огромн|крошечн)\w*'
        }
        
        extracted_info = []
        
        for category, pattern in patterns.items():
            matches = re.findall(pattern, text_lower)
            if matches:
                if category in ['weight', 'volume', 'pieces']:
                    for match in matches:
                        if isinstance(match, tuple):
                            extracted_info.append(f"{match[0]}{match[1]}")
                        else:
                            extracted_info.append(match)
                else:
                    extracted_info.extend(matches)
        
        return ", ".join(extracted_info) if extracted_info else None
    
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
    
    def _parse_input_analysis(self, content: str) -> Dict[str, Any]:
        """Parse input analysis response"""
        try:
            import json
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found")
            
            json_str = content[start_idx:end_idx]
            result = json.loads(json_str)
            
            return {
                "is_food_related": result.get("is_food_related", False),
                "analysis_type": result.get("analysis_type", "not_food"),
                "food_description": result.get("food_description", ""),
                "portion_info": result.get("portion_info"),
                "confidence": result.get("confidence", 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error parsing input analysis: {e}")
            # Fallback to regex-based analysis
            text = content.lower()
            is_food = any(word in text for word in ['еда', 'блюдо', 'съел', 'поел'])
            
            return {
                "is_food_related": is_food,
                "analysis_type": "approximate" if is_food else "not_food", 
                "food_description": content[:100],
                "portion_info": None,
                "confidence": 0.3
            }
    
    async def analyze_user_input(self, user_input: str) -> Dict[str, Any]:
        """Analyze user input and determine response strategy"""
        
        try:
            analyzer = await self.get_input_analyzer()
            
            # Create input state
            input_state = {
                "messages": [],
                "user_input": user_input.strip()
            }
            
            # Analyze input
            result = await analyzer.ainvoke(input_state)
            
            return {
                "is_food_related": result["is_food_related"],
                "analysis_type": result["analysis_type"],
                "food_description": result["food_description"],
                "portion_info": result["portion_info"],
                "confidence": result["analysis_confidence"],
                "original_input": user_input
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
                "original_input": user_input
            }
    
    async def process_food_input(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Process food input based on analysis type"""
        
        analysis_type = analysis["analysis_type"]
        food_description = analysis["food_description"]
        portion_info = analysis["portion_info"]
        
        try:
            if analysis_type == "exact":
                # For exact portions, analyze and create single option
                food_analysis = await langgraph_service.analyze_food_text_with_langgraph(
                    food_description, portion_info
                )
                # Ensure we have all required fields
                self._validate_food_analysis(food_analysis)
                return food_analysis
                
            elif analysis_type == "approximate":
                # For approximate descriptions, let AI generate multiple options
                food_analysis = await langgraph_service.analyze_food_text_with_langgraph(
                    food_description, portion_info
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
                    "clarification_message": self._get_clarification_message(analysis["original_input"])
                }
            
            else:  # not_food
                return {
                    "not_food": True,
                    "message": "Я не смог определить блюдо в твоем сообщении. Попробуй описать что ты ел более конкретно."
                }
                
        except Exception as e:
            logger.error(f"Error processing food input: {e}")
            
            # Return not_food response on error
            return {
                "not_food": True,
                "message": f"Не удалось проанализировать '{food_description}' как еду. Попробуй описать конкретное блюдо."
            }
    
    def _validate_food_analysis(self, analysis: Dict[str, Any]) -> None:
        """Validate that food analysis has all required fields"""
        
        # Check if AI determined this is not food
        if analysis.get("is_food") == False:
            raise ValueError("AI determined this is not food")
        
        required_fields = ["food_name", "description", "portion_options", "nutrition_per_100g"]
        
        for field in required_fields:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if food_name is empty or generic
        food_name = analysis.get("food_name", "").strip()
        if not food_name or food_name.lower() in ["неизвестное блюдо", "неопределенное блюдо", "", "как дела"]:
            raise ValueError("Invalid or empty food name")
        
        # Validate nutrition_per_100g structure
        nutrition = analysis["nutrition_per_100g"]
        required_nutrition_fields = ["calories", "protein", "fat", "carbs"]
        
        for field in required_nutrition_fields:
            if field not in nutrition:
                raise ValueError(f"Missing nutrition field: {field}")
        
        # Check if nutrition values are reasonable (not all zeros)
        total_nutrition = sum(nutrition.get(field, 0) for field in required_nutrition_fields)
        if total_nutrition == 0:
            raise ValueError("All nutrition values are zero - likely not food")
        
        # Validate portion_options structure
        if not isinstance(analysis["portion_options"], list) or len(analysis["portion_options"]) == 0:
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