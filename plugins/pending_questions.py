from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

import config
from bot import db, bot
import logging
from .start_bot import main_menu_keyboard, welcome_message
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# Router setup
pending_questions_router = Router(name="pending_questions")

# States for pending questions management
class PendingQuestionStates(StatesGroup):
    viewing_questions = State()

# Sponsor footer for consistent messaging
SPONSOR_FOOTER = f" "

# Predefined messages
MESSAGES = {
    "no_pending_questions": "📭 هیچ سؤال در انتظار بررسی یافت نشد." + SPONSOR_FOOTER,
    "view_question": """
📋 سؤال در انتظار بررسی {current_idx}/{total}:

🔍 موضوع: {topic_name}

❓ سؤال: 
{question_text}

🔢 گزینه‌ها:
1. {option_1}
2. {option_2}
3. {option_3}
4. {option_4}

✅ گزینه صحیح: {correct_option}

👤 ایجاد شده توسط: {creator_info}
🕒 تاریخ ایجاد: {created_at}
🆔 شناسه سؤال: {question_id}
""" + SPONSOR_FOOTER,
    "approved": "✅ سؤال با موفقیت تأیید شد." + SPONSOR_FOOTER,
    "rejected": "❌ سؤال رد شده و حذف گردید." + SPONSOR_FOOTER,
    "error": "❗ خطایی رخ داد: {error}" + SPONSOR_FOOTER,
    "approving": "⏳ در حال تأیید سؤال..." + SPONSOR_FOOTER,
    "rejecting": "⏳ در حال رد کردن سؤال..." + SPONSOR_FOOTER,
    "error_question_not_found": "❌ خطا: سؤال یافت نشد." + SPONSOR_FOOTER,
    "error_question_not_approved": "❌ خطا: سؤال نمی‌تواند تأیید شود." + SPONSOR_FOOTER,
    "error_question_not_deleted": "❌ خطا: سؤال یافت نشد یا امکان حذف آن وجود ندارد." + SPONSOR_FOOTER,
    "invalid_index": "⚠️ شاخص سؤال نامعتبر است. بازگشت به سؤال اول." + SPONSOR_FOOTER,
    "processing": "⏳ در حال پردازش...",
    
    # Keyboard button texts
    "previous": "◀️ قبلی",
    "next": "بعدی ▶️",
    "approve": "✅ تأیید",
    "reject": "❌ رد",
    "cancel": "❌ لغو",
    
    # Welcome back message
    "welcome_back": "🔙 بازگشت به منوی اصلی"
}

# ------------------------------
# Keyboard functions
# ------------------------------

