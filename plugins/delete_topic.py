from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

import config
from bot import db
import logging
from typing import Optional, Dict, Any, List
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)

# Router setup
delete_topic_router = Router(name="delete_topic")


# States for topic deletion flow
class DeleteTopicStates(StatesGroup):
    waiting_for_confirmation = State()


# Sponsor footer for consistent messaging
SPONSOR_FOOTER = f" "

# Predefined messages
MESSAGES = {
    "select_topic": "🔍 لطفاً موضوع مورد نظر برای حذف را انتخاب کنید:" + SPONSOR_FOOTER,
    "not_found": "📭 هیچ موضوعی یافت نشد" + SPONSOR_FOOTER,
    "confirm_delete": """
⚠️ آیا از حذف این موضوع اطمینان دارید؟

🔖 نام موضوع: 
{name}

📄 توضیحات موضوع: 
{description}

🆔 شناسه موضوع: 
{topic_id}

⚠️ هشدار: این عملیات قابل بازگشت نیست!
""" + SPONSOR_FOOTER,
    "deleted": "✅ موضوع '{name}' با موفقیت حذف شد." + SPONSOR_FOOTER,
    "canceled": "❌ حذف موضوع لغو شد." + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داده است: {error}" + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    
    # Keyboard button texts
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


def get_topics_list_keyboard() -> Optional[InlineKeyboardMarkup]:
    """
    Create keyboard with all topics
    
    Returns:
        Optional[InlineKeyboardMarkup]: Keyboard with topic buttons or None if no topics
    """
    topics = db.get_all_topics()
    if not topics:
        return None

    kb = InlineKeyboardBuilder()
    for topic in topics:
        kb.button(text=topic["name"], callback_data=f"delete_view_{topic['topic_id']}")

    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_cancel")
    kb.adjust(2)  # 2 buttons per row
    return kb.as_markup()


def get_confirmation_keyboard(topic_id: str) -> InlineKeyboardMarkup:
    """
    Create confirmation keyboard for topic deletion
    
    Args:
        topic_id: ID of the topic to delete
        
    Returns:
        InlineKeyboardMarkup: Keyboard with confirmation buttons
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_confirm_delete"], callback_data=f"delete_confirm_{topic_id}")
    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_cancel")
    kb.adjust(2)  # 2 buttons in one row
    return kb.as_markup()


# Command handler
@delete_topic_router.message(Command("delete_topic"), F.from_user.id == config.ADMIN_ID)
async def cmd_delete_topic(message: Message) -> None:
    """
    Handler for /delete_topic command, shows list of topics
    
    Args:
        message: Admin's message with the command
    """
    try:
        keyboard = get_topics_list_keyboard()
        if not keyboard:
            await message.answer(
                MESSAGES["not_found"],
                parse_mode=ParseMode.HTML
            )
            return

        await message.answer(
            text=MESSAGES["select_topic"],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} initiated topic deletion")
    except Exception as e:
        logger.error(f"Error in delete_topic command: {e}")
        # Don't send error to user, just log it


# Cancel callback
@delete_topic_router.callback_query(F.data == "delete_cancel")
async def cancel_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle cancellation of topic deletion
    
    Args:
        callback: Callback query from cancel button
        state: FSM context to clear
    """
    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        # Message might be too old to delete
        logger.debug("Could not delete message, it might be too old")

    try:
        await callback.message.answer(
            text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} cancelled topic deletion")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")


# View topic callback
@delete_topic_router.callback_query(F.data.startswith("delete_view_"))
async def view_topic_for_deletion(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Show topic details and confirm deletion
    
    Args:
        callback: Callback query with topic ID
        state: FSM context to store topic information
    """
    topic_id = callback.data.split("_")[2]

    try:
        # Get topic info
        response = db.get_topic_by_id(topic_id)
        if response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["not_found"]
            )
            await callback.answer()
            return

        topic = response["topic"]

        # Save topic_id to state
        await state.update_data(topic_id=topic_id, topic_name=topic["name"])
        await state.set_state(DeleteTopicStates.waiting_for_confirmation)

        # Show confirmation message
        confirmation_text = MESSAGES["confirm_delete"].format(
            name=topic["name"],
            description=topic["description"],
            topic_id=topic["topic_id"]
        )

        await safe_edit_message(
            callback.message,
            text=confirmation_text,
            reply_markup=get_confirmation_keyboard(topic_id)
        )

        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewing topic {topic_id} for deletion")
    except Exception as e:
        logger.error(f"Error viewing topic for deletion: {e}")
        # Don't send error to user, just log it
        await callback.answer()


# Confirm deletion callback
@delete_topic_router.callback_query(F.data.startswith("delete_confirm_"))
async def confirm_topic_deletion(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Process topic deletion after confirmation
    
    Args:
        callback: Callback query with topic ID
        state: FSM context with stored topic information
    """
    topic_id = callback.data.split("_")[2]

    try:
        # Get topic name from state
        data = await state.get_data()
        topic_name = data.get("topic_name", "Unknown")

        # Delete topic
        db.delete_topic(topic_id)
        
        # Log successful deletion
        logger.info(f"Admin {callback.from_user.id} deleted topic {topic_id} ({topic_name})")

        # Clear state
        await state.clear()

        # Delete confirmation message
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            logger.debug("Could not delete message, it might be too old")

        # Return to welcome screen
        await callback.message.answer(
            text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

        await callback.answer()
    except Exception as e:
        logger.error(f"Error deleting topic: {e}")
        # Don't send the error message to the user, just log it
        await callback.answer()
