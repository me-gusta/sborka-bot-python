import os
import json
import logging
from typing import Optional, List, Dict, Any
from jinja2 import Template

from ..database import get_session, User, Message, Summarization

logger = logging.getLogger(__name__)

# Content directory path
CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "content")


def get_or_create_user(telegram_id: int, username: Optional[str] = None) -> User:
    """Get existing user or create a new one."""
    logger.info(f"Getting or creating user with telegram_id: {telegram_id}")
    
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        
        if user:
            logger.info(f"Found existing user: {user.id}")
            if username and user.username != username:
                user.username = username
                logger.info(f"Updated username to: {username}")
            # Create a detached copy
            user_data = {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'is_onboarding': user.is_onboarding,
                'onboarding_step': user.onboarding_step,
                'onboarding_answers': user.onboarding_answers,
                'psychotype': user.psychotype,
                'recommended_center': user.recommended_center,
                'recommended_business': user.recommended_business,
                'recommended_soul': user.recommended_soul,
                'recommended_body': user.recommended_body,
                'selected_center': user.selected_center,
                'selected_business': user.selected_business,
                'selected_soul': user.selected_soul,
                'selected_body': user.selected_body,
                'chat_id': user.chat_id,
                'thread_soul': user.thread_soul,
                'thread_body': user.thread_body,
                'thread_business': user.thread_business,
                'thread_center': user.thread_center,
            }
        else:
            logger.info(f"Creating new user with telegram_id: {telegram_id}")
            user = User(
                telegram_id=telegram_id,
                username=username,
                is_onboarding=True,
                onboarding_step=0,
                onboarding_answers=""
            )
            session.add(user)
            session.flush()
            user_data = {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'is_onboarding': user.is_onboarding,
                'onboarding_step': user.onboarding_step,
                'onboarding_answers': user.onboarding_answers,
                'psychotype': user.psychotype,
                'recommended_center': user.recommended_center,
                'recommended_business': user.recommended_business,
                'recommended_soul': user.recommended_soul,
                'recommended_body': user.recommended_body,
                'selected_center': user.selected_center,
                'selected_business': user.selected_business,
                'selected_soul': user.selected_soul,
                'selected_body': user.selected_body,
                'chat_id': user.chat_id,
                'thread_soul': user.thread_soul,
                'thread_body': user.thread_body,
                'thread_business': user.thread_business,
                'thread_center': user.thread_center,
            }
            logger.info(f"Created new user with id: {user_data['id']}")
    
    # Return a new detached user object with the data
    detached_user = User()
    for key, value in user_data.items():
        setattr(detached_user, key, value)
    
    return detached_user


def load_onboarding_questions() -> List[Dict[str, Any]]:
    """Load onboarding questions from JSON file."""
    questions_path = os.path.join(CONTENT_DIR, "onboarding.json")
    logger.info(f"Loading onboarding questions from: {questions_path}")
    
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    
    logger.info(f"Loaded {len(questions)} onboarding questions")
    return questions


