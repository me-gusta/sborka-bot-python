import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from ..database import get_session, User, Message
from ..services import AIService, SummarizationService
from ..utils import (
    get_or_create_user,
    build_sphere_prompt,
    detect_sphere_from_topic,
    get_sphere_by_thread,
    update_user_thread
)

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handler for chat messages with AI agents."""
    
    def __init__(self, ai_service: AIService, summarization_service: SummarizationService):
        self.ai_service = ai_service
        self.summarization_service = summarization_service
        logger.info("ChatHandler initialized")
    
    def _user_has_all_curators(self, telegram_id: int) -> bool:
        """Check if user has selected all curators."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            return all([
                user.selected_center,
                user.selected_business,
                user.selected_soul,
                user.selected_body
            ])
    
    def _get_user_curator(self, telegram_id: int, sphere: str) -> Optional[str]:
        """Get the curator selected for a specific sphere."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None
            
            if sphere == "center":
                return user.selected_center
            elif sphere == "business":
                return user.selected_business
            elif sphere == "soul":
                return user.selected_soul
            elif sphere == "body":
                return user.selected_body
            
            return None
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        message_text = update.message.text
        chat_id = update.effective_chat.id
        message_thread_id = update.message.message_thread_id
        
        logger.info(f"Received text message from user {telegram_id}: {message_text[:50]}...")
        logger.info(f"Chat ID: {chat_id}, Thread ID: {message_thread_id}")
        
        # Check if user has all curators selected
        if not self._user_has_all_curators(telegram_id):
            logger.warning(f"User {telegram_id} hasn't selected all curators yet")
            await update.message.reply_text(
                "Пожалуйста, сначала выберите наставников для всех сфер. "
                "Используйте команду /curators"
            )
            return
        
        # Detect sphere from topic name
        sphere = None
        
        # Try to get sphere from message thread topic
        if message_thread_id:
            # Try to get topic name from the message
            if update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
                topic_name = update.message.reply_to_message.forum_topic_created.name
                sphere = detect_sphere_from_topic(topic_name)
                if sphere:
                    # Update user's thread mapping
                    update_user_thread(telegram_id, sphere, message_thread_id, chat_id)
            
            # If not found from topic creation, try to get from stored mapping
            if not sphere:
                sphere = get_sphere_by_thread(telegram_id, chat_id, message_thread_id)
        
        # If no sphere detected and it's a direct message (not in topic)
        if not sphere and not message_thread_id:
            # Default to center for direct messages
            sphere = "center"
            logger.info("No thread ID, defaulting to center sphere")
        
        if not sphere:
            logger.warning(f"Could not detect sphere for message from user {telegram_id}")
            await update.message.reply_text(
                "Не удалось определить сферу для этого сообщения. "
                "Пожалуйста, убедитесь, что пишете в правильном топике."
            )
            return
        
        logger.info(f"Detected sphere: {sphere}")
        
        # Get curator for the sphere
        curator = self._get_user_curator(telegram_id, sphere)
        if not curator:
            logger.error(f"No curator found for sphere {sphere}")
            await update.message.reply_text("Ошибка: не найден куратор для этой сферы.")
            return
        
        logger.info(f"Using curator: {curator} for sphere: {sphere}")
        
        # Send typing action
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        try:
            # Get user from database
            user = get_or_create_user(telegram_id, username)
            
            # Build the prompt
            system_prompt = build_sphere_prompt(user.id, sphere, curator)
            
            # Generate AI response
            logger.info(f"Generating AI response for user {telegram_id} in sphere {sphere}")
            ai_response = await self.ai_service.generate_response(
                prompt=message_text,
                system_instruction=system_prompt
            )
            
            # Store both messages in database
            with get_session() as session:
                # Store user message
                user_msg = Message(
                    user_id=user.id,
                    sphere=sphere,
                    role="user",
                    content=message_text
                )
                session.add(user_msg)
                
                # Store assistant message
                assistant_msg = Message(
                    user_id=user.id,
                    sphere=sphere,
                    role="assistant",
                    content=ai_response
                )
                session.add(assistant_msg)
            
            logger.info(f"Stored messages for user {telegram_id} in sphere {sphere}")
            
            # Send the response
            await update.message.reply_text(ai_response)
            
            logger.info(f"Sent AI response to user {telegram_id}")
            
            # Check if summarization is needed
            try:
                await self.summarization_service.summarize(user.id, sphere)
            except Exception as e:
                logger.error(f"Error during summarization: {e}", exc_info=True)
                # Don't fail the whole request if summarization fails
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}", exc_info=True)
            await update.message.reply_text(
                f"Произошла ошибка при обработке сообщения: {str(e)}"
            )
    
    async def process_transcribed_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str
    ):
        """Process transcribed text from voice message."""
        # Create a modified update with the transcribed text
        # Then handle it like a regular text message
        
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        chat_id = update.effective_chat.id
        message_thread_id = update.message.message_thread_id if update.message else None
        
        logger.info(f"Processing transcribed text for user {telegram_id}: {text[:50]}...")
        
        # Check if user has all curators selected
        if not self._user_has_all_curators(telegram_id):
            logger.warning(f"User {telegram_id} hasn't selected all curators yet")
            await update.message.reply_text(
                "Пожалуйста, сначала выберите наставников для всех сфер. "
                "Используйте команду /curators"
            )
            return
        
        # Detect sphere from topic name
        sphere = None
        
        # Try to get sphere from message thread topic
        if message_thread_id:
            # Try to get topic name from the message
            if update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
                topic_name = update.message.reply_to_message.forum_topic_created.name
                sphere = detect_sphere_from_topic(topic_name)
                if sphere:
                    # Update user's thread mapping
                    update_user_thread(telegram_id, sphere, message_thread_id, chat_id)
            
            # If not found from topic creation, try to get from stored mapping
            if not sphere:
                sphere = get_sphere_by_thread(telegram_id, chat_id, message_thread_id)
        
        # If no sphere detected and it's a direct message (not in topic)
        if not sphere and not message_thread_id:
            sphere = "center"
            logger.info("No thread ID, defaulting to center sphere")
        
        if not sphere:
            logger.warning(f"Could not detect sphere for voice message from user {telegram_id}")
            await update.message.reply_text(
                "Не удалось определить сферу для этого сообщения. "
                "Пожалуйста, убедитесь, что пишете в правильном топике."
            )
            return
        
        logger.info(f"Detected sphere: {sphere}")
        
        # Get curator
        curator = self._get_user_curator(telegram_id, sphere)
        if not curator:
            await update.message.reply_text("Ошибка: не найден куратор для этой сферы.")
            return
        
        # Send typing action
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        try:
            user = get_or_create_user(telegram_id, username)
            
            # Build prompt and generate response
            system_prompt = build_sphere_prompt(user.id, sphere, curator)
            ai_response = await self.ai_service.generate_response(
                prompt=text,
                system_instruction=system_prompt
            )
            
            # Store messages
            with get_session() as session:
                user_msg = Message(
                    user_id=user.id,
                    sphere=sphere,
                    role="user",
                    content=text
                )
                session.add(user_msg)
                
                assistant_msg = Message(
                    user_id=user.id,
                    sphere=sphere,
                    role="assistant",
                    content=ai_response
                )
                session.add(assistant_msg)
            
            # Send response
            await update.message.reply_text(ai_response)
            
            # Check summarization
            try:
                await self.summarization_service.summarize(user.id, sphere)
            except Exception as e:
                logger.error(f"Error during summarization: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error processing transcribed text: {e}", exc_info=True)
            await update.message.reply_text(
                f"Произошла ошибка при обработке сообщения: {str(e)}"
            )


