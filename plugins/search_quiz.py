from aiogram import Router, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.enums import ParseMode
import logging
import config
from bot import db
import uuid
from html import escape
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
# واردات موارد مورد نیاز از utils
from utils import (
    active_quizzes, 
    quiz_settings, 
    SPONSOR_FOOTER, 
    format_participants_list, 
    COMMON_MESSAGES,
    update_quiz_settings,
    create_quiz_keyboard_for_existing,
    create_quiz_message,
    limit_user_requests
)

logger = logging.getLogger(__name__)

# Quiz search router
search_quiz_router = Router(name="search_quiz")

def extract_settings_from_callback_data(callback_data: str) -> Dict[str, int]:
    """
    Extract question count and time limit from quiz_start callback data
    
    Args:
        callback_data: Callback data string in format quiz_start:topic_id:user_id:quiz_id:question_count:time_limit
        
    Returns:
        Dict with question_count and time_limit values
    """
    result = {
        "question_count": config.QUIZ_COUNT_OF_QUESTIONS_LIST[0],
        "time_limit": config.QUIZ_TIME_LIMIT_LIST[0]
    }
    
    try:
        parts = callback_data.split(":")
        if len(parts) >= 6 and parts[0] == "quiz_start":
            result["question_count"] = int(parts[4])
            result["time_limit"] = int(parts[5])
    except (ValueError, IndexError) as e:
        logger.error(f"Error extracting settings: {e}")
    
    return result

# Constant messages
MESSAGES = {
    "choose_topic": "🔍 لطفاً یک موضوع برای کوئیز انتخاب کنید:" + SPONSOR_FOOTER,
    "no_active_topics": "⚠️ در حال حاضر هیچ موضوع فعالی برای کوئیز وجود ندارد." + SPONSOR_FOOTER,
    "quiz_info": """
<b>📋 اطلاعات کوئیز:</b>

<b>🎯 موضوع:</b> {topic_name}
<b>❓ تعداد سؤالات:</b> {question_count}
<b>⏱ زمان هر سؤال:</b> {time_limit} ثانیه

به این کوئیز بپیوندید و دانش خود را محک بزنید!""" + SPONSOR_FOOTER,
    "error_try_again": "❌ خطا در بارگیری موضوعات. لطفاً دوباره تلاش کنید." + SPONSOR_FOOTER,
    
    # Error messages and user feedback
    "invalid_data_format": "❌ فرمت داده نامعتبر است",
    "only_creator_can_change": "⚠️ فقط سازنده کوئیز می‌تواند تنظیمات را تغییر دهد",
    "invalid_question_count": "❌ تعداد سؤالات نامعتبر است",
    "invalid_time_limit": "❌ محدودیت زمانی نامعتبر است",
    "cannot_update_settings": "⚠️ امکان به‌روزرسانی تنظیمات کوئیز وجود ندارد",
    "selected_questions": "✅ {count} سؤال انتخاب شد",
    "selected_time": "⏱ زمان هر سؤال: {time} ثانیه",
    "error_updating_settings": "❌ خطا در به‌روزرسانی تنظیمات",
    "click_to_start": "🎮 برای شروع کوئیز اینجا کلیک کنید"
}

# استفاده از پیام‌های مشترک
MESSAGES.update({
    "start_quiz": COMMON_MESSAGES["start_quiz"],
    "join_quiz": COMMON_MESSAGES["join_quiz"],
    "sponsor_channel": COMMON_MESSAGES["sponsor_channel"],
    "last_updated": COMMON_MESSAGES["last_updated"],
    "question_count_btn": COMMON_MESSAGES["question_count_btn"],
    "time_limit_btn": COMMON_MESSAGES["time_limit_btn"]
})

