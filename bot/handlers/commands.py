import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..database import get_session, User
from ..utils import get_or_create_user

logger = logging.getLogger(__name__)


class CommandsHandler:
    """Handler for bot commands."""
    
    def __init__(self, onboarding_handler):
        self.onboarding_handler = onboarding_handler
        logger.info("CommandsHandler initialized")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"Start command from user {telegram_id} ({username})")
        
        # Get or create user
        user = get_or_create_user(telegram_id, username)
        
        # Check if user needs onboarding
        if user.is_onboarding or not user.psychotype:
            logger.info(f"User {telegram_id} needs onboarding")
            await update.message.reply_text(
                "Добро пожаловать! 👋\n\n"
                "Давайте начнём с небольшого теста, чтобы понять вас лучше и подобрать подходящих наставников."
            )
            await self.onboarding_handler.start_onboarding(update, context)
        else:
            logger.info(f"User {telegram_id} already completed onboarding")
            await update.message.reply_text(
                "С возвращением! 👋\n\n"
                "Вы уже прошли тест. Используйте /curators для выбора наставников "
                "или /psychotype для повторного прохождения теста."
            )
    
    async def psychotype_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /psychotype command - restart the personality test."""
        telegram_id = update.effective_user.id
        
        logger.info(f"Psychotype command from user {telegram_id}")
        
        await update.message.reply_text(
            "Начинаем тест заново! 🔄\n\n"
            "Отвечайте на вопросы, выбирая наиболее подходящий вариант."
        )
        
        await self.onboarding_handler.start_onboarding(update, context)
    
    async def curators_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /curators command - show curator selection."""
        telegram_id = update.effective_user.id
        
        logger.info(f"Curators command from user {telegram_id}")
        
        # Check if user has completed onboarding
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                logger.warning(f"User {telegram_id} not found")
                await update.message.reply_text(
                    "Пожалуйста, сначала пройдите тест с помощью команды /start"
                )
                return
            
            if user.is_onboarding:
                logger.warning(f"User {telegram_id} is still in onboarding")
                await update.message.reply_text(
                    "Пожалуйста, сначала завершите тест личности."
                )
                return
        
        # Show curators selection message
        webapp_url = os.getenv("WEBAPP_URL", "http://127.0.0.1:5000")
        curator_page_url = f"{webapp_url}/curator-choice?user_id={telegram_id}"
        
        message_text = (
            "Сейчас тебе нужно выбрать наставников! "
            "Не волнуйся, ты всегда сможешь изменить свой выбор и выбрать того, кто тебе больше по душе."
        )
        
        logger.info(f"Sending curators message with webapp URL: {curator_page_url}")
        
        # Check if URL is HTTPS (required for web_app buttons)
        # If not HTTPS, use regular URL button instead
        keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Выбрать наставников",
                    url=curator_page_url
                )]
            ])
        
        await update.message.reply_text(
            text=message_text,
            reply_markup=keyboard
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        logger.info(f"Help command from user {update.effective_user.id}")
        
        help_text = (
            "🤖 *Команды бота*\n\n"
            "/start - Начать работу с ботом\n"
            "/psychotype - Пройти тест личности заново\n"
            "/curators - Выбрать наставников\n"
            "/help - Показать это сообщение\n\n"
            "*Как использовать*\n\n"
            "1. Пройдите тест личности\n"
            "2. Выберите наставников для каждой сферы\n"
            "3. Общайтесь с наставниками в соответствующих топиках:\n"
            "   - 🎯 Штаб - общая координация\n"
            "   - 💼 Дело - бизнес и карьера\n"
            "   - 🧘 Душа - эмоции и внутренний мир\n"
            "   - 💪 Тело - здоровье и физическая форма\n\n"
            "Вы можете отправлять текстовые и голосовые сообщения (до 1 минуты)."
        )
        
        await update.message.reply_text(help_text, parse_mode="Markdown")