def load_curator_prompt(sphere: str, curator: Optional[str] = None) -> str:
    """
    Load curator prompt template from file.
    
    Args:
        sphere: The sphere (center, soul, body, business)
        curator: The curator label (e.g., 'plan', 'vibe', etc.)
    
    Returns:
        The prompt template string
    """
    if not curator:
        raise ValueError(f"Curator label required for sphere: {sphere}")
    
    prompt_path = os.path.join(CONTENT_DIR, "curators", sphere, f"{curator}.txt")
    
    logger.info(f"Loading curator prompt from: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_last_messages(user_id: int, sphere: str, limit: int = 10) -> List[Message]:
    """Get the last N messages for a user in a specific sphere."""
    with get_session() as session:
        messages = session.query(Message).filter(
            Message.user_id == user_id,
            Message.sphere == sphere
        ).order_by(Message.id.desc()).limit(limit).all()
        
        # Reverse to get chronological order and detach
        result = []
        for m in reversed(messages):
            msg = Message(
                id=m.id,
                user_id=m.user_id,
                sphere=m.sphere,
                role=m.role,
                content=m.content,
                created_at=m.created_at
            )
            result.append(msg)
        
        logger.debug(f"Retrieved {len(result)} messages for user {user_id} in {sphere}")
        return result


def get_last_summarization_text(user_id: int, sphere: str) -> str:
    """Get the text of the last summarization for a sphere, or 'no data'."""
    with get_session() as session:
        summarization = session.query(Summarization).filter(
            Summarization.user_id == user_id,
            Summarization.sphere == sphere
        ).order_by(Summarization.created_at.desc()).first()
        
        if summarization:
            return summarization.text
        return "no data"


def build_sphere_prompt(user_id: int, sphere: str, curator: Optional[str] = None) -> str:
    """
    Build the complete prompt for a sphere conversation.
    
    Args:
        user_id: The user's database ID
        sphere: The sphere (center, soul, body, business)
        curator: The curator label for the sphere
        
    Returns:
        The complete prompt string with all data inserted
    """
    logger.info(f"Building sphere prompt for user {user_id}, sphere: {sphere}, curator: {curator}")
    
    # Load the curator prompt template
    prompt_template = load_curator_prompt(sphere, curator)
    
    # Get summarizations for all spheres
    sum_soul = get_last_summarization_text(user_id, "soul")
    sum_body = get_last_summarization_text(user_id, "body")
    sum_business = get_last_summarization_text(user_id, "business")
    
    # Get last 10 messages for this sphere
    messages = get_last_messages(user_id, sphere, limit=10)
    history_lines = []
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        history_lines.append(f"{role_label}: {msg.content}")
    history = "\n".join(history_lines) if history_lines else "no data"
    
    # Render the template
    template = Template(prompt_template)
    prompt = template.render(
        sumSoul=sum_soul,
        sumBody=sum_body,
        sumBusiness=sum_business,
        history=history
    )
    
    logger.debug(f"Built prompt (length: {len(prompt)})")
    return prompt


def detect_sphere_from_topic(topic_name: Optional[str]) -> Optional[str]:
    """
    Detect the sphere from a topic name.
    
    Args:
        topic_name: The name of the message thread topic
        
    Returns:
        The sphere name ('soul', 'body', 'business', 'center') or None
    """
    if not topic_name:
        logger.debug("No topic name provided, cannot detect sphere")
        return None
    
    topic_lower = topic_name.lower()
    logger.info(f"Detecting sphere from topic: {topic_name}")
    
    sphere_mapping = {
        "душа": "soul",
        "дело": "business",
        "тело": "body",
        "штаб": "center"
    }
    
    for keyword, sphere in sphere_mapping.items():
        if keyword in topic_lower:
            logger.info(f"Detected sphere: {sphere} from topic: {topic_name}")
            return sphere
    
    logger.info(f"Could not detect sphere from topic: {topic_name}")
    return None


def update_user_thread(telegram_id: int, sphere: str, thread_id: int, chat_id: int):
    """Update user's thread ID for a specific sphere."""
    logger.info(f"Updating thread for user {telegram_id}, sphere: {sphere}, thread_id: {thread_id}")
    
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.warning(f"User not found: {telegram_id}")
            return
        
        user.chat_id = chat_id
        
        if sphere == "soul":
            user.thread_soul = thread_id
        elif sphere == "body":
            user.thread_body = thread_id
        elif sphere == "business":
            user.thread_business = thread_id
        elif sphere == "center":
            user.thread_center = thread_id
        
        logger.info(f"Updated thread_{sphere} to {thread_id} for user {telegram_id}")


def get_sphere_by_thread(telegram_id: int, chat_id: int, thread_id: Optional[int]) -> Optional[str]:
    """Get the sphere associated with a specific thread ID for a user."""
    logger.info(f"Getting sphere for user {telegram_id}, chat_id: {chat_id}, thread_id: {thread_id}")
    
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.warning(f"User not found: {telegram_id}")
            return None
        
        if user.chat_id != chat_id:
            logger.debug(f"Chat ID mismatch: expected {user.chat_id}, got {chat_id}")
            return None
        
        if thread_id == user.thread_soul:
            return "soul"
        elif thread_id == user.thread_body:
            return "body"
        elif thread_id == user.thread_business:
            return "business"
        elif thread_id == user.thread_center:
            return "center"
        
        logger.debug(f"No matching thread found for thread_id: {thread_id}")
        return None


