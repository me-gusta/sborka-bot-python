import os
import logging
import replicate
from typing import Optional

logger = logging.getLogger(__name__)


class AIService:
    """Service for interacting with Replicate AI API."""
    
    def __init__(self):
        self.token = os.getenv("REPLICATE_TOKEN")
        if not self.token:
            logger.warning("REPLICATE_TOKEN not set in environment variables")
        else:
            os.environ["REPLICATE_API_TOKEN"] = self.token
            logger.info("AIService initialized with Replicate token")
    
    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generate a response from the AI model.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            
        Returns:
            The AI response as a string
        """
        logger.info(f"Generating AI response for prompt (length: {len(prompt)})")
        logger.debug(f"Prompt preview")
        logger.debug(prompt)
        
        try:
            input_data = {
                "prompt": prompt,
                "temperature": 0.7,
                "max_output_tokens": 2048
            }
            
            if system_instruction:
                input_data["system_instruction"] = system_instruction
            
            logger.info("Sending request to Replicate API (google/gemini-2.5-flash)")
            
            output = []
            for event in replicate.stream("google/gemini-2.5-flash", input=input_data):
                output.append(str(event))
            
            response = "".join(output)
            logger.info(f"Received AI response (length: {len(response)})")
            logger.debug(f"Response preview: {response[:200]}...")
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            raise
    
    async def generate_json_response(self, prompt: str, max_retries: int = 3) -> dict:
        """
        Generate a JSON response from the AI model with retry logic.
        
        Args:
            prompt: The user prompt expecting JSON response
            max_retries: Maximum number of retries if JSON parsing fails
            
        Returns:
            Parsed JSON response as dictionary
        """
        import json
        
        logger.info(f"Generating JSON response with max {max_retries} retries")
        
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} to get valid JSON")
            
            try:
                response = await self.generate_response(prompt)
                
                # Try to extract JSON from response
                response = response.strip()
                
                # Remove markdown code blocks if present
                if response.startswith("```json"):
                    response = response[7:]
                if response.startswith("```"):
                    response = response[3:]
                if response.endswith("```"):
                    response = response[:-3]
                
                response = response.strip()
                
                result = json.loads(response)
                logger.info(f"Successfully parsed JSON response on attempt {attempt + 1}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached, could not parse JSON response")
                    raise ValueError(f"Failed to parse JSON response after {max_retries} attempts: {e}")
                    
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}", exc_info=True)
                if attempt == max_retries - 1:
                    raise
        
        raise ValueError("Failed to get valid JSON response")


