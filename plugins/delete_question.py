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
from typing import Optional, Dict, Any, List, Union
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)

# Router setup
delete_question_router = Router(name="delete_question")

# States for question deletion
class DeleteQuestionStates(StatesGroup):
    selecting_topic = State()
    viewing_questions = State()

# Sponsor footer for consistent messaging
SPONSOR_FOOTER = f" "

# Predefined messages
MESSAGES = {
    "select_topic": "🔍 لطفاً موضوع مورد نظر برای مشاهده سوالات آن را انتخاب کنید:" + SPONSOR_FOOTER,
    "no_topics": "📭 هیچ موضوعی یافت نشد. لطفاً ابتدا با استفاده از دستور /add_topic موضوع اضافه کنید." + SPONSOR_FOOTER,
    "no_questions": "📝 هیچ سوالی برای این موضوع یافت نشد." + SPONSOR_FOOTER,
    "view_question": """
📊 سوال {current_idx}/{total}:

🔖 موضوع: {topic_name}

❓ سوال: 
{question_text}

🔢 گزینه‌ها:
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

✅ گزینه صحیح: {correct_option}

👤 ایجاد شده توسط: {creator_info}
🕒 تاریخ ایجاد: {created_at}
🆔 شناسه سوال: {question_id}
⚡ تأیید شده: {is_approved}
""" + SPONSOR_FOOTER,
    "confirm_delete": "⚠️ آیا از حذف این سوال اطمینان دارید؟" + SPONSOR_FOOTER,
    "deleted": "✅ سوال با موفقیت حذف شد." + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داده است: {error}" + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    
    # Keyboard button texts
    "btn_prev": "◀️ قبلی",
    "btn_next": "بعدی ▶️",
    "btn_delete": "🗑️ حذف این سوال",
    "btn_back_to_topics": "🔙 بازگشت به موضوعات",
    "btn_cancel": "❌ لغو",
    "btn_confirm_delete": "✅ تأیید حذف",
}

# Helper functions
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

def get_topics_keyboard() -> Optional[InlineKeyboardMarkup]:
    """
    Create keyboard with all topics for selection
    
    Returns:
        Optional[InlineKeyboardMarkup]: Keyboard with topic buttons or None if no topics
    """
    topics = db.get_all_topics()
    if not topics:
        return None
        
    kb = InlineKeyboardBuilder()
    for topic in topics:
        if topic.get("is_active", True):  # Only show active topics
            kb.button(text=topic["name"], callback_data=f"delete_question_topic_{topic['topic_id']}")
    
    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_question_cancel")
    kb.adjust(2)  # 2 buttons per row
    return kb.as_markup()

def get_question_navigation_keyboard(current_idx: int, total_questions: int, question_id: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for navigating between questions and deleting current question
    
    Args:
        current_idx: Current question index
        total_questions: Total number of questions
        question_id: ID of the current question
        
    Returns:
        InlineKeyboardMarkup: Navigation keyboard
    """
    kb = InlineKeyboardBuilder()
    
    # Add navigation buttons only if needed
    if total_questions > 1:
        # Previous button (only if not on first question)
        if current_idx > 0:
            kb.button(text=MESSAGES["btn_prev"], callback_data=f"delete_question_nav_prev_{current_idx}")
        
        # Next button (only if not on last question)
        if current_idx < total_questions - 1:
            kb.button(text=MESSAGES["btn_next"], callback_data=f"delete_question_nav_next_{current_idx}")
    
    # Add delete button
    kb.button(text=MESSAGES["btn_delete"], callback_data=f"delete_question_confirm_{question_id}")
    
    # Add back and cancel buttons
    kb.button(text=MESSAGES["btn_back_to_topics"], callback_data="delete_question_back_to_topics")
    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_question_cancel")
    
    # Adjust layout based on which buttons are present
    if total_questions > 1:
        if current_idx > 0 and current_idx < total_questions - 1:
            kb.adjust(2, 1, 1, 1)  # Both prev/next buttons (2 in row), then delete, back, cancel
        else:
            kb.adjust(1, 1, 1, 1)  # Only prev or next button, then delete, back, cancel
    else:
        kb.adjust(1, 1, 1)  # Just delete, back, cancel buttons
        
    return kb.as_markup()

def get_confirmation_keyboard(question_id: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for confirming question deletion
    
    Args:
        question_id: ID of the question to delete
        
    Returns:
        InlineKeyboardMarkup: Confirmation keyboard
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_confirm_delete"], callback_data=f"delete_question_delete_{question_id}")
    kb.button(text=MESSAGES["btn_cancel"], callback_data=f"delete_question_view_{question_id}")
    kb.adjust(2)  # 2 buttons in one row
    return kb.as_markup()

# Command handler
@delete_question_router.message(Command("delete_question"), F.from_user.id == config.ADMIN_ID)
async def cmd_delete_question(message: Message, state: FSMContext) -> None:
    """
    Handler for /delete_question command
    
    Args:
        message: Admin's message with the command
        state: FSM context to clear and set
    """
    try:
        # Clear any previous state
        await state.clear()
        
        # Show list of topics
        keyboard = get_topics_keyboard()
        if not keyboard:
            await message.answer(
                MESSAGES["no_topics"],
                parse_mode=ParseMode.HTML
            )
            return
            
        await state.set_state(DeleteQuestionStates.selecting_topic)
        await message.answer(
            MESSAGES["select_topic"],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} initiated question deletion")
    except Exception as e:
        logger.error(f"Error in delete_question command: {e}")
        # Don't send error to user, just log it

# Cancel callback
@delete_question_router.callback_query(F.data == "delete_question_cancel")
async def cancel_delete_question(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle cancellation of question deletion
    
    Args:
        callback: Callback query from cancel button
        state: FSM context to clear
    """
    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it might be too old")
        
    try:
        # Return to welcome screen
        await callback.message.answer(
            text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} cancelled question deletion")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")

