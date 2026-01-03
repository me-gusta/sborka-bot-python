import os
import json
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from jinja2 import Template

from ..database import get_session, User
from ..utils import get_or_create_user, get_all_spheres_history, get_help_text

logger = logging.getLogger(__name__)


class CommandsHandler:
    """Handler for bot commands."""
    
    def __init__(self, onboarding_handler, ai_service=None):
        self.onboarding_handler = onboarding_handler
        self.ai_service = ai_service
        logger.info("CommandsHandler initialized")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        logger.info(f"Start command from user {telegram_id} ({username})")
        
        # Get or create user
        user = get_or_create_user(telegram_id, username, first_name, last_name)
        
        # Check if user needs onboarding
        if user.is_onboarding:
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
                "или /reset_goals для повторного прохождения теста."
            )
    
    async def reset_goals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset_goals command - restart the goals test."""
        telegram_id = update.effective_user.id
        
        logger.info(f"Reset goals command from user {telegram_id}")
        
        await update.message.reply_text(
            "Начинаем тест заново! 🔄\n\n"
            "Отвечайте на вопросы, отправляя текстовые сообщения."
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
    
    async def poster_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /poster command - show poster selection."""
        telegram_id = update.effective_user.id
        
        logger.info(f"Poster command from user {telegram_id}")
        
        message_text = (
            "Выбери свой постер:\n"
            "- \"Криптохайп\"\n"
            "- \"Неонуар\""
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Криптохайп", callback_data="poster_cryptohype")],
            [InlineKeyboardButton("Неонуар", callback_data="poster_neonoir")]
        ])
        
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard
        )
    
    async def handle_poster_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle poster selection callback."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        telegram_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Extract poster handle from callback data (poster_cryptohype or poster_neonoir)
        if data == "poster_cryptohype":
            handle = "cryptohype"
        elif data == "poster_neonoir":
            handle = "neonoir"
        else:
            logger.warning(f"Unknown poster handle: {data}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Неизвестный тип постера"
            )
            return
        
        logger.info(f"Generating poster '{handle}' for user {telegram_id}")
        
        try:
            # Send "generating" message
            await context.bot.send_message(
                chat_id=chat_id,
                text="Генерирую изображение. Это займет до 2х минут"
            )
            
            # Get user
            user = get_or_create_user(
                telegram_id, 
                update.effective_user.username,
                update.effective_user.first_name,
                update.effective_user.last_name
            )
            
            # Generate poster
            image_path = await self._generate_poster(user, handle)
            
            # Send image to user
            with open(image_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo
                )
            
            logger.info(f"Successfully generated and sent poster '{handle}' for user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error generating poster: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Произошла ошибка при генерации постера: {str(e)}"
            )
    
    async def _generate_poster(self, user: User, handle: str) -> str:
        """
        Generate a poster for a user.
        
        Args:
            user: user
            handle: Poster handle (cryptohype or neonoir)
            
        Returns:
            Path to the generated image file
        """
        user_id = user.id
        logger.info(f"Generating poster '{handle}' for user {user_id}")
        
        if not self.ai_service:
            raise ValueError("AI service not available")
        
        # Get content directory
        content_dir = Path(__file__).parent.parent.parent / "content" / "posters"
        generated_dir = Path(__file__).parent.parent.parent / "generated" / "posters"
        
        # Create generated directory if it doesn't exist
        generated_dir.mkdir(parents=True, exist_ok=True)
        
        # Read variables.txt
        variables_path = content_dir / handle / "variables.txt"
        if not variables_path.exists():
            raise FileNotFoundError(f"Variables file not found: {variables_path}")
        
        with open(variables_path, "r", encoding="utf-8") as f:
            variables_template = f.read()
        
        # Get history from all spheres
        history = get_all_spheres_history(user_id)
        
        # Generate variables using AI (using nunjucks/jinja2 template)
        template = Template(variables_template)
        variables_prompt = template.render(history=history)

        logger.info("Generating variables JSON from AI...")
        variables_json = await self.ai_service.generate_json_response(variables_prompt)
        
        # Read imagePrompt.json
        image_prompt_path = content_dir / handle / "imagePrompt.json"
        if not image_prompt_path.exists():
            raise FileNotFoundError(f"Image prompt file not found: {image_prompt_path}")
        
        with open(image_prompt_path, "r", encoding="utf-8") as f:
            image_prompt_template = f.read()
        
        # Render imagePrompt with variables
        image_prompt_template_obj = Template(image_prompt_template)

        # if user.username:
        #     variables_json['username'] = '@' + user.name
        variables_json['first_name'] = user.first_name

        image_prompt = image_prompt_template_obj.render(**variables_json)

        # Read imageBasePrompt.txt
        image_base_prompt_path = content_dir / "imageBasePrompt.txt"
        if not image_base_prompt_path.exists():
            raise FileNotFoundError(f"Image base prompt file not found: {image_base_prompt_path}")
        
        with open(image_base_prompt_path, "r", encoding="utf-8") as f:
            image_base_prompt_template = f.read()
        
        # Render imageBasePrompt with imagePrompt
        base_template = Template(image_base_prompt_template)
        final_prompt = base_template.render(imagePrompt=image_prompt)
        
        logger.info("Generating image from Gemini...")
        # Generate image
        image_bytes = await self.ai_service.generate_image(final_prompt)
        
        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"{handle}_{user_id}_{timestamp}.png"
        image_path = generated_dir / image_filename
        
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        
        logger.info(f"Saved image to {image_path}")
        
        return str(image_path)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        logger.info(f"Help command from user {update.effective_user.id}")
        
        help_text = get_help_text()
        await update.message.reply_text(help_text, parse_mode="HTML")


