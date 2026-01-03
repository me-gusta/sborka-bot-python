import os
import json
import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from ..database import get_session, User, Message
from ..utils import get_or_create_user, load_onboarding_questions, get_help_text, CONTENT_DIR

logger = logging.getLogger(__name__)


class OnboardingHandler:
    """Handler for user onboarding and goals test."""
    
    def __init__(self, ai_service=None):
        self.ai_service = ai_service
        self.questions = load_onboarding_questions()
        logger.info(f"OnboardingHandler initialized with {len(self.questions)} questions")
    
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
            db_user.onboarding_answers = "[]"
        
        logger.info(f"Onboarding state reset for user {telegram_id}")
        
        # Send first question
        await self._send_question(update, context, 0)
    
    async def _send_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, step: int):
        """Send a specific question to the user."""
        if step >= len(self.questions):
            logger.warning(f"Invalid step {step}, max is {len(self.questions) - 1}")
            return
        
        question_data = self.questions[step]
        question_text = question_data["question"]
        prefix = f"[{step + 1}/{len(self.questions)}]"
        message_text = f"{prefix}\n\n{question_text}\n\n_Отправьте ваш ответ текстовым сообщением._"
        
        logger.info(f"Sending question {step + 1}/{len(self.questions)}")
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                text=message_text,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=message_text,
                parse_mode="Markdown"
            )
    
    async def handle_text_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's text answer to a question."""
        telegram_id = update.effective_user.id
        answer_text = update.message.text.strip()
        
        logger.info(f"User {telegram_id} answered with text: {answer_text[:50]}...")
        
        # Get current user state
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                logger.error(f"User not found: {telegram_id}")
                await update.message.reply_text("Ошибка: пользователь не найден. Пожалуйста, начните с /start")
                return
            
            if not user.is_onboarding:
                logger.warning(f"User {telegram_id} is not in onboarding mode")
                await update.message.reply_text("Вы уже прошли тест. Используйте /reset_goals для повторного прохождения.")
                return
            
            current_step = user.onboarding_step
            
            if current_step >= len(self.questions):
                logger.warning(f"User {telegram_id} answered after completing test")
                await update.message.reply_text("Тест уже завершен. Используйте /reset_goals для повторного прохождения.")
                return
            
            # Store answer
            answers = json.loads(user.onboarding_answers) if user.onboarding_answers else []
            question_data = self.questions[current_step]
            answers.append({
                "question_key": question_data.get("key", f"question_{current_step}"),
                "question": question_data["question"],
                "answer": answer_text
            })
            user.onboarding_answers = json.dumps(answers, ensure_ascii=False)
            
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
        """Complete the onboarding process and save results."""
        logger.info(f"Completing onboarding for user {telegram_id}")
        
        try:
            # Get user answers
            with get_session() as session:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                answers = json.loads(user.onboarding_answers) if user.onboarding_answers else []
                
                # Format all answers as a single text
                formatted_answers = []
                for answer_data in answers:
                    formatted_answers.append(
                        f"{answer_data['question']}\n{answer_data['answer']}"
                    )
                
                results_text = "\n\n".join(formatted_answers)
                
                # Get existing first message in center sphere if exists
                first_message = session.query(Message).filter(
                    Message.user_id == user.id,
                    Message.sphere == "center"
                ).order_by(Message.id.asc()).first()
                
                if first_message:
                    # Update the first message (overwrite previous test results)
                    first_message.content = results_text
                    first_message.role = "user"
                    logger.info(f"Updated first message in center sphere for user {telegram_id} (overwriting previous test results)")
                else:
                    # Save results as the first message in center sphere
                    center_message = Message(
                        user_id=user.id,
                        sphere="center",
                        role="user",
                        content=results_text
                    )
                    session.add(center_message)
                    logger.info(f"Created first message in center sphere for user {telegram_id}")
                
                # Mark onboarding as complete
                user.is_onboarding = False
                session.commit()
            
            logger.info(f"Onboarding completed for user {telegram_id}, results saved to center sphere")
            
            # Send success message
            await update.message.reply_text(
                "✅ Тест завершён!\n\n"
                "Ваши ответы сохранены. Теперь вы можете выбрать наставников."
            )
            
            # Trigger the curators command flow
            await self._show_curators_message(update, context)
            
            # Send help message
            await self._send_help_message(update, context)
            
        except Exception as e:
            logger.error(f"Error completing onboarding: {e}", exc_info=True)
            await update.message.reply_text(
                f"Произошла ошибка при обработке результатов: {str(e)}\n"
                "Пожалуйста, попробуйте снова с командой /reset_goals"
            )
    
    async def _show_curators_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the curators selection message."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
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
            parse_mode="HTML"
        )
    
    def is_user_onboarding(self, telegram_id: int) -> bool:
        """Check if user is currently in onboarding mode."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return True  # New user should start onboarding
            return user.is_onboarding
