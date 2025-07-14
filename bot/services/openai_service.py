import logging
from typing import AsyncGenerator, Optional, Dict, Any
import json
import base64
from io import BytesIO

import openai
from openai import AsyncOpenAI
from PIL import Image

from bot.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def analyze_food_photo(
        self, 
        image_data: bytes, 
        user_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze food photo and return nutrition information"""
        
        try:
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
            
            # Prepare prompt
            prompt = self._get_food_analysis_prompt(user_description)
            
            # Make API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
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
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            # Parse response
            content = response.choices[0].message.content
            return self._parse_food_analysis_response(content)
            
        except Exception as e:
            logger.error(f"Error analyzing food photo: {e}")
            raise
    
    async def analyze_food_text(
        self, 
        food_description: str, 
        portion_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze food from text description"""
        
        try:
            prompt = self._get_text_analysis_prompt(food_description, portion_info)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            return self._parse_food_analysis_response(content)
            
        except Exception as e:
            logger.error(f"Error analyzing food text: {e}")
            raise
    
    async def get_nutrition_advice_stream(
        self, 
        user_question: str, 
        user_nutrition_data: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """Get nutrition advice with streaming response"""
        
        try:
            prompt = self._get_nutrition_advice_prompt(user_question, user_nutrition_data)
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты профессиональный нутрициолог. Отвечай на русском языке, дай полезные и научно обоснованные советы по питанию."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.7,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Error getting nutrition advice: {e}")
            yield f"Извините, произошла ошибка при получении совета: {str(e)}"
    
    def _get_food_analysis_prompt(self, user_description: Optional[str] = None) -> str:
        """Get prompt for food photo analysis"""
        
        base_prompt = """
        Проанализируй это изображение еды и верни результат в формате JSON:

        {
            "food_name": "название блюда",
            "description": "краткое описание состава",
            "portion_options": [
                {"size": "small", "weight": 150, "description": "маленькая порция"},
                {"size": "medium", "weight": 250, "description": "средняя порция"}, 
                {"size": "large", "weight": 350, "description": "большая порция"}
            ],
            "nutrition_per_100g": {
                "calories": калории_на_100г,
                "protein": белки_на_100г,
                "fat": жиры_на_100г,
                "carbs": углеводы_на_100г
            }
        }
        
        Будь точным в расчетах БЖУ. Если не можешь точно определить, укажи примерные значения для похожих блюд.
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

        Формат ответа:
        {
            "food_name": "название блюда",
            "description": "краткое описание состава",
            "portion_options": [
                {"size": "small", "weight": вес_в_граммах, "description": "описание"},
                {"size": "medium", "weight": вес_в_граммах, "description": "описание"},
                {"size": "large", "weight": вес_в_граммах, "description": "описание"}
            ],
            "nutrition_per_100g": {
                "calories": калории_на_100г,
                "protein": белки_на_100г,
                "fat": жиры_на_100г,
                "carbs": углеводы_на_100г
            }
        }
        
        Если пользователь указал конкретный вес порции, адаптируй варианты под это.
        """
        
        return prompt
    
    def _get_nutrition_advice_prompt(self, user_question: str, user_nutrition_data: Optional[Dict] = None) -> str:
        """Get prompt for nutrition advice"""
        
        prompt = f"Вопрос пользователя: {user_question}\n\n"
        
        if user_nutrition_data:
            prompt += "Данные о питании пользователя сегодня:\n"
            prompt += f"- Калории: {user_nutrition_data.get('total_calories', 0):.1f} ккал\n"
            prompt += f"- Белки: {user_nutrition_data.get('total_protein', 0):.1f} г\n"
            prompt += f"- Жиры: {user_nutrition_data.get('total_fat', 0):.1f} г\n"
            prompt += f"- Углеводы: {user_nutrition_data.get('total_carbs', 0):.1f} г\n"
            prompt += f"- Количество приемов пищи: {user_nutrition_data.get('entries_count', 0)}\n\n"
        
        prompt += "Дай полезный совет с учетом этой информации."
        
        return prompt
    
    def _parse_food_analysis_response(self, content: str) -> Dict[str, Any]:
        """Parse food analysis response from OpenAI"""
        
        try:
            # Try to extract JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = content[start_idx:end_idx]
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            logger.error(f"Response content: {content}")
            
            # Return default structure if parsing fails
            return {
                "food_name": "Неизвестное блюдо",
                "description": content[:200] + "..." if len(content) > 200 else content,
                "portion_options": [
                    {"size": "small", "weight": 150, "description": "маленькая порция"},
                    {"size": "medium", "weight": 250, "description": "средняя порция"},
                    {"size": "large", "weight": 350, "description": "большая порция"}
                ],
                "nutrition_per_100g": {
                    "calories": 200,
                    "protein": 10,
                    "fat": 10,
                    "carbs": 25
                }
            }


# Global service instance
openai_service = OpenAIService() 