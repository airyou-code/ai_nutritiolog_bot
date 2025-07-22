import hashlib
import logging

from bot.services.redis_service import redis_service

logger = logging.getLogger(__name__)


class NutritionAnalyzer:
    """Service for nutrition analysis and calculations"""

    def __init__(self):
        self.redis_service = redis_service
        # Import here to avoid circular imports
        from bot.services.langgraph_service import langgraph_service

        self.langgraph_service = langgraph_service

    async def analyze_food_from_photo(
        self, image_data: bytes, user_description: str | None = None
    ) -> dict:
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
            # Analyze with LangGraph
            analysis = await self.langgraph_service.analyze_food_photo_with_langgraph(
                image_data, user_description
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
        self, food_description: str, portion_info: str | None = None
    ) -> dict:
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
            # Analyze with LangGraph
            analysis = await self.langgraph_service.analyze_food_text_with_langgraph(
                food_description, portion_info
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
        self, nutrition_per_100g: dict, portion_weight: float
    ) -> dict:
        """Calculate total nutrition for specific portion weight"""

        multiplier = portion_weight / 100.0

        return {
            "total_calories": round(nutrition_per_100g["calories"] * multiplier, 1),
            "total_protein": round(nutrition_per_100g["protein"] * multiplier, 1),
            "total_fat": round(nutrition_per_100g["fat"] * multiplier, 1),
            "total_carbs": round(nutrition_per_100g["carbs"] * multiplier, 1),
            "portion_weight": portion_weight,
        }

    def create_portion_options_with_nutrition(self, analysis: dict) -> list[dict]:
        """Create portion options with calculated nutrition"""

        portion_options = []
        nutrition_per_100g = analysis["nutrition_per_100g"]

        for option in analysis["portion_options"]:
            portion_nutrition = self.calculate_nutrition_for_portion(
                nutrition_per_100g, option["weight"]
            )

            portion_options.append(
                {
                    "size": option["size"],
                    "weight": option["weight"],
                    "description": option["description"],
                    "nutrition": portion_nutrition,
                }
            )

        return portion_options

    def calculate_daily_nutrition_percentage(
        self, current_nutrition: dict, daily_goals: dict | None = None
    ) -> dict:
        """Calculate percentage of daily nutrition goals achieved"""

        if not daily_goals:
            # Use average daily requirements
            daily_goals = {"calories": 2000, "protein": 150, "fat": 65, "carbs": 250}

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

    def _process_analysis_result(self, analysis: dict) -> dict:
        """Process and validate analysis result from OpenAI"""

        # Check if AI determined this is not food
        if not analysis.get("is_food"):
            logger.info("AI determined this is not food, returning not_food structure")
            return {
                "is_food": False,
                "food_name": "",
                "description": analysis.get(
                    "description", "На изображении не обнаружена еда"
                ),
                "portion_options": [],
                "nutrition_per_100g": {
                    "calories": 0,
                    "protein": 0,
                    "fat": 0,
                    "carbs": 0,
                },
            }

        # Ensure all required fields exist with defaults
        processed = {
            "is_food": True,
            "food_name": analysis.get("food_name", "Неизвестное блюдо"),
            "description": analysis.get("description", "Описание недоступно"),
            "portion_options": [],
            "nutrition_per_100g": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
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
            # Generate smart default portions based on food name
            portions = self._generate_smart_default_portions(processed["food_name"])

        for portion in portions:
            if isinstance(portion, dict) and "size" in portion and "weight" in portion:
                processed["portion_options"].append(
                    {
                        "size": portion["size"],
                        "weight": max(
                            50, min(portion["weight"], 1000)
                        ),  # 50g - 1kg range
                        "description": portion.get(
                            "description", f"{portion['size']} порция"
                        ),
                    }
                )

        # Ensure we have at least one portion option
        if not processed["portion_options"]:
            processed["portion_options"] = [
                {"size": "exact", "weight": 200, "description": "стандартная порция"}
            ]

        return processed

    def _generate_smart_default_portions(self, food_name: str) -> list[dict]:
        """Generate smart default portions based on food name"""

        food_lower = food_name.lower()

        # Check if food name contains specific quantity
        import re

        numbers = re.findall(r"\d+", food_name)

        # Fruits and vegetables
        if any(fruit in food_lower for fruit in ["банан", "яблок", "апельсин", "груш"]):
            if numbers:  # If specific quantity mentioned
                qty = int(numbers[0])
                weight = qty * 120  # average fruit weight
                return [{"size": "exact", "weight": weight, "description": f"{qty} шт"}]
            else:  # Generic fruit
                return [
                    {"size": "small", "weight": 120, "description": "1 штука"},
                    {"size": "medium", "weight": 240, "description": "2 штуки"},
                    {"size": "large", "weight": 360, "description": "3 штуки"},
                ]

        # Bread and bakery
        elif any(
            bread in food_lower for bread in ["хлеб", "булочк", "батон", "кусочек"]
        ):
            if "кусочек" in food_lower or numbers:
                return [{"size": "exact", "weight": 30, "description": "кусочек"}]
            else:
                return [
                    {"size": "small", "weight": 30, "description": "1 кусочек"},
                    {"size": "medium", "weight": 60, "description": "2 кусочка"},
                    {"size": "large", "weight": 90, "description": "3 кусочка"},
                ]

        # Drinks
        elif any(
            drink in food_lower for drink in ["стакан", "кружк", "чашк", "бутылк"]
        ):
            if "стакан" in food_lower:
                return [{"size": "exact", "weight": 250, "description": "стакан"}]
            elif "кружк" in food_lower or "чашк" in food_lower:
                return [{"size": "exact", "weight": 300, "description": "кружка"}]
            elif "бутылк" in food_lower:
                return [{"size": "exact", "weight": 500, "description": "бутылка"}]

        # Soups and liquid dishes
        elif any(soup in food_lower for soup in ["суп", "борщ", "щи", "похлебк"]):
            if "тарелк" in food_lower:
                return [{"size": "exact", "weight": 300, "description": "тарелка"}]
            else:
                return [
                    {"size": "small", "weight": 200, "description": "полтарелки"},
                    {"size": "medium", "weight": 300, "description": "тарелка"},
                    {"size": "large", "weight": 400, "description": "большая тарелка"},
                ]

        # Porridge and cereals
        elif any(cereal in food_lower for cereal in ["каш", "овсянк", "гречк", "рис"]):
            if "тарелк" in food_lower:
                return [{"size": "exact", "weight": 200, "description": "тарелка каши"}]
            else:
                return [
                    {"size": "small", "weight": 150, "description": "маленькая порция"},
                    {"size": "medium", "weight": 200, "description": "средняя порция"},
                    {"size": "large", "weight": 250, "description": "большая порция"},
                ]

        # Default case - check if specific quantity mentioned
        elif numbers:
            # If we found numbers but don't know the food type, use moderate weight
            qty = int(numbers[0])
            weight = qty * 100  # 100g per unit as default
            return [{"size": "exact", "weight": weight, "description": f"{qty} порций"}]

        else:
            # Generic unknown food - provide options
            return [
                {"size": "small", "weight": 100, "description": "маленькая порция"},
                {"size": "medium", "weight": 200, "description": "средняя порция"},
                {"size": "large", "weight": 300, "description": "большая порция"},
            ]

    def format_nutrition_summary(self, nutrition: dict) -> str:
        """Format nutrition data as readable text"""

        return (
            f"🔥 Калории: {nutrition.get('total_calories', 0):.1f} ккал\n"
            f"🥩 Белки: {nutrition.get('total_protein', 0):.1f} г\n"
            f"🥑 Жиры: {nutrition.get('total_fat', 0):.1f} г\n"
            f"🍞 Углеводы: {nutrition.get('total_carbs', 0):.1f} г"
        )

    def format_daily_summary(
        self, daily_nutrition: dict, goals: dict | None = None
    ) -> str:
        """Format daily nutrition summary"""

        summary = "📊 Сегодня съедено:\n\n"
        summary += self.format_nutrition_summary(daily_nutrition)
        summary += f"\n🍽 Приемов пищи: {daily_nutrition.get('entries_count', 0)}"

        if goals:
            percentages = self.calculate_daily_nutrition_percentage(
                daily_nutrition, goals
            )
            summary += "\n\n📈 Выполнение целей:\n"
            summary += f"🔥 Калории: {percentages.get('calories_percentage', 0):.1f}%\n"
            summary += f"🥩 Белки: {percentages.get('protein_percentage', 0):.1f}%\n"
            summary += f"🥑 Жиры: {percentages.get('fat_percentage', 0):.1f}%\n"
            summary += f"🍞 Углеводы: {percentages.get('carbs_percentage', 0):.1f}%"

        return summary


# Global service instance
nutrition_analyzer = NutritionAnalyzer()