def get_quiz_keyboard(user_id: Union[int, str], topic_id: str, topic_name: Optional[str] = None,
                      question_count: int = None, time_limit: int = None) -> InlineKeyboardMarkup:
    """
    Create a keyboard for quiz with start, join, and sponsor buttons.
    Plus options for question count and time limit.
    
    Args:
        user_id: ID of the user who created the quiz
        topic_id: Topic ID
        topic_name: Topic name (optional)
        question_count: Selected question count (optional)
        time_limit: Selected time limit (optional)
        
    Returns:
        InlineKeyboardMarkup: Prepared keyboard with buttons
    """
    # Create a unique identifier for the quiz
    quiz_id = str(uuid.uuid4())[0:8]
    
    # Default values if not provided
    if question_count is None:
        question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
    if time_limit is None:
        time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
    
    # Store initial settings
    quiz_settings[quiz_id] = {
        "question_count": question_count,
        "time_limit": time_limit
    }
    
    # Create main buttons
    buttons = [
        [
            InlineKeyboardButton(
                text=MESSAGES["start_quiz"],
                callback_data=f"quiz_start:{topic_id}:{user_id}:{quiz_id}:{question_count}:{time_limit}"
            ),
            InlineKeyboardButton(
                text=MESSAGES["join_quiz"],
                callback_data=f"quiz_join:{topic_id}:{user_id}:{quiz_id}"
            )
        ]
    ]
    
    # Create question count buttons dynamically from config
    question_count_buttons = []
    for count in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
        button = InlineKeyboardButton(
            text=f"{MESSAGES['question_count_btn'].format(count=count, selected='✅' if count == question_count else '')}",
            callback_data=f"quiz_qcount:{topic_id}:{user_id}:{quiz_id}:{count}"
        )
        question_count_buttons.append(button)
    
    # Add question count buttons
    if question_count_buttons:
        buttons.append(question_count_buttons)
    
    # Create time limit buttons dynamically from config
    time_limit_buttons = []
    for limit in config.QUIZ_TIME_LIMIT_LIST:
        button = InlineKeyboardButton(
            text=f"{MESSAGES['time_limit_btn'].format(limit=limit, selected='✅' if limit == time_limit else '')}",
            callback_data=f"quiz_tlimit:{topic_id}:{user_id}:{quiz_id}:{limit}"
        )
        time_limit_buttons.append(button)
    
    # Add time limit buttons
    if time_limit_buttons:
        buttons.append(time_limit_buttons)
    
    # Add sponsor button
    buttons.append([
        InlineKeyboardButton(
            text=MESSAGES["sponsor_channel"],
            url=f"{config.SPONSOR_CHANNEL_URL}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@search_quiz_router.inline_query()
async def process_inline_query(query: InlineQuery) -> None:
    """
    Process inline query from users searching for quizzes.
    
    Args:
        query: Inline query object from Telegram
    """
    try:
        # Create or update user in database
        db.create_user(user_id=query.from_user.id, has_start=None)
        search_text = query.query.strip()
        
        # Check if query follows the quiz sharing pattern
        if search_text.startswith("quiz_"):
            # Extract information from query (quiz_user_id_topic_id_topic_name)
            parts = search_text.split('_', 3)
            if len(parts) >= 4:
                creator_id = parts[1]
                topic_id = parts[2]
                topic_name = parts[3]
                
                # Verify topic exists in database
                topic_result = db.get_topic_by_id(topic_id)
                if topic_result["status"] == "success" and topic_result["topic"].get("is_active", False):
                    # Show only the specific topic
                    return await show_specific_topic(query, creator_id, topic_id, topic_name)
        
        # If query doesn't match expected pattern or parameters are invalid, show all topics
        return await show_topic_list(query)
    
    except Exception as e:
        # Log error and show simple error message
        logger.error(f"Error processing inline query: {e}")
        await query.answer(
            results=[],
            switch_pm_text=MESSAGES["click_to_start"],
            switch_pm_parameter="start",
            cache_time=60
        )


async def show_specific_topic(query: InlineQuery, creator_id: str, topic_id: str, topic_name: str) -> None:
    """
    Display only a specific shared topic.
    
    Args:
        query: Inline query object
        creator_id: Quiz creator ID
        topic_id: Topic ID
        topic_name: Topic name
    """
    try:
        # Verify topic exists in database
        topic_result = db.get_topic_by_id(topic_id)
        if topic_result["status"] != "success":
            logger.warning(f"Topic not found when showing specific topic: {topic_id}")
            return await show_topic_list(query)
            
        # Use topic name from database for better security
        real_topic_name = topic_result["topic"]["name"]

        # Use topic description from database for better security
        real_topic_description = topic_result["topic"]["description"]
        
        # Create main quiz message
        message_text = create_quiz_message(topic_name=real_topic_name, 
                                           topic_description=real_topic_description)
        
        # Create actions keyboard
        reply_markup = get_quiz_keyboard(creator_id, topic_id, real_topic_name)
        
        # Create search result
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"کوییز: {real_topic_name}",
                description=f"شروع یا پیوستن به کوییز {real_topic_name}",
                input_message_content=InputTextMessageContent(
                    message_text=message_text,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=reply_markup
            )
        ]
        
        # Answer query with result
        await query.answer(
            results=results,
            cache_time=60
        )
        logger.info(f"Showed specific topic: {topic_id} ({real_topic_name})")
    
    except Exception as e:
        # Log error and fall back to showing all topics
        logger.error(f"Error showing specific topic: {e}")
        return await show_topic_list(query)


async def show_topic_list(query: InlineQuery) -> None:
    """
    Display a list of all active topics for selection in inline mode.
    
    Args:
        query: Inline query object
    """
    try:
        # Get all active topics
        topics = db.get_all_topics()
        active_topics = [topic for topic in topics if topic.get("is_active", False)]
        
        if not active_topics:
            # If no active topics exist
            logger.info("No active topics found for inline query")
            await query.answer(
                results=[],
                switch_pm_text=MESSAGES["no_active_topics"],
                switch_pm_parameter="no_topics",
                cache_time=60
            )
            return
            
        results = []
        
        # Create result for each active topic
        for topic in active_topics:
            # Message text and descriptions
            title = topic["name"]
            description = topic.get("description", "موضوع کوییز را انتخاب کنید")
            topic_id = topic['topic_id']
            
            # Create main quiz message
            message_text = create_quiz_message(topic_name=title, 
                                               topic_description=description)
            
            # Create actions keyboard with Start and Join buttons
            reply_markup = get_quiz_keyboard(query.from_user.id, topic_id, title)
            
            # Create search result with direct buttons
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description or "موضوع کوییز را انتخاب کنید",
                    input_message_content=InputTextMessageContent(
                        message_text=message_text,
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=reply_markup
                )
            )
        # Answer query with results
        await query.answer(
            results=results,
            cache_time=60
        )
        logger.info(f"Showed topic list with {len(results)} topics")
    
    except Exception as e:
        # Log error and show simple error message
        logger.error(f"Error showing topic list: {e}")
        await query.answer(
            results=[],
            switch_pm_text=MESSAGES["error_try_again"],
            switch_pm_parameter="error",
            cache_time=60
        )

# Add new handlers for question count and time limit selection
@search_quiz_router.callback_query(F.data.startswith("quiz_qcount:"))
@limit_user_requests(seconds=2)
async def handle_question_count(callback: CallbackQuery) -> None:
    """
    Handle selection of question count
    
    Args:
        callback: Callback query from quiz_qcount button
    """
    try:
        # Parse data from callback
        parts = callback.data.split(":")
        if len(parts) != 5:
            await callback.answer(MESSAGES["invalid_data_format"], show_alert=True)
            return
            
        topic_id = parts[1]
        user_id = parts[2]
        quiz_id = parts[3]
        question_count = int(parts[4])
        
        # بررسی دسترسی کاربر - فقط سازنده کوییز مجاز به تغییر تنظیمات است
        current_user_id = callback.from_user.id
        if str(current_user_id) != str(user_id):
            await callback.answer(MESSAGES["only_creator_can_change"], show_alert=True)
            return
        
        # Validate question count
        if question_count not in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
            await callback.answer(MESSAGES["invalid_question_count"], show_alert=True)
            return
            
        # Check if we have inline_message_id
        if not callback.inline_message_id:
            await callback.answer(MESSAGES["cannot_update_settings"], show_alert=True)
            return
        
        # Get current settings or use defaults
        if quiz_id in quiz_settings:
            current_time_limit = quiz_settings[quiz_id].get("time_limit", config.QUIZ_TIME_LIMIT_LIST[0])
        else:
            current_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
            
        # Save settings in quiz_settings
        quiz_settings[quiz_id] = {
            "question_count": question_count,
            "time_limit": current_time_limit
        }
        
        # به روزرسانی تنظیمات در active_quizzes نیز
        if quiz_id in active_quizzes:
            active_quizzes[quiz_id]["question_count"] = question_count
            
        # Update the quiz settings
        await update_quiz_settings(
            callback=callback,
            topic_id=topic_id,
            user_id=user_id,
            quiz_id=quiz_id,
            question_count=question_count,
            time_limit=current_time_limit
        )
        
        # Confirm selection to user
        await callback.answer(MESSAGES["selected_questions"].format(count=question_count), show_alert=False)
        
    except Exception as e:
        logger.error(f"Error handling question count selection: {e}")
        await callback.answer(MESSAGES["error_updating_settings"], show_alert=True)


@search_quiz_router.callback_query(F.data.startswith("quiz_tlimit:"))
@limit_user_requests(seconds=2)
async def handle_time_limit(callback: CallbackQuery) -> None:
    """
    Handle selection of time limit per question
    
    Args:
        callback: Callback query from quiz_tlimit button
    """
    try:
        # Parse data from callback
        parts = callback.data.split(":")
        if len(parts) != 5:
            await callback.answer(MESSAGES["invalid_data_format"], show_alert=True)
            return
            
        topic_id = parts[1]
        user_id = parts[2]
        quiz_id = parts[3]
        time_limit = int(parts[4])
        
        # بررسی دسترسی کاربر - فقط سازنده کوییز مجاز به تغییر تنظیمات است
        current_user_id = callback.from_user.id
        if str(current_user_id) != str(user_id):
            await callback.answer(MESSAGES["only_creator_can_change"], show_alert=True)
            return
        
        # Validate time limit
        if time_limit not in config.QUIZ_TIME_LIMIT_LIST:
            await callback.answer(MESSAGES["invalid_time_limit"], show_alert=True)
            return
            
        # Check if we have inline_message_id
        if not callback.inline_message_id:
            await callback.answer(MESSAGES["cannot_update_settings"], show_alert=True)
            return
        
        # Get current settings or use defaults
        if quiz_id in quiz_settings:
            current_question_count = quiz_settings[quiz_id].get("question_count", config.QUIZ_COUNT_OF_QUESTIONS_LIST[0])
        else:
            current_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
            
        # Save settings
        quiz_settings[quiz_id] = {
            "question_count": current_question_count,
            "time_limit": time_limit
        }
        
        # به روزرسانی تنظیمات در active_quizzes نیز
        if quiz_id in active_quizzes:
            active_quizzes[quiz_id]["time_limit"] = time_limit
            
        # Update the quiz settings
        await update_quiz_settings(
            callback=callback,
            topic_id=topic_id,
            user_id=user_id,
            quiz_id=quiz_id,
            question_count=current_question_count,
            time_limit=time_limit
        )
        
        # Confirm selection to user
        await callback.answer(MESSAGES["selected_time"].format(time=time_limit), show_alert=False)
        
    except Exception as e:
        logger.error(f"Error handling time limit selection: {e}")
        await callback.answer(MESSAGES["error_updating_settings"], show_alert=True)
