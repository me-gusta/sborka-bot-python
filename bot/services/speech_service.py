import os
import logging
import replicate
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechService:
    """Service for speech-to-text conversion using Replicate API."""
    
    # Maximum voice message duration in seconds
    MAX_DURATION_SECONDS = 60
    
    def __init__(self):
        self.token = os.getenv("REPLICATE_TOKEN")
        if not self.token:
            logger.warning("REPLICATE_TOKEN not set in environment variables")
        else:
            os.environ["REPLICATE_API_TOKEN"] = self.token
            logger.info("SpeechService initialized with Replicate token")
    
    async def transcribe_audio(self, audio_url: str) -> str:
        """
        Transcribe audio to text using Whisper model.
        
        Args:
            audio_url: URL to the audio file
            
        Returns:
            Transcribed text
        """
        logger.info(f"Starting transcription for audio: {audio_url}")
        
        try:
            input_data = {
                "audio": audio_url,
                "batch_size": 64,
                "language": "russian",
                "task": "transcribe"
            }
            
            logger.info("Sending request to Replicate API (vaibhavs10/incredibly-fast-whisper)")
            
            output = replicate.run(
                "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
                input=input_data
            )
            
            # Output format: {"text": "transcribed text", "chunks": [...]}
            if isinstance(output, dict) and "text" in output:
                text = output["text"]
                logger.info(f"Successfully transcribed audio (length: {len(text)})")
                logger.debug(f"Transcription preview: {text[:200]}...")
                return text
            else:
                logger.warning(f"Unexpected output format: {output}")
                return str(output)
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            raise
    
    def is_duration_valid(self, duration_seconds: int) -> bool:
        """
        Check if the audio duration is within allowed limits.
        
        Args:
            duration_seconds: Duration of the audio in seconds
            
        Returns:
            True if duration is valid, False otherwise
        """
        is_valid = duration_seconds <= self.MAX_DURATION_SECONDS
        logger.info(f"Duration check: {duration_seconds}s (max: {self.MAX_DURATION_SECONDS}s) - valid: {is_valid}")
        return is_valid


