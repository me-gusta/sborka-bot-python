import os
import logging
from typing import Optional, List
from jinja2 import Template
from datetime import datetime

from ..database import get_session, Message, Summarization, User
from .ai_service import AIService

logger = logging.getLogger(__name__)

# Content directory path
CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "content")


class SummarizationService:
    """Service for summarizing conversation history."""
    
    # Summarize after these many message pairs (user + assistant)
    FIRST_SUMMARIZATION_THRESHOLD = 3
    REGULAR_SUMMARIZATION_THRESHOLD = 10
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        logger.info("SummarizationService initialized")
    
    def _load_summarization_prompt(self) -> str:
        """Load the summarization prompt template."""
        prompt_path = os.path.join(CONTENT_DIR, "summarization.txt")
        logger.debug(f"Loading summarization prompt from: {prompt_path}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _get_message_count(self, user_id: int, sphere: str) -> int:
        """Get the count of message pairs for a user in a specific sphere."""
        with get_session() as session:
            count = session.query(Message).filter(
                Message.user_id == user_id,
                Message.sphere == sphere,
                Message.role == "user"
            ).count()
            logger.debug(f"Message pair count for user {user_id} in {sphere}: {count}")
            return count
    
    def _get_last_summarization(self, user_id: int, sphere: str) -> Optional[Summarization]:
        """Get the most recent summarization for a user and sphere."""
        with get_session() as session:
            summarization = session.query(Summarization).filter(
                Summarization.user_id == user_id,
                Summarization.sphere == sphere
            ).order_by(Summarization.created_at.desc()).first()
            
            if summarization:
                logger.debug(f"Found last summarization for user {user_id} in {sphere}")
            else:
                logger.debug(f"No summarization found for user {user_id} in {sphere}")
            
            return summarization
    
    def get_last_summarization_text(self, user_id: int, sphere: str) -> str:
        """Get the text of the last summarization, or 'no data' if none exists."""
        summarization = self._get_last_summarization(user_id, sphere)
        if summarization:
            return summarization.text
        return "no data"
    
    def _get_messages_since_last_summarization(self, user_id: int, sphere: str) -> List[Message]:
        """Get all messages since the last summarization."""
        with get_session() as session:
            last_sum = self._get_last_summarization(user_id, sphere)
            
            query = session.query(Message).filter(
                Message.user_id == user_id,
                Message.sphere == sphere
            )
            
            if last_sum:
                query = query.filter(Message.created_at > last_sum.created_at)
            
            messages = query.order_by(Message.created_at.asc()).all()
            logger.debug(f"Found {len(messages)} messages since last summarization for user {user_id} in {sphere}")
            
            # Detach messages from session before returning
            return [
                Message(
                    id=m.id,
                    user_id=m.user_id,
                    sphere=m.sphere,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at
                ) for m in messages
            ]
    
    def should_summarize(self, user_id: int, sphere: str) -> bool:
        """Check if summarization should be performed."""
        messages = self._get_messages_since_last_summarization(user_id, sphere)
        user_messages = [m for m in messages if m.role == "user"]
        count = len(user_messages)
        
        # Check if we have an existing summarization
        has_previous = self._get_last_summarization(user_id, sphere) is not None
        
        if has_previous:
            should = count >= self.REGULAR_SUMMARIZATION_THRESHOLD
        else:
            should = count >= self.FIRST_SUMMARIZATION_THRESHOLD
        
        logger.info(f"Summarization check for user {user_id} in {sphere}: "
                   f"count={count}, has_previous={has_previous}, should_summarize={should}")
        return should
    
    async def summarize(self, user_id: int, sphere: str) -> Optional[str]:
        """
        Perform summarization for a user's conversation in a specific sphere.
        
        Args:
            user_id: The user's database ID
            sphere: The sphere to summarize (soul, body, business)
            
        Returns:
            The summarization text, or None if summarization wasn't needed
        """
        logger.info(f"Starting summarization for user {user_id} in sphere {sphere}")
        
        if not self.should_summarize(user_id, sphere):
            logger.info("Summarization not needed at this time")
            return None
        
        try:
            # Get messages to summarize
            messages = self._get_messages_since_last_summarization(user_id, sphere)
            
            if not messages:
                logger.warning("No messages to summarize")
                return None
            
            # Build history string
            history_lines = []
            for msg in messages:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg.content}")
            history = "\n".join(history_lines)
            
            # Load and render prompt template
            prompt_template = self._load_summarization_prompt()
            template = Template(prompt_template)
            prompt = template.render(history=history)
            
            logger.info("Sending summarization request to AI")
            summary_text = await self.ai_service.generate_response(prompt)
            
            # Save summarization to database
            with get_session() as session:
                summarization = Summarization(
                    user_id=user_id,
                    sphere=sphere,
                    text=summary_text,
                    created_at=datetime.utcnow()
                )
                session.add(summarization)
            
            logger.info(f"Summarization saved for user {user_id} in sphere {sphere}")
            return summary_text
            
        except Exception as e:
            logger.error(f"Error during summarization: {e}", exc_info=True)
            raise