# Back to topics callback
@delete_question_router.callback_query(F.data == "delete_question_back_to_topics")
async def back_to_topics(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Return to topic selection
    
    Args:
        callback: Callback query from back button
        state: FSM context to update
    """
    try:
        # Show list of topics
        keyboard = get_topics_keyboard()
        if not keyboard:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_topics"]
            )
            await state.clear()
            return
            
        await state.set_state(DeleteQuestionStates.selecting_topic)
        await safe_edit_message(
            callback.message,
            MESSAGES["select_topic"],
            keyboard
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} went back to topics list")
    except Exception as e:
        logger.error(f"Error going back to topics: {e}")
        # Don't send error to user, just log it
        await callback.answer()

# Topic selection callback
@delete_question_router.callback_query(F.data.startswith("delete_question_topic_"))
async def topic_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle topic selection and show first question
    
    Args:
        callback: Callback query with topic ID
        state: FSM context to store topic and questions data
    """
    topic_id = callback.data.split("_")[3]
    
    try:
        # Get topic info
        topic_response = db.get_topic_by_id(topic_id)
        if topic_response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["error"].format(error=topic_response["message"])
            )
            await state.clear()
            return
            
        topic = topic_response["topic"]
        topic_name = topic["name"]
        
        # Get topic questions
        questions_response = db.get_questions_by_topic(topic_id)
        if questions_response["status"] == "error":
            # No questions found
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await callback.answer()
            return
            
        questions = questions_response["questions"]
        
        # Save topic and questions data to state
        await state.update_data(
            topic_id=topic_id,
            topic_name=topic_name,
            current_idx=0,
            questions=questions
        )
        
        # Show first question
        await state.set_state(DeleteQuestionStates.viewing_questions)
        await show_question(callback, state, 0)
        logger.info(f"Admin {callback.from_user.id} selected topic {topic_id} ({topic_name}) with {len(questions)} questions")
    except Exception as e:
        logger.error(f"Error selecting topic: {e}")
        # Don't send error to user, just log it
        await callback.answer()

