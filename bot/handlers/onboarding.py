import os
import json
import logging
from typing import Optional
from jinja2 import Template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..database import get_session, User
from ..services import AIService
from ..utils import get_or_create_user, load_onboarding_questions, get_help_text, CONTENT_DIR

logger = logging.getLogger(__name__)


class OnboardingHandler:
    """Handler for user onboarding and personality test."""
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.questions = load_onboarding_questions()
        logger.info(f"OnboardingHandler initialized with {len(self.questions)} questions")
    
    def _build_question_message(self, question_data: dict, current: int, total: int) -> str:
        """Build the message text for a question."""
        prefix = f"[{current}/{total}]"
        question = question_data["question"]
        
        answers = []
        for letter in ["A", "B", "C", "D"]:
            if letter in question_data:
                answers.append(f"{letter}. {question_data[letter]}")
        
        return f"{prefix} {question}\n\n" + "\n".join(answers)
    
    def _build_answer_keyboard(self) -> InlineKeyboardMarkup:
        """Build the inline keyboard for answering questions."""
        buttons = [
            InlineKeyboardButton("A", callback_data="onboard_A"),
            InlineKeyboardButton("B", callback_data="onboard_B"),
            InlineKeyboardButton("C", callback_data="onboard_C"),
            InlineKeyboardButton("D", callback_data="onboard_D"),
        ]
        return InlineKeyboardMarkup([buttons])
    
    async def start_onboarding(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the onboarding process for a user."""
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        logger.info(f"Starting onboarding for user {telegram_id} ({username})")
        
        # Get or create user
        user = get_or_create_user(telegram_id, username, first_name, last_name)
        
        # Reset onboarding state
        with get_session() as session:
            db_user = session.query(User).filter(User.telegram_id == telegram_id).first()
            db_user.is_onboarding = True
            db_user.onboarding_step = 0
            db_user.onboarding_answers = ""
            db_user.psychotype = None
        
        logger.info(f"Onboarding state reset for user {telegram_id}")
        
        # Send first question
        await self._send_question(update, context, 0)
    
    async def _send_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, step: int):
        """Send a specific question to the user."""
        if step >= len(self.questions):
            logger.warning(f"Invalid step {step}, max is {len(self.questions) - 1}")
            return
        
        question_data = self.questions[step]
        message_text = self._build_question_message(question_data, step + 1, len(self.questions))
        keyboard = self._build_answer_keyboard()
        
        logger.info(f"Sending question {step + 1}/{len(self.questions)}")
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                text=message_text,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=keyboard
            )
    
    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to a question."""
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        answer = query.data.replace("onboard_", "")  # Extract A, B, C, or D
        
        logger.info(f"User {telegram_id} answered: {answer}")
        
        # Get current user state
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                logger.error(f"User not found: {telegram_id}")
                await query.message.reply_text("Ошибка: пользователь не найден. Пожалуйста, начните с /start")
                return
            
            if not user.is_onboarding:
                logger.warning(f"User {telegram_id} is not in onboarding mode")
                await query.message.reply_text("Вы уже прошли тест. Используйте /psychotype для повторного прохождения.")
                return
            
            current_step = user.onboarding_step
            
            # Store answer
            answers = json.loads(user.onboarding_answers) if user.onboarding_answers else []
            answers.append({
                "question_index": current_step,
                "answer": answer
            })
            user.onboarding_answers = json.dumps(answers)
            
            # Move to next step
            user.onboarding_step = current_step + 1
            next_step = user.onboarding_step
        
        logger.info(f"User {telegram_id} moved to step {next_step}")
        
        # Check if test is complete
        if next_step >= len(self.questions):
            await self._complete_onboarding(update, context, telegram_id)
        else:
            await self._send_question(update, context, next_step)
    
    async def _complete_onboarding(self, update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int):
        """Complete the onboarding process and analyze results."""
        logger.info(f"Completing onboarding for user {telegram_id}")
        
        # Notify user about processing
        await update.callback_query.message.reply_text("Мы обрабатываем ваш результат...")
        
        # Check if we should skip AI requests
        skip_personality_requests = os.getenv("SKIP_PERSONALITY_REQUESTS", "false").lower() in ("true", "1", "yes")
        
        try:
            if skip_personality_requests:
                # Use hardcoded values instead of AI requests
                logger.info("SKIP_PERSONALITY_REQUESTS is enabled, using hardcoded values")
                psychotype_result = "Обыкновенный человек"
                recommendations = {
                    "center": "vibe",
                    "business": "vibe",
                    "soul": "vibe",
                    "body": "vibe"
                }
            else:
                # Get user answers
                with get_session() as session:
                    user = session.query(User).filter(User.telegram_id == telegram_id).first()
                    answers = json.loads(user.onboarding_answers) if user.onboarding_answers else []
                
                # Build psychotype prompt
                psychotype_prompt = await self._build_psychotype_prompt(answers)
                
                logger.info("Generating psychotype analysis...")
                psychotype_result = await self.ai_service.generate_response(psychotype_prompt)
                
                # Build recommendation prompt and get curator recommendations
                recommendation_prompt = await self._build_recommendation_prompt(psychotype_result)
                
                logger.info("Generating curator recommendations...")
                recommendations = await self.ai_service.generate_json_response(recommendation_prompt)
            
            # Validate recommendations
            required_fields = ["center", "business", "soul", "body"]
            for field in required_fields:
                if field not in recommendations:
                    raise ValueError(f"Missing required field in recommendations: {field}")
            
            # Save psychotype and recommendations
            with get_session() as session:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                user.psychotype = psychotype_result
                user.recommended_center = recommendations["center"]
                user.recommended_business = recommendations["business"]
                user.recommended_soul = recommendations["soul"]
                user.recommended_body = recommendations["body"]
                
                # Also set as selected curators
                user.selected_center = recommendations["center"]
                user.selected_business = recommendations["business"]
                user.selected_soul = recommendations["soul"]
                user.selected_body = recommendations["body"]
                
                # Mark onboarding as complete
                user.is_onboarding = False
            
            logger.info(f"Recommendations saved for user {telegram_id}: {recommendations}")
            
            # Send success message with psychotype
            await update.callback_query.message.reply_text(
                f"✅ Тест завершён!\n\n"
                f"Мы подобрали для вас наставников на основе вашего профиля."
            )
            
            # Trigger the curators command flow
            await self._show_curators_message(update, context)
            
            # Send help message
            await self._send_help_message(update, context)
            
        except Exception as e:
            logger.error(f"Error completing onboarding: {e}", exc_info=True)
            await update.callback_query.message.reply_text(
                f"Произошла ошибка при обработке результатов: {str(e)}\n"
                "Пожалуйста, попробуйте снова с командой /psychotype"
            )
    
    async def _build_psychotype_prompt(self, answers: list) -> str:
        """Build the psychotype analysis prompt."""
        logger.info("Building psychotype prompt")
        
        # Format answers
        results_lines = []
        for answer_data in answers:
            q_index = answer_data["question_index"]
            answer = answer_data["answer"]
            
            if q_index < len(self.questions):
                question = self.questions[q_index]["question"]
                answer_text = self.questions[q_index].get(answer, answer)
                results_lines.append(f"{question}: {answer_text}")
        
        results = "\n".join(results_lines)
        
        # Load prompt template
        prompt_path = os.path.join(CONTENT_DIR, "psycotype.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            template_str = f.read()
        
        template = Template(template_str)
        prompt = template.render(results=results)
        
        logger.debug(f"Built psychotype prompt (length: {len(prompt)})")
        return prompt
    
    async def _build_recommendation_prompt(self, psychotype: str) -> str:
        """Build the curator recommendation prompt."""
        logger.info("Building recommendation prompt")
        
        # Load prompt template
        prompt_path = os.path.join(CONTENT_DIR, "recommendation.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            template_str = f.read()
        
        template = Template(template_str)
        prompt = template.render(psychotype=psychotype)
        
        logger.debug(f"Built recommendation prompt (length: {len(prompt)})")
        return prompt
    
    async def _show_curators_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the curators selection message."""
        webapp_url = os.getenv("WEBAPP_URL", "https://127.0.0.1:5000")
        curator_page_url = f"{webapp_url}/curator-choice"
        
        message_text = (
            "Сейчас тебе нужно выбрать наставников! "
            "Не волнуйся, ты всегда сможешь изменить свой выбор и выбрать того, кто тебе больше по душе."
        )
        
        # Get user's telegram_id for the webapp
        telegram_id = update.effective_user.id
        curator_page_url_with_user = f"{curator_page_url}?user_id={telegram_id}"

        print(curator_page_url_with_user)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Выбрать наставников",
                url=curator_page_url_with_user
            )]
        ])
        
        logger.info(f"Sending curators message with webapp URL: {curator_page_url_with_user}")
        
        try:
            if update.callback_query:
                await update.callback_query.answer()
        except:
            ...

        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard
        )
    
    async def _send_help_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message to user."""
        help_text = get_help_text()
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode="Markdown"
        )
    
    def is_user_onboarding(self, telegram_id: int) -> bool:
        """Check if user is currently in onboarding mode."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return True  # New user should start onboarding
            return user.is_onboarding


