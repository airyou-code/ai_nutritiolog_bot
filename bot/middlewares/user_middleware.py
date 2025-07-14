import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery, InlineQuery

from bot.database.connection import get_db_session
from bot.database.operations.user_ops import get_or_create_user, update_user_activity

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Middleware to handle user registration and activity tracking"""
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """Process user data for each update"""
        
        user = None
        
        # Extract user from different event types
        if isinstance(event, Update):
            # Handle Update object
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user
            elif event.inline_query:
                user = event.inline_query.from_user
        elif isinstance(event, Message):
            # Handle Message object directly
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            # Handle CallbackQuery object directly
            user = event.from_user
        elif isinstance(event, InlineQuery):
            # Handle InlineQuery object directly
            user = event.from_user
        
        if user and not user.is_bot:
            try:
                async with get_db_session() as session:
                    # Get or create user in database
                    db_user = await get_or_create_user(
                        session=session,
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        language_code=user.language_code
                    )
                    
                    # Update last activity
                    await update_user_activity(session, user.id)
                    
                    # Add user to handler data
                    data["db_user"] = db_user
                    data["user_id"] = user.id
                    
                    logger.debug(f"User {user.id} processed and added to data")
                    
            except Exception as e:
                logger.error(f"Error processing user {user.id}: {e}")
                # Continue without database user if error occurs
                data["db_user"] = None
                data["user_id"] = user.id if user else None
        
        # Call the handler
        return await handler(event, data) 