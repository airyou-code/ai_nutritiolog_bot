import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config.settings import settings
from bot.database.connection import close_db
from bot.services.redis_service import redis_service
from bot.services.langgraph_service import langgraph_service
from bot.middlewares.user_middleware import UserMiddleware

# Import all handlers
from bot.handlers import start, photo_analysis, text_input, diary, chat, profile, universal_food_input

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


async def on_startup():
    """Bot startup actions"""
    logger.info("Starting AI Nutrition Bot...")
    
    # Database tables should be created via Alembic migrations
    # Run: uv run alembic upgrade head
    logger.info("Database tables managed by Alembic migrations")
    
    # Initialize Redis
    try:
        await redis_service.connect()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        # Continue without Redis - it's optional
    
    # Initialize LangGraph service
    try:
        # Pre-initialize checkpointer to test Redis connection
        await langgraph_service.get_checkpointer()
        logger.info("LangGraph service initialized successfully")
    except Exception as e:
        logger.warning(f"LangGraph service initialization warning: {e}")
        # Continue - LangGraph will work with memory fallback
    
    logger.info("Bot startup completed")


async def on_shutdown():
    """Bot shutdown actions"""
    logger.info("Shutting down AI Nutrition Bot...")
    
    # Close database connections
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")
    
    # Close Redis connections
    try:
        await redis_service.disconnect()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")
    
    logger.info("Bot shutdown completed")


async def main():
    """Main bot function"""
    
    # Create bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Create dispatcher with memory storage for FSM
    dp = Dispatcher(storage=MemoryStorage())
    
    # Add middleware
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    
    # Include routers
    dp.include_router(start.router)
    dp.include_router(photo_analysis.router)
    dp.include_router(text_input.router)
    dp.include_router(diary.router)
    dp.include_router(chat.router)
    dp.include_router(profile.router)
    dp.include_router(universal_food_input.router)  # Must be last for universal text handling
    
    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"]
        )
    except Exception as e:
        logger.error(f"Error during polling: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