def get_question_keyboard(current_idx: int, total_questions: int, question_id: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for navigating between questions and approving/rejecting current question
    
    Args:
        current_idx: Current question index
        total_questions: Total number of pending questions
        question_id: ID of the current question
        
    Returns:
        InlineKeyboardMarkup: Keyboard with navigation and action buttons
    """
    kb = InlineKeyboardBuilder()
    
    # Add navigation buttons only if needed
    if total_questions > 1:
        if current_idx > 0:
            kb.button(text=MESSAGES["previous"], callback_data=f"pending_nav_prev_{current_idx}")
        
        if current_idx < total_questions - 1:
            kb.button(text=MESSAGES["next"], callback_data=f"pending_nav_next_{current_idx}")
    
    # Add action buttons
    kb.button(text=MESSAGES["approve"], callback_data=f"pending_approve_{question_id}")
    kb.button(text=MESSAGES["reject"], callback_data=f"pending_reject_{question_id}")
    kb.button(text=MESSAGES["cancel"], callback_data="pending_cancel")
    
    # Adjust layout
    if total_questions > 1 and current_idx > 0 and current_idx < total_questions - 1:
        kb.adjust(2, 2, 1)  # Both prev/next, then approve/reject, then cancel
    elif total_questions > 1:
        kb.adjust(1, 2, 1)  # Only prev or next, then approve/reject, then cancel
    else:
        kb.adjust(2, 1)  # Just approve/reject, then cancel
        
    return kb.as_markup()

# ------------------------------
# Safe message editing
# ------------------------------

async def safe_edit_message(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    """
    Edit a message with error handling to prevent unwanted error messages
    
    Args:
        message: Message to edit
        text: New text content
        reply_markup: Optional keyboard markup
        
    Returns:
        bool: Success status of the operation
    """
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            # Not a real error, message content hasn't changed
            logger.debug("Message not modified, content is the same")
            return True
        else:
            # Log the error but don't send to user
            logger.error(f"Error editing message: {e}")
            return False
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False

# ------------------------------
# Command handler
# ------------------------------

@pending_questions_router.message(Command("pending_questions"), F.from_user.id == config.ADMIN_ID)
async def cmd_pending_questions(message: Message, state: FSMContext) -> None:
    """
    Handler for /pending_questions command that shows pending questions for admin review
    
    Args:
        message: Admin's message with command
        state: FSM context for storing question data
    """
    # Clear any previous state
    await state.clear()
    
    try:
        # Get all questions with is_approved=False
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        if not pending_questions:
            await message.answer(
                MESSAGES["no_pending_questions"],
                parse_mode=ParseMode.HTML
            )
            return
        
        # Save questions to state
        await state.update_data(questions=pending_questions, current_idx=0)
        await state.set_state(PendingQuestionStates.viewing_questions)
        
        # Display first question
        await display_question(message, pending_questions[0], 0, len(pending_questions), is_new_message=True)
        logger.info(f"Admin started reviewing {len(pending_questions)} pending questions")
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error in pending_questions command: {e}")

# ------------------------------
# Navigation handlers
# ------------------------------

@pending_questions_router.callback_query(F.data.startswith("pending_nav_prev_"))
async def nav_prev(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Navigate to previous question in the review queue
    
    Args:
        callback: Callback query from navigation button
        state: FSM context with question data
    """
    await callback.answer()
    
    current_idx = int(callback.data.split("_")[3]) - 1
    await navigate_to_question(callback, state, current_idx)
    logger.info(f"Admin navigated to previous question (index: {current_idx})")

@pending_questions_router.callback_query(F.data.startswith("pending_nav_next_"))
async def nav_next(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Navigate to next question in the review queue
    
    Args:
        callback: Callback query from navigation button
        state: FSM context with question data
    """
    await callback.answer()
    
    current_idx = int(callback.data.split("_")[3]) + 1
    await navigate_to_question(callback, state, current_idx)
    logger.info(f"Admin navigated to next question (index: {current_idx})")

@pending_questions_router.callback_query(F.data == "pending_cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Cancel pending questions review and return to main menu
    
    Args:
        callback: Callback query from cancel button
        state: FSM context to clear
    """
    await callback.answer()
    
    await state.clear()
    
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it may have been deleted already")
    
    await callback.message.answer(
        text=welcome_message.format(full_name=callback.from_user.full_name),
        reply_markup=main_menu_keyboard,
        parse_mode=ParseMode.HTML
    )
    logger.info(f"Admin cancelled pending questions review")

# ------------------------------
# Question action handlers
# ------------------------------

@pending_questions_router.callback_query(F.data.startswith("pending_approve_"))
async def approve_question(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Approve a pending question and make it available in quizzes
    
    Args:
        callback: Callback query from approve button
        state: FSM context with question data
    """
    await callback.answer(MESSAGES["processing"])
    
    question_id = callback.data.split("_")[2]
    
    # Show processing message
    await safe_edit_message(
        callback.message,
        MESSAGES["approving"]
    )
    
    try:
        # Update question directly
        result = db.questions.update_one(
            {"question_id": question_id},
            {"$set": {"is_approved": True}}
        )
        
        if result.modified_count == 0:
            # Check if question exists
            if not db.questions.find_one({"question_id": question_id}):
                await safe_edit_message(
                    callback.message,
                    MESSAGES["error_question_not_found"]
                )
                return
            else:
                await safe_edit_message(
                    callback.message,
                    MESSAGES["error_question_not_approved"]
                )
                return
        
        # Success - update the question list and display next
        data = await state.get_data()
        current_idx = data.get("current_idx", 0)
        
        # Get updated pending questions
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        # Update state with new questions
        await state.update_data(questions=pending_questions)
        
        # Show success message
        await safe_edit_message(
            callback.message,
            MESSAGES["approved"]
        )
        logger.info(f"Question {question_id} approved successfully")
        
        # If no more questions, end the process
        if not pending_questions:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
        
        # Adjust index if needed
        if current_idx >= len(pending_questions):
            current_idx = len(pending_questions) - 1
        
        # Update state with new index
        await state.update_data(current_idx=current_idx)
        
        # Show next question
        await display_question(callback.message, pending_questions[current_idx], current_idx, len(pending_questions))
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error approving question: {e}")

@pending_questions_router.callback_query(F.data.startswith("pending_reject_"))
async def reject_question(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Reject and delete a pending question
    
    Args:
        callback: Callback query from reject button
        state: FSM context with question data
    """
    await callback.answer(MESSAGES["processing"])
    
    question_id = callback.data.split("_")[2]
    
    # Show processing message
    await safe_edit_message(
        callback.message,
        MESSAGES["rejecting"]
    )
    
    try:
        # Delete question directly
        result = db.questions.delete_one({"question_id": question_id})
        
        if result.deleted_count == 0:
            await safe_edit_message(
                callback.message,
                MESSAGES["error_question_not_deleted"]
            )
            return
        
        # Success - update the question list and display next
        data = await state.get_data()
        current_idx = data.get("current_idx", 0)
        
        # Get updated pending questions
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        # Update state with new questions
        await state.update_data(questions=pending_questions)
        
        # Show success message
        await safe_edit_message(
            callback.message,
            MESSAGES["rejected"]
        )
        logger.info(f"Question {question_id} rejected and deleted")
        
        # If no more questions, end the process
        if not pending_questions:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
        
        # Adjust index if needed
        if current_idx >= len(pending_questions):
            current_idx = len(pending_questions) - 1
        
        # Update state with new index
        await state.update_data(current_idx=current_idx)
        
        # Show next question
        await display_question(callback.message, pending_questions[current_idx], current_idx, len(pending_questions))
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error rejecting question: {e}")

# ------------------------------
# Helper functions
# ------------------------------

async def navigate_to_question(callback: CallbackQuery, state: FSMContext, current_idx: int) -> None:
    """
    Navigate to a specific question index in the pending questions list
    
    Args:
        callback: Callback query from navigation button
        state: FSM context with question data
        current_idx: Target question index
    """
    data = await state.get_data()
    questions = data.get("questions", [])
    
    # Validate the index
    if current_idx < 0 or current_idx >= len(questions):
        logger.warning(f"Invalid question index: {current_idx}, max: {len(questions)-1}")
        await safe_edit_message(
            callback.message,
            MESSAGES["invalid_index"]
        )
        current_idx = 0
        if len(questions) == 0:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
    
    # Update state with new index
    await state.update_data(current_idx=current_idx)
    
    # Display the question
    await display_question(callback.message, questions[current_idx], current_idx, len(questions))

async def display_question(message_obj: Message, question: Dict[str, Any], idx: int, total: int, is_new_message: bool = False) -> None:
    """
    Display a question with all its information
    
    Args:
        message_obj: Message object for reply or edit
        question: Question data dictionary
        idx: Current question index
        total: Total number of questions
        is_new_message: Whether to create a new message or edit existing one
    """
    try:
        # Get topic information
        topic_info = db.topics.find_one({"topic_id": question["topic_id"]})
        topic_name = topic_info["name"] if topic_info else "Unknown"
        
        # Get creator information
        creator_id = question["created_by"]
        creator_info = f"User ID: {creator_id}"
        
        creator = db.users.find_one({"user_id": creator_id})
        if creator:
            username = creator.get("username", "")
            full_name = creator.get("full_name", "")
            
            if username and full_name:
                creator_info = f"{full_name} (@{username}, ID: {creator_id})"
            elif username:
                creator_info = f"@{username} (ID: {creator_id})"
            elif full_name:
                creator_info = f"{full_name} (ID: {creator_id})"
        
        # Format the question message
        question_text = MESSAGES["view_question"].format(
            current_idx=idx + 1,  # 1-based index for display
            total=total,
            topic_name=topic_name,
            question_text=question["text"],
            option_1=question["options"][0],
            option_2=question["options"][1],
            option_3=question["options"][2],
            option_4=question["options"][3],
            correct_option=question["correct_option"] + 1,  # Convert from 0-based to 1-based
            creator_info=creator_info,
            created_at=question["created_at"],
            question_id=question["question_id"]
        )
        
        # Create keyboard
        keyboard = get_question_keyboard(idx, total, question["question_id"])
        
        # Send or edit message
        if is_new_message:
            await message_obj.answer(
                question_text, 
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            await safe_edit_message(
                message_obj,
                question_text,
                keyboard
            )
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error displaying question: {e}")
