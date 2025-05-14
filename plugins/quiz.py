from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
import logging
import config
from bot import db
from .start_bot import main_menu_keyboard
from utils import limit_user_requests
from typing import Optional, Union, Dict, List, Any

logger = logging.getLogger(__name__)


quiz_router = Router(name="quiz")


SPONSOR_FOOTER = f" "


MESSAGES = {
    "select_topic": "📚 لطفاً یک موضوع برای کوئیز خود انتخاب کنید:" + SPONSOR_FOOTER,
    "all_topics": "🔎 همه موضوعات",
    "share_quiz": "🎮 کوئیز شما با موضوع <b>{topic_name}</b> آماده است!\n\nمی‌توانید کوئیز را اینجا شروع کنید یا آن را با دیگران به اشتراک بگذارید." + SPONSOR_FOOTER,
    "start_here": "▶️ شروع کوئیز",
    "share": "🔗 اشتراک‌گذاری کوئیز",
    "back": "◀️ بازگشت",
    "cancel": "❌ لغو",
    "no_active_topics": "⚠️ در حال حاضر هیچ موضوع فعالی برای کوئیز وجود ندارد. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داد: {error}" + SPONSOR_FOOTER,
    "error_general": "❌ خطایی رخ داده است. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "error_topics": "⚠️ در حال حاضر امکان بارگذاری موضوعات وجود ندارد. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "error_action": "⚠️ در حال حاضر امکان تکمیل این عملیات وجود ندارد. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "quiz_cancelled": "🚫 انتخاب کوئیز لغو شد. {user_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    "invalid_callback": "❓ داده‌های دریافتی نامعتبر است." + SPONSOR_FOOTER
}


def get_topics_keyboard() -> Optional[InlineKeyboardMarkup]:

    kb = InlineKeyboardBuilder()
    
    try:
        topics = db.get_all_topics()
        if not topics:
            logger.warning("No topics returned from database")
            return None
            
        active_topics = [topic for topic in topics if topic.get("is_active", False)]
        
        if not active_topics:
            logger.info("No active topics found")
            return None
            
        for topic in active_topics:
            kb.button(
                text=topic["name"],
                callback_data=f"quiz_topic:{topic['topic_id']}:{topic['name']}"
            )
            
        
        kb.button(text=MESSAGES["cancel"], callback_data="quiz_cancel")
        
        kb.adjust(2)
        
        return kb.as_markup()
    except Exception as e:
        logger.error(f"Error creating topics keyboard: {e}")
        return None


def get_share_keyboard(topic_id: str, topic_name: str, user_id: int) -> InlineKeyboardMarkup:

    try:
        kb = InlineKeyboardBuilder()
        
        
        
        
        kb.button(
            text=MESSAGES["share"],
            switch_inline_query=f"quiz_{user_id}_{topic_id}_{topic_name}"
        )
        
        
        kb.button(text=MESSAGES["back"], callback_data="quiz_back_to_topics")
        kb.button(text=MESSAGES["cancel"], callback_data="quiz_cancel")
        
        kb.adjust(1, 1, 2)
        
        return kb.as_markup()
    except Exception as e:
        logger.error(f"Error creating share keyboard: {e}")
        return create_fallback_keyboard()


def create_fallback_keyboard() -> InlineKeyboardMarkup:

    try:
        kb = InlineKeyboardBuilder()
        kb.button(text=MESSAGES["back"], callback_data="quiz_back_to_topics")
        kb.button(text=MESSAGES["cancel"], callback_data="quiz_cancel")
        kb.adjust(2)
        return kb.as_markup()
    except Exception as e:
        logger.error(f"Error creating fallback keyboard: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])


async def safe_edit_message(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = None) -> bool:

    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("Message not modified, content is the same")
            return True
        else:
            logger.error(f"Error editing message: {e}")
            try:
                await message.edit_text(text=MESSAGES["error_general"])
            except Exception as inner_e:
                logger.error(f"Complete failure in editing message: {inner_e}")
            return False
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False


@quiz_router.message(F.text == config.MAIN_MENU_START_QUIZ_BUTTON)
@limit_user_requests(seconds=1)
async def start_quiz(message: Message) -> None:

    try:
        db.create_user(user_id=message.from_user.id, 
                       username=message.from_user.username if message.from_user.username else None,
                       full_name=message.from_user.full_name if message.from_user.full_name else "",
                       has_start=True)
        
        topics_keyboard = get_topics_keyboard()
        
        if not topics_keyboard:
            await message.answer(MESSAGES["no_active_topics"], parse_mode=ParseMode.HTML)
            return
            
        await message.answer(
            text=MESSAGES["select_topic"],
            reply_markup=topics_keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {message.from_user.id} started quiz selection")
    except Exception as e:
        logger.error(f"Error starting quiz: {e}")


@quiz_router.callback_query(F.data.startswith("quiz_topic:"))
@limit_user_requests(seconds=1)
async def topic_selected(callback: CallbackQuery) -> None:

    await callback.answer()
    
    try:
        parts = callback.data.split(":", 2)
        if len(parts) < 3:
            logger.warning(f"Invalid callback data format: {callback.data}")
            return
            
        topic_id = parts[1]
        topic_name = parts[2]
        
        user_id = callback.from_user.id
        
        share_keyboard = get_share_keyboard(topic_id, topic_name, user_id)
        
        await safe_edit_message(
            message=callback.message,
            text=MESSAGES["share_quiz"].format(topic_name=topic_name),
            reply_markup=share_keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {user_id} selected topic {topic_id}")
    except Exception as e:
        logger.error(f"Error selecting topic: {e}")


@quiz_router.callback_query(F.data == "quiz_back_to_topics")
@limit_user_requests(seconds=1)
async def back_to_topics(callback: CallbackQuery) -> None:

    await callback.answer()
    
    try:
        topics_keyboard = get_topics_keyboard()
        if not topics_keyboard:
            await safe_edit_message(
                message=callback.message,
                text=MESSAGES["no_active_topics"],
                parse_mode=ParseMode.HTML
            )
            return
            
        await safe_edit_message(
            message=callback.message,
            text=MESSAGES["select_topic"],
            reply_markup=topics_keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {callback.from_user.id} went back to topics")
    except Exception as e:
        logger.error(f"Error going back to topics: {e}")


@quiz_router.callback_query(F.data == "quiz_cancel")
@limit_user_requests(seconds=1)
async def cancel_quiz(callback: CallbackQuery) -> None:

    await callback.answer()
    
    try:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            logger.debug("Could not delete message")
            
        await callback.message.answer(
            text=MESSAGES["quiz_cancelled"].format(user_name=callback.from_user.full_name),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {callback.from_user.id} cancelled quiz selection")
    except Exception as e:
        logger.error(f"Error cancelling quiz: {e}")



