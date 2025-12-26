import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from .database import init_db
from .services import AIService, SpeechService, SummarizationService
from .handlers import OnboardingHandler, ChatHandler, CommandsHandler, VoiceHandler

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SborkaBot:
    """Main bot class that wires everything together."""

    def __init__(self):
        logger.info("Initializing SborkaBot...")

        # Initialize database
        init_db()

        # Initialize services
        self.ai_service = AIService()
        self.speech_service = SpeechService()
        self.summarization_service = SummarizationService(self.ai_service)

        # Initialize handlers
        self.onboarding_handler = OnboardingHandler(self.ai_service)
        self.chat_handler = ChatHandler(self.ai_service, self.summarization_service)
        self.commands_handler = CommandsHandler(self.onboarding_handler)
        self.voice_handler = VoiceHandler(self.speech_service, self.chat_handler)

        # Get bot token
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")

        # Check for test environment
        self.use_test_env = os.getenv("USE_TG_TEST", "false").lower() == "true"

        logger.info("SborkaBot initialized successfully")

    async def _handle_message(self, update: Update, context):
        """Route messages based on user state."""
        telegram_id = update.effective_user.id

        logger.info(f"Received message from user {telegram_id}")

        # Check if user is in onboarding
        if self.onboarding_handler.is_user_onboarding(telegram_id):
            logger.info(f"User {telegram_id} is in onboarding mode, ignoring message")
            await update.message.reply_text(
                "Пожалуйста, сначала завершите тест личности, отвечая на вопросы выше."
            )
            return
        print('onboarding_handler', telegram_id)
        # Handle as regular chat message
        await self.chat_handler.handle_text_message(update, context)

    async def _handle_voice(self, update: Update, context):
        """Handle voice messages."""
        telegram_id = update.effective_user.id

        logger.info(f"Received voice message from user {telegram_id}")

        # Check if user is in onboarding
        if self.onboarding_handler.is_user_onboarding(telegram_id):
            logger.info(f"User {telegram_id} is in onboarding mode, ignoring voice")
            await update.message.reply_text(
                "Пожалуйста, сначала завершите тест личности."
            )
            return

        # Handle voice message
        await self.voice_handler.handle_voice_message(update, context)

    async def _handle_callback(self, update: Update, context):
        """Handle callback queries."""
        query = update.callback_query
        data = query.data

        logger.info(f"Received callback: {data}")

        if data.startswith("onboard_"):
            await self.onboarding_handler.handle_answer(update, context)
        else:
            logger.warning(f"Unknown callback data: {data}")
            await query.answer("Неизвестная команда")

    async def _error_handler(self, update: Update, context):
        """Handle errors globally."""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

        # Try to notify user
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"Произошла ошибка: {str(context.error)}\n"
                    "Пожалуйста, попробуйте снова или обратитесь в поддержку."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")

    def run(self):
        """Run the bot."""
        logger.info("Starting bot...")
        logger.info(f"USE_TG_TEST: {self.use_test_env}")

        # Build application
        builder = (Application.builder()
                .base_url("https://api.telegram.org/bot{token}/test")
                .base_file_url("https://api.telegram.org/file/bot{token}/test").token(self.bot_token))

        # Use test environment if configured
        # IMPORTANT: Test environment requires:
        # 1. A bot token created in Telegram Test Environment (via test app)
        # 2. The test environment uses different DC servers
        # 
        # To create a test bot:
        # - iOS: Tap Settings icon 10 times quickly to access test environment
        # - Android: Go to Settings > Hold on version number 
        # - Then create a new account and bot via test @BotFather
        if self.use_test_env:
            logger.info("Using Telegram test environment")
            # Test environment API endpoints
            # Test DC uses: api.telegram.org but with test tokens
            # For local Bot API server test mode, you'd use:
            (
                builder
                .base_url("https://api.telegram.org/bot{token}/test")
                .base_file_url("https://api.telegram.org/file/bot{token}/test")
            )
            # builder.base_url("http://localhost:8081/bot")
            # builder.base_file_url("http://localhost:8081/file/bot")
            # builder.local_mode(True)
            #
            # For official test DC, just use a test environment token
            # The base URL stays the same, but token must be from test env
            pass
        else:
            logger.info("Using Telegram production environment")

        application = builder.build()

        # Add command handlers
        application.add_handler(CommandHandler("start", self.commands_handler.start_command))
        application.add_handler(CommandHandler("psychotype", self.commands_handler.psychotype_command))
        application.add_handler(CommandHandler("curators", self.commands_handler.curators_command))
        application.add_handler(CommandHandler("help", self.commands_handler.help_command))

        # Add callback query handler
        application.add_handler(CallbackQueryHandler(self._handle_callback))

        # Add message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_message
        ))
        application.add_handler(MessageHandler(
            filters.VOICE,
            self._handle_voice
        ))

        # Add error handler
        application.add_error_handler(self._error_handler)

        logger.info("Bot is ready to start polling...")

        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Entry point for the bot."""
    try:
        bot = SborkaBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