# Navigation callbacks
@delete_question_router.callback_query(F.data.startswith("delete_question_nav_prev_"))
async def navigate_to_prev(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Navigate to previous question
    
    Args:
        callback: Callback query with current index
        state: FSM context with questions data
    """
    current_idx = int(callback.data.split("_")[4])
    await show_question(callback, state, current_idx - 1)
    logger.info(f"Admin {callback.from_user.id} navigated to previous question (index {current_idx-1})")

@delete_question_router.callback_query(F.data.startswith("delete_question_nav_next_"))
async def navigate_to_next(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Navigate to next question
    
    Args:
        callback: Callback query with current index
        state: FSM context with questions data
    """
    current_idx = int(callback.data.split("_")[4])
    await show_question(callback, state, current_idx + 1)
    logger.info(f"Admin {callback.from_user.id} navigated to next question (index {current_idx+1})")

# View specific question (after canceling delete confirmation)
@delete_question_router.callback_query(F.data.startswith("delete_question_view_"))
async def view_specific_question(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Return to viewing the question after canceling deletion
    
    Args:
        callback: Callback query with question ID
        state: FSM context with stored questions
    """
    try:
        data = await state.get_data()
        questions = data.get("questions", [])
        current_idx = data.get("current_idx", 0)
        
        # Make sure we're in the right state
        await state.set_state(DeleteQuestionStates.viewing_questions)
        
        # Show the current question again
        await show_question(callback, state, current_idx)
        logger.info(f"Admin {callback.from_user.id} cancelled question deletion and returned to view")
    except Exception as e:
        logger.error(f"Error viewing specific question: {e}")
        # Don't send error to user, just log it
        await callback.answer()

# Confirm deletion callback
@delete_question_router.callback_query(F.data.startswith("delete_question_confirm_"))
async def confirm_question_deletion(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Show confirmation for question deletion
    
    Args:
        callback: Callback query with question ID
        state: FSM context with questions data
    """
    question_id = callback.data.split("_")[3]
    
    try:
        # Show confirmation message
        await safe_edit_message(
            callback.message,
            f"{callback.message.text}\n\n{MESSAGES['confirm_delete']}",
            get_confirmation_keyboard(question_id)
        )
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} requested confirmation for deleting question {question_id}")
    except Exception as e:
        logger.error(f"Error showing delete confirmation: {e}")
        # Don't send error to user, just log it
        await callback.answer()

# Delete question callback
@delete_question_router.callback_query(F.data.startswith("delete_question_delete_"))
async def delete_question(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Process question deletion after confirmation
    
    Args:
        callback: Callback query with question ID
        state: FSM context with questions data
    """
    question_id = callback.data.split("_")[3]
    
    try:
        # Delete the question
        response = db.reject_question(question_id)  # Using reject_question for deletion
        
        if response["status"] == "error":
            logger.error(f"Error deleting question {question_id}: {response['message']}")
            await safe_edit_message(
                callback.message,
                f"{callback.message.text}\n\nError: {response['message']}"
            )
            await callback.answer()
            return
        
        # Log successful deletion
        logger.info(f"Admin {callback.from_user.id} deleted question {question_id}")
        
        # Update the questions list in state after deletion
        data = await state.get_data()
        questions = data.get("questions", [])
        current_idx = data.get("current_idx", 0)
        topic_id = data.get("topic_id")
        
        # Get updated questions from database
        updated_questions_response = db.get_questions_by_topic(topic_id)
        
        if updated_questions_response["status"] == "error":
            # No more questions left
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await state.clear()
            await callback.answer()
            return
            
        updated_questions = updated_questions_response["questions"]
        
        # Save updated questions to state
        await state.update_data(questions=updated_questions)
        
        # Adjust current_idx if needed (e.g., if we deleted the last question)
        if current_idx >= len(updated_questions):
            current_idx = max(0, len(updated_questions) - 1)
            await state.update_data(current_idx=current_idx)
        
        # Show success message briefly
        await callback.answer(MESSAGES["deleted"])
        
        # Show the next question
        await show_question(callback, state, current_idx)
    except Exception as e:
        logger.error(f"Error deleting question: {e}")
        # Don't send error to user, just log it
        await callback.answer()

async def show_question(callback: CallbackQuery, state: FSMContext, idx: int) -> None:
    """
    Helper function to show a question at given index
    
    Args:
        callback: Callback query object
        state: FSM context with questions data
        idx: Index of the question to show
    """
    try:
        data = await state.get_data()
        questions = data.get("questions", [])
        topic_name = data.get("topic_name", "Unknown")
        
        if not questions or idx < 0 or idx >= len(questions):
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await state.clear()
            return
        
        # Update current index in state
        await state.update_data(current_idx=idx)
        
        # Get question at current index
        question = questions[idx]
        question_id = question["question_id"]
        creator_id = question["created_by"]
        
        # Try to get creator info
        creator_info = f"User ID {creator_id}"
        try:
            creator_data = db.get_user_by_id(creator_id)
            if creator_data["status"] == "success":
                creator = creator_data["user"]
                username = creator.get("username")
                full_name = creator.get("full_name")
                
                if username and full_name:
                    creator_info = f"{full_name} (@{username}, ID: {creator_id})"
                elif username:
                    creator_info = f"@{username} (ID: {creator_id})"
                elif full_name:
                    creator_info = f"{full_name} (ID: {creator_id})"
        except Exception as e:
            logger.error(f"Error getting creator info: {e}")
        
        # Format the question message
        question_text = MESSAGES["view_question"].format(
            current_idx=idx + 1,  # 1-based for display
            total=len(questions),
            topic_name=topic_name,
            question_text=question["text"],
            option_1=question["options"][0],
            option_2=question["options"][1],
            option_3=question["options"][2],
            option_4=question["options"][3],
            correct_option=question["correct_option"] + 1,  # 0-based to 1-based
            creator_info=creator_info,
            created_at=question["created_at"],
            question_id=question_id,
            is_approved=question["is_approved"]
        )
        
        # Create navigation keyboard
        keyboard = get_question_navigation_keyboard(idx, len(questions), question_id)
        
        # Show the question
        await safe_edit_message(
            callback.message,
            question_text,
            keyboard
        )
    except Exception as e:
        logger.error(f"Error showing question: {e}")
        # Don't send error to user, just log it
