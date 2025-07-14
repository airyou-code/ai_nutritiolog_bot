import logging
import hashlib
from typing import Dict, List, Optional, Tuple

from bot.services.openai_service import openai_service
from bot.services.redis_service import redis_service

logger = logging.getLogger(__name__)


class NutritionAnalyzer:
    """Service for nutrition analysis and calculations"""
    
    def __init__(self):
        self.openai_service = openai_service
        self.redis_service = redis_service
    
    async def analyze_food_from_photo(
        self, 
        image_data: bytes, 
        user_description: Optional[str] = None
    ) -> Dict:
        """Analyze food from photo with caching"""
        
        # Create cache key from image hash
        image_hash = hashlib.md5(image_data).hexdigest()
        cache_key = f"photo_{image_hash}"
        
        if user_description:
            desc_hash = hashlib.md5(user_description.encode()).hexdigest()[:8]
            cache_key += f"_{desc_hash}"
        
        # Try to get from cache first
        cached_result = await self.redis_service.get_cached_food_analysis(cache_key)
        if cached_result:
            logger.info(f"Using cached food analysis for key: {cache_key}")
            return cached_result
        
        try:
            # Analyze with OpenAI
            analysis = await self.openai_service.analyze_food_photo(
                image_data, 
                user_description
            )
            
            # Process and validate analysis
            processed_analysis = self._process_analysis_result(analysis)
            
            # Cache the result
            await self.redis_service.cache_food_analysis(cache_key, processed_analysis)
            
            return processed_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing food photo: {e}")
            raise
    
    async def analyze_food_from_text(
        self, 
        food_description: str, 
        portion_info: Optional[str] = None
    ) -> Dict:
        """Analyze food from text description with caching"""
        
        # Create cache key from description
        desc_text = f"{food_description}_{portion_info or ''}"
        cache_key = f"text_{hashlib.md5(desc_text.encode()).hexdigest()}"
        
        # Try to get from cache first
        cached_result = await self.redis_service.get_cached_food_analysis(cache_key)
        if cached_result:
            logger.info(f"Using cached food analysis for key: {cache_key}")
            return cached_result
        
        try:
            # Analyze with OpenAI
            analysis = await self.openai_service.analyze_food_text(
                food_description, 
                portion_info
            )
            
            # Process and validate analysis
            processed_analysis = self._process_analysis_result(analysis)
            
            # Cache the result
            await self.redis_service.cache_food_analysis(cache_key, processed_analysis)
            
            return processed_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing food text: {e}")
            raise
    
    def calculate_nutrition_for_portion(
        self, 
        nutrition_per_100g: Dict, 
        portion_weight: float
    ) -> Dict:
        """Calculate total nutrition for specific portion weight"""
        
        multiplier = portion_weight / 100.0
        
        return {
            "total_calories": round(nutrition_per_100g["calories"] * multiplier, 1),
            "total_protein": round(nutrition_per_100g["protein"] * multiplier, 1),
            "total_fat": round(nutrition_per_100g["fat"] * multiplier, 1),
            "total_carbs": round(nutrition_per_100g["carbs"] * multiplier, 1),
            "portion_weight": portion_weight
        }
    
    def create_portion_options_with_nutrition(
        self, 
        analysis: Dict
    ) -> List[Dict]:
        """Create portion options with calculated nutrition"""
        
        portion_options = []
        nutrition_per_100g = analysis["nutrition_per_100g"]
        
        for option in analysis["portion_options"]:
            portion_nutrition = self.calculate_nutrition_for_portion(
                nutrition_per_100g, 
                option["weight"]
            )
            
            portion_options.append({
                "size": option["size"],
                "weight": option["weight"],
                "description": option["description"],
                "nutrition": portion_nutrition
            })
        
        return portion_options
    
    def calculate_daily_nutrition_percentage(
        self, 
        current_nutrition: Dict, 
        daily_goals: Optional[Dict] = None
    ) -> Dict:
        """Calculate percentage of daily nutrition goals achieved"""
        
        if not daily_goals:
            # Use average daily requirements
            daily_goals = {
                "calories": 2000,
                "protein": 150,
                "fat": 65,
                "carbs": 250
            }
        
        percentages = {}
        for nutrient in ["calories", "protein", "fat", "carbs"]:
            current_key = f"total_{nutrient}"
            goal_key = f"daily_{nutrient}_goal"
            
            current_value = current_nutrition.get(current_key, 0)
            goal_value = daily_goals.get(goal_key) or daily_goals.get(nutrient, 1)
            
            percentages[f"{nutrient}_percentage"] = round(
                (current_value / goal_value) * 100, 1
            )
        
        return percentages
    
    def _process_analysis_result(self, analysis: Dict) -> Dict:
        """Process and validate analysis result from OpenAI"""
        
        # Ensure all required fields exist with defaults
        processed = {
            "food_name": analysis.get("food_name", "Неизвестное блюдо"),
            "description": analysis.get("description", "Описание недоступно"),
            "portion_options": [],
            "nutrition_per_100g": {
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0
            }
        }
        
        # Validate and process nutrition per 100g
        nutrition = analysis.get("nutrition_per_100g", {})
        for nutrient in ["calories", "protein", "fat", "carbs"]:
            value = nutrition.get(nutrient, 0)
            # Ensure reasonable ranges
            if nutrient == "calories":
                processed["nutrition_per_100g"][nutrient] = max(0, min(value, 900))
            else:  # protein, fat, carbs
                processed["nutrition_per_100g"][nutrient] = max(0, min(value, 100))
        
        # Validate and process portion options
        portions = analysis.get("portion_options", [])
        if not portions:
            # Default portions if none provided
            portions = [
                {"size": "small", "weight": 150, "description": "маленькая порция"},
                {"size": "medium", "weight": 250, "description": "средняя порция"},
                {"size": "large", "weight": 350, "description": "большая порция"}
            ]
        
        for portion in portions:
            if isinstance(portion, dict) and "size" in portion and "weight" in portion:
                processed["portion_options"].append({
                    "size": portion["size"],
                    "weight": max(50, min(portion["weight"], 1000)),  # 50g - 1kg range
                    "description": portion.get("description", f"{portion['size']} порция")
                })
        
        # Ensure we have at least one portion option
        if not processed["portion_options"]:
            processed["portion_options"] = [
                {"size": "medium", "weight": 250, "description": "средняя порция"}
            ]
        
        return processed
    
    def format_nutrition_summary(self, nutrition: Dict) -> str:
        """Format nutrition data as readable text"""
        
        return (
            f"🔥 Калории: {nutrition.get('total_calories', 0):.1f} ккал\n"
            f"🥩 Белки: {nutrition.get('total_protein', 0):.1f} г\n"
            f"🥑 Жиры: {nutrition.get('total_fat', 0):.1f} г\n"
            f"🍞 Углеводы: {nutrition.get('total_carbs', 0):.1f} г"
        )
    
    def format_daily_summary(self, daily_nutrition: Dict, goals: Optional[Dict] = None) -> str:
        """Format daily nutrition summary"""
        
        summary = "📊 Сегодня съедено:\n\n"
        summary += self.format_nutrition_summary(daily_nutrition)
        summary += f"\n🍽 Приемов пищи: {daily_nutrition.get('entries_count', 0)}"
        
        if goals:
            percentages = self.calculate_daily_nutrition_percentage(daily_nutrition, goals)
            summary += "\n\n📈 Выполнение целей:\n"
            summary += f"🔥 Калории: {percentages.get('calories_percentage', 0):.1f}%\n"
            summary += f"🥩 Белки: {percentages.get('protein_percentage', 0):.1f}%\n"
            summary += f"🥑 Жиры: {percentages.get('fat_percentage', 0):.1f}%\n"
            summary += f"🍞 Углеводы: {percentages.get('carbs_percentage', 0):.1f}%"
        
        return summary


# Global service instance
nutrition_analyzer = NutritionAnalyzer() 