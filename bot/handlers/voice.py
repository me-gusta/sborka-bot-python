import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..database import get_session, User
from ..services import SpeechService

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Handler for voice messages."""
    
    MAX_DURATION_SECONDS = 60
    
    def __init__(self, speech_service: SpeechService, chat_handler):
        self.speech_service = speech_service
        self.chat_handler = chat_handler
        logger.info("VoiceHandler initialized")
    
    def _user_has_all_curators(self, telegram_id: int) -> bool:
        """Check if user has selected all curators."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            return all([
                user.selected_business,
                user.selected_soul,
                user.selected_body
            ])
    
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming voice messages."""
        telegram_id = update.effective_user.id
        voice = update.message.voice
        
        logger.info(f"Received voice message from user {telegram_id}, duration: {voice.duration}s")
        
        # Check if user has all curators selected
        if not self._user_has_all_curators(telegram_id):
            logger.warning(f"User {telegram_id} hasn't selected all curators yet")
            await update.message.reply_text(
                "Пожалуйста, сначала выберите наставников для всех сфер. "
                "Используйте команду /curators"
            )
            return
        
        # Check duration
        if voice.duration > self.MAX_DURATION_SECONDS:
            logger.warning(f"Voice message too long: {voice.duration}s (max: {self.MAX_DURATION_SECONDS}s)")
            await update.message.reply_text(
                f"Голосовое сообщение слишком длинное. "
                f"Максимальная продолжительность: {self.MAX_DURATION_SECONDS} секунд."
            )
            return
        
        try:
            # Notify user about processing
            await update.message.reply_text("🎤 Обрабатываю голосовое сообщение...")
            
            # Get the voice file
            voice_file = await context.bot.get_file(voice.file_id)
            voice_url = voice_file.file_path
            
            logger.info(f"Voice file URL: {voice_url}")
            
            # Transcribe the audio
            logger.info("Starting transcription...")
            transcribed_text = await self.speech_service.transcribe_audio(voice_url)
            
            if not transcribed_text or transcribed_text.strip() == "":
                logger.warning("Transcription returned empty text")
                await update.message.reply_text(
                    "Не удалось распознать речь в голосовом сообщении. "
                    "Пожалуйста, попробуйте снова."
                )
                return
            
            logger.info(f"Transcribed text: {transcribed_text[:100]}...")
            
            # Send transcription to user
            await update.message.reply_text(f"📝 Распознано: {transcribed_text}")
            
            # Process the transcribed text
            await self.chat_handler.process_transcribed_text(update, context, transcribed_text)
            
        except Exception as e:
            logger.error(f"Error handling voice message: {e}", exc_info=True)
            await update.message.reply_text(
                f"Произошла ошибка при обработке голосового сообщения: {str(e)}"
            )


