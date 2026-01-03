import os
import re
import json
import base64
import logging
import asyncio
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)


class AIService:
    """Service for interacting with Google Gemini AI API."""
    
    _configured = False
    
    def __init__(self):
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.model_fallback = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-1.5-flash")
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        self._configure_api()
    
    def _configure_api(self):
        """Configure Gemini API with API key (only once)."""
        if AIService._configured:
            return
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not set in environment variables")
            return
        
        try:
            genai.configure(api_key=api_key)
            AIService._configured = True
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Gemini configuration error: {e}")
    
    def _get_model(self, use_fallback: bool = False) -> Optional[genai.GenerativeModel]:
        """Get Gemini model instance with fallback support."""
        try:
            model_name = self.model_fallback if use_fallback else self.model_name
            return genai.GenerativeModel(
                model_name=model_name,
                safety_settings=self.safety_settings
            )
        except Exception as e:
            logger.error(f"Error initializing model: {e}")
            return None
    
    def _clean_json_string(self, text: str) -> str:
        """Remove markdown code blocks from JSON response."""
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        return text.strip()
    
    async def generate_response(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a text response from Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            temperature: Generation temperature (0.0-1.0)
            
        Returns:
            The AI response as a string
        """
        logger.info(f"Generating AI response for prompt (length: {len(prompt)})")
        
        model = self._get_model(use_fallback=False)
        if not model:
            return "AI service not configured."
        
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"
        
        logger.debug(f"Prompt: {full_prompt}")
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={"temperature": temperature}
            )
            
            if not response.parts:
                logger.error(f"Safety block: {response.prompt_feedback}")
                return "Request blocked by safety filters. Please rephrase."
            
            result = response.text
            logger.info(f"Received AI response (length: {len(result)})")
            logger.debug(f"Response preview: {result[:200]}...")
            return result
            
        except Exception as e:
            logger.error(f"Primary model failed: {e}")
            
            # Try fallback model
            logger.info(f"Trying fallback model: {self.model_fallback}")
            model_fallback = self._get_model(use_fallback=True)
            
            if model_fallback:
                try:
                    response = await asyncio.to_thread(
                        model_fallback.generate_content,
                        full_prompt,
                        generation_config={"temperature": temperature}
                    )
                    return response.text
                except Exception as e2:
                    logger.error(f"Fallback model also failed: {e2}")
            
            raise
    
    async def generate_json_response(self, prompt: str, max_retries: int = 3) -> dict:
        """
        Generate a JSON response from Gemini with retry logic.
        
        Args:
            prompt: The prompt expecting JSON response
            max_retries: Maximum number of retries if JSON parsing fails
            
        Returns:
            Parsed JSON response as dictionary
        """
        logger.info(f"Generating JSON response with max {max_retries} retries")
        
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} to get valid JSON")
            
            try:
                response = await self.generate_response(prompt, temperature=0.1)
                clean_text = self._clean_json_string(response)
                result = json.loads(clean_text)
                logger.info(f"Successfully parsed JSON on attempt {attempt + 1}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached, could not parse JSON")
                    raise ValueError(f"Failed to parse JSON after {max_retries} attempts: {e}")
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}", exc_info=True)
                if attempt == max_retries - 1:
                    raise
        
        raise ValueError("Failed to get valid JSON response")
    
    async def generate_image(self, prompt: str) -> bytes:
        """
        Generate an image using Gemini image generation model.
        
        Args:
            prompt: The image generation prompt
            
        Returns:
            Image bytes
        """
        logger.info(f"Generating image with prompt (length: {len(prompt)})")
        
        try:
            # Use gemini-3-pro-image-preview model for image generation
            image_model = genai.GenerativeModel("gemini-3-pro-image-preview")
            
            response = await asyncio.to_thread(
                image_model.generate_content,
                prompt
            )
            
            if not response.parts:
                logger.error(f"Image generation blocked: {response.prompt_feedback}")
                raise ValueError("Image generation blocked by safety filters")
            
            # Check if response contains image
            if hasattr(response, 'parts') and response.parts:
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        logger.info("Received image data from Gemini")
                        return part.inline_data.data
                    elif hasattr(part, 'text') and part.text:
                        # Sometimes Gemini returns base64 encoded image in text
                        try:
                            # Try to decode as base64
                            image_data = base64.b64decode(part.text)
                            logger.info("Decoded image from base64 text")
                            return image_data
                        except:
                            pass
            
            # Alternative: check if response has images
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                logger.info("Received image data from candidate")
                                return part.inline_data.data
            
            logger.error("No image data found in response")
            raise ValueError("No image data in response")
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}", exc_info=True)
            raise