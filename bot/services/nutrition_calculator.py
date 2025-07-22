import logging

from bot.database.models.user import TelegramUser

logger = logging.getLogger(__name__)


class NutritionCalculator:
    """Service for calculating personalized nutrition requirements"""

    # Activity level multipliers for TDEE calculation
    ACTIVITY_MULTIPLIERS = {
        "sedentary": 1.2,  # Малоподвижный (офисная работа, нет физической активности)
        "lightly_active": 1.375,  # Легкая активность (легкие упражнения 1-3 дня в неделю)
        "moderately_active": 1.55,  # Умеренная активность (упражнения 3-5 дней в неделю)
        "very_active": 1.725,  # Высокая активность (тяжелые упражнения 6-7 дней в неделю)
        "extremely_active": 1.9,  # Экстремальная активность (2 раза в день, очень тяжелые тренировки)
    }

    # Goal-based calorie adjustments
    GOAL_ADJUSTMENTS = {
        "weight_loss": -500,  # Дефицит 500 ккал для похудения (~0.5 кг в неделю)
        "weight_gain": +500,  # Профицит 500 ккал для набора массы (~0.5 кг в неделю)
        "maintain_weight": 0,  # Поддержание веса
    }

    def calculate_bmr(self, user: TelegramUser) -> float | None:
        """
        Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation

        For men: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) + 5
        For women: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) - 161
        """
        if not all([user.weight, user.height, user.age, user.gender]):
            return None

        bmr = 10 * user.weight + 6.25 * user.height - 5 * user.age

        if user.gender == "male":
            bmr += 5
        elif user.gender == "female":
            bmr -= 161
        else:
            return None

        return round(bmr, 0)

    def calculate_tdee(self, user: TelegramUser) -> float | None:
        """Calculate Total Daily Energy Expenditure"""
        bmr = self.calculate_bmr(user)
        if not bmr or not user.activity_level:
            return None

        activity_multiplier = self.ACTIVITY_MULTIPLIERS.get(user.activity_level)
        if not activity_multiplier:
            return None

        tdee = bmr * activity_multiplier
        return round(tdee, 0)

    def calculate_target_calories(self, user: TelegramUser) -> float | None:
        """Calculate target daily calories based on goal"""
        tdee = self.calculate_tdee(user)
        if not tdee or not user.goal:
            return None

        goal_adjustment = self.GOAL_ADJUSTMENTS.get(user.goal, 0)
        target_calories = tdee + goal_adjustment

        # Ensure minimum calories (not below 1200 for women, 1500 for men)
        min_calories = 1200 if user.gender == "female" else 1500
        target_calories = max(target_calories, min_calories)

        return round(target_calories, 0)

    def calculate_macros(self, user: TelegramUser) -> dict[str, float] | None:
        """
        Calculate recommended macronutrients based on goal

        General recommendations:
        - Protein: 1.6-2.2g per kg body weight (higher for muscle gain)
        - Fat: 20-35% of total calories
        - Carbs: Remaining calories
        """
        target_calories = self.calculate_target_calories(user)
        if not target_calories or not user.weight:
            return None

        # Protein calculation based on goal
        if user.goal == "weight_gain":
            protein_per_kg = 2.2  # Higher protein for muscle gain
        elif user.goal == "weight_loss":
            protein_per_kg = 2.0  # Higher protein to preserve muscle during weight loss
        else:
            protein_per_kg = 1.8  # Maintenance

        protein_grams = round(user.weight * protein_per_kg, 1)
        protein_calories = protein_grams * 4

        # Fat calculation (25% of calories for balanced approach)
        fat_calories = target_calories * 0.25
        fat_grams = round(fat_calories / 9, 1)

        # Carbs calculation (remaining calories)
        carbs_calories = target_calories - protein_calories - fat_calories
        carbs_grams = round(carbs_calories / 4, 1)

        return {
            "calories": target_calories,
            "protein": protein_grams,
            "fat": fat_grams,
            "carbs": carbs_grams,
            "protein_percent": round((protein_calories / target_calories) * 100, 1),
            "fat_percent": round((fat_calories / target_calories) * 100, 1),
            "carbs_percent": round((carbs_calories / target_calories) * 100, 1),
        }

    def get_bmi_category(self, bmi: float) -> tuple[str, str]:
        """Get BMI category and description"""
        if bmi < 18.5:
            return "underweight", "Недостаточный вес"
        elif 18.5 <= bmi < 25:
            return "normal", "Нормальный вес"
        elif 25 <= bmi < 30:
            return "overweight", "Избыточный вес"
        elif 30 <= bmi < 35:
            return "obese_1", "Ожирение I степени"
        elif 35 <= bmi < 40:
            return "obese_2", "Ожирение II степени"
        else:
            return "obese_3", "Ожирение III степени"

    def format_user_profile(self, user: TelegramUser) -> str:
        """Format user profile information"""
        if not user.has_complete_profile:
            return "❌ Профиль не заполнен"

        # Basic info
        gender_emoji = "👨" if user.gender == "male" else "👩"
        gender_text = "Мужской" if user.gender == "male" else "Женский"

        # Activity level
        activity_texts = {
            "sedentary": "Малоподвижный",
            "lightly_active": "Легкая активность",
            "moderately_active": "Умеренная активность",
            "very_active": "Высокая активность",
            "extremely_active": "Экстремальная активность",
        }
        activity_text = activity_texts.get(user.activity_level, user.activity_level)

        # Goal
        goal_texts = {
            "weight_loss": "🎯 Похудение",
            "weight_gain": "💪 Набор мышечной массы",
            "maintain_weight": "⚖️ Поддержание веса",
        }
        goal_text = goal_texts.get(user.goal, user.goal)

        # BMI
        bmi = user.bmi
        bmi_category, bmi_desc = self.get_bmi_category(bmi) if bmi else ("", "")

        # Calculations
        macros = self.calculate_macros(user)

        profile_text = f"""
{gender_emoji} **Профиль пользователя**

📊 **Параметры:**
• Возраст: {user.age} лет
• Вес: {user.weight} кг
• Рост: {user.height} см
• Пол: {gender_text}

📈 **ИМТ:** {bmi} ({bmi_desc})

🏃‍♂️ **Активность:** {activity_text}
{goal_text}

💡 **Рекомендации на день:**
"""

        if macros:
            profile_text += f"""
🔥 **Калории:** {macros["calories"]:.0f} ккал
🥩 **Белки:** {macros["protein"]}г ({macros["protein_percent"]}%)
🥑 **Жиры:** {macros["fat"]}г ({macros["fat_percent"]}%)
🍞 **Углеводы:** {macros["carbs"]}г ({macros["carbs_percent"]}%)
"""
        else:
            profile_text += "\n❌ Не удалось рассчитать рекомендации"

        return profile_text

    def get_activity_levels(self) -> dict[str, str]:
        """Get available activity levels with descriptions"""
        return {
            "sedentary": "Малоподвижный (офисная работа)",
            "lightly_active": "Легкая активность (1-3 дня в неделю)",
            "moderately_active": "Умеренная активность (3-5 дней в неделю)",
            "very_active": "Высокая активность (6-7 дней в неделю)",
            "extremely_active": "Экстремальная активность (2 раза в день)",
        }

    def get_goals(self) -> dict[str, str]:
        """Get available goals with descriptions"""
        return {
            "weight_loss": "🎯 Похудение (-0.5 кг в неделю)",
            "maintain_weight": "⚖️ Поддержание веса",
            "weight_gain": "💪 Набор мышечной массы (+0.5 кг в неделю)",
        }


# Create global instance
nutrition_calculator = NutritionCalculator()
