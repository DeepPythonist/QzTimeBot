
import logging
from functools import wraps
from html import escape
from datetime import datetime
from typing import Callable, Any, Union, Dict, List, Optional

import redis
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

import config

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True
)


def limit_user_requests(seconds: int = 1):
    """
    Decorator for rate limiting user requests to prevent spam and abuse.
    Each function will have its own separate rate limiting.
    
    Args:
        seconds: The cooldown period in seconds before a user can make another request
        
    Returns:
        Callable: Decorator function that wraps the handler
        
    Example:
        @limit_user_requests(seconds=5)
        async def my_handler(event, *args, **kwargs):
            # Handler code
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(event: Union[Message, CallbackQuery], *args: Any, **kwargs: Any):
            user_id = event.from_user.id
            rate_limit_key = f"user:{user_id}:func:{func.__name__}:requests"
            
            if not redis_client.get(rate_limit_key):
                redis_client.setex(name=rate_limit_key, value=1, time=seconds)
                return await func(event, *args, **kwargs)
            else:
                logger.info(f"User {user_id} is rate limited for function {func.__name__}")
                return None

        return wrapper
    return decorator


active_quizzes = {}

quiz_settings = {}

SPONSOR_FOOTER = f" "

COMMON_MESSAGES = {
    "start_quiz": "🎮 شروع کوییز",
    "join_quiz": "🚪 پیوستن به کوییز",
    "sponsor_channel": "👑 کانال اسپانسر",
    
    "question_count_btn": "{count} سوال {selected}",
    "time_limit_btn": "{limit} ثانیه {selected}",
    
    "last_updated": "\n\n<i>آخرین بروزرسانی: {update_time}</i>",
    
    "quiz_info_with_participants": """
<b>📋 اطلاعات کوییز:</b>

<b>موضوع:</b> {topic_name}
<b>تعداد سوالات:</b> {question_count}
<b>زمان هر سوال:</b> {time_limit} ثانیه
<b>شرکت‌کنندگان ({participant_count}):</b>
{participants_list}

به این کوییز بپیوندید تا دانش خود را بسنجید!
""" + SPONSOR_FOOTER
}

MAX_DISPLAYED_PARTICIPANTS = 10
CREATOR_ICON = "👑"
CREATOR_SUFFIX = "(سازنده)"
NO_PARTICIPANTS_MESSAGE = "هنوز شرکت‌کننده‌ای وجود ندارد"
ADDITIONAL_PARTICIPANTS_MESSAGE = "\n... و {} نفر دیگر"

SELECTED_INDICATOR = "✅"


class ButtonType:
    START = "quiz_start"
    JOIN = "quiz_join"
    QUESTION_COUNT = "quiz_qcount"
    TIME_LIMIT = "quiz_tlimit"


def create_button_row(text1: str, callback_data1: str, text2: str, callback_data2: str) -> List[InlineKeyboardButton]:
    """Helper function to create a row with two buttons"""
    return [
        InlineKeyboardButton(text=text1, callback_data=callback_data1),
        InlineKeyboardButton(text=text2, callback_data=callback_data2)
    ]


def create_option_buttons(
    values: List[int], 
    prefix: str, 
    topic_id: str, 
    user_id: Union[int, str], 
    quiz_id: str, 
    selected_value: int,
    format_func: Callable[[int, bool], str]
) -> List[InlineKeyboardButton]:
    """Helper function to create option buttons with selected indicator"""
    buttons = []
    for value in values:
        is_selected = value == selected_value
        text = format_func(value, is_selected)
        callback_data = f"{prefix}:{topic_id}:{user_id}:{quiz_id}:{value}"
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
    return buttons


def format_count_button(count: int, is_selected: bool) -> str:
    """Format text for question count button"""
    indicator = SELECTED_INDICATOR if is_selected else ""
    return f"{count} سوال {indicator}".strip()


def format_time_button(seconds: int, is_selected: bool) -> str:
    """Format text for time limit button"""
    indicator = SELECTED_INDICATOR if is_selected else ""
    return f"{seconds} ثانیه {indicator}".strip()


def format_participants_list(participants: Dict[Union[int, str], Dict[str, Any]], creator_id: Union[int, str]) -> str:
    """
    Format a list of participants for display in a message.
    
    Args:
        participants: Dictionary of participant data keyed by user ID
        creator_id: ID of the quiz creator
        
    Returns:
        str: Formatted text with participant list
    """
    if not participants:
        return NO_PARTICIPANTS_MESSAGE
        
    creator_id = int(creator_id) if isinstance(creator_id, str) else creator_id
    
    formatted_entries = []
    for user_id, user_data in participants.items():
        user_id = int(user_id) if isinstance(user_id, str) else user_id
        
        name = user_data.get('full_name', '')
        if not name:
            name = f"کاربر {user_id}"
            
        if user_id == creator_id:
            formatted_entries.append(f"{name} {CREATOR_ICON} {CREATOR_SUFFIX}")
        else:
            formatted_entries.append(name)
    
    if len(formatted_entries) <= MAX_DISPLAYED_PARTICIPANTS:
        return '\n'.join(f"{i+1}. {entry}" for i, entry in enumerate(formatted_entries))
    else:
        visible_entries = [f"{i+1}. {entry}" for i, entry in enumerate(formatted_entries[:MAX_DISPLAYED_PARTICIPANTS])]
        remaining_count = len(formatted_entries) - MAX_DISPLAYED_PARTICIPANTS
        return '\n'.join(visible_entries) + ADDITIONAL_PARTICIPANTS_MESSAGE.format(remaining_count)


QUIZ_INFO_TEMPLATE = """
<b>📋 اطلاعات کوییز:</b>

<b>موضوع:</b> {topic_name}
<b>توضیحات:</b> {topic_description}
<b>تعداد سوالات:</b> {question_count}
<b>زمان هر سوال:</b> {time_limit} ثانیه

به این کوییز بپیوندید تا دانش خود را بسنجید!"""


def create_quiz_message(topic_name: str, 
                        topic_description: str, 
                        question_count: int = None, 
                        time_limit: int = None) -> str:
    """
    Create a formatted quiz message with topic information and settings.
    
    Args:
        topic_name: Topic name (will be HTML-escaped)
        question_count: Number of questions (defaults to first value in config)
        time_limit: Time limit per question in seconds (defaults to first value in config)
        
    Returns:
        str: Formatted message text with quiz information
    """
    safe_topic_name = escape(topic_name or "موضوع ناشناس")
    safe_topic_description = escape(topic_description or "بدون توضیحات")

    if question_count is None or question_count not in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
        question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
    
    if time_limit is None or time_limit not in config.QUIZ_TIME_LIMIT_LIST:
        time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
    
    message_text = QUIZ_INFO_TEMPLATE.format(
        topic_name=safe_topic_name,
        topic_description=safe_topic_description,
        question_count=question_count,
        time_limit=time_limit
    ) + SPONSOR_FOOTER
    
    return message_text


def create_quiz_keyboard_for_existing(
    topic_id: str, 
    user_id: Union[int, str], 
    quiz_id: str, 
    question_count: int, 
    time_limit: int
) -> InlineKeyboardMarkup:
    """
    Create quiz keyboard for an existing quiz with selected options.
    
    Args:
        topic_id: Topic ID
        user_id: User ID
        quiz_id: Quiz ID
        question_count: Selected question count
        time_limit: Selected time limit
        
    Returns:
        InlineKeyboardMarkup: Updated keyboard
    """
    buttons = []
    
    start_data = f"{ButtonType.START}:{topic_id}:{user_id}:{quiz_id}:{question_count}:{time_limit}"
    join_data = f"{ButtonType.JOIN}:{topic_id}:{user_id}:{quiz_id}"
    buttons.append(create_button_row(
        COMMON_MESSAGES["start_quiz"], start_data,
        COMMON_MESSAGES["join_quiz"], join_data
    ))
    
    if config.QUIZ_COUNT_OF_QUESTIONS_LIST:
        count_buttons = create_option_buttons(
            config.QUIZ_COUNT_OF_QUESTIONS_LIST,
            ButtonType.QUESTION_COUNT,
            topic_id, user_id, quiz_id,
            question_count,
            format_count_button
        )
        buttons.append(count_buttons)
    
    if config.QUIZ_TIME_LIMIT_LIST:
        time_buttons = create_option_buttons(
            config.QUIZ_TIME_LIMIT_LIST,
            ButtonType.TIME_LIMIT,
            topic_id, user_id, quiz_id,
            time_limit,
            format_time_button
        )
        buttons.append(time_buttons)
    
    buttons.append([
        InlineKeyboardButton(
            text=COMMON_MESSAGES["sponsor_channel"],
            url=config.SPONSOR_CHANNEL_URL
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_topic_name(topic_id: str) -> str:
    """
    Get topic name from database by ID.
    
    Args:
        topic_id: Topic ID to retrieve
        
    Returns:
        str: Topic name or default "Unknown Topic" if not found
    """
    from bot import db  # Lazy import to avoid circular imports
    
    topic_name = "موضوع ناشناس"
    try:
        topic_info = db.get_topic_by_id(topic_id)
        if topic_info.get("status") == "success":
            topic_name = topic_info.get("topic", {}).get("name", "موضوع ناشناس")
            topic_description = topic_info.get("topic", {}).get("description", "بدون توضیحات")
    except Exception as e:
        logger.error(f"Error retrieving topic name: {e}")
    
    return topic_name, topic_description


def get_message_for_active_quiz(
    quiz_id: str, 
    user_id: str, 
    topic_name: str, 
    question_count: int, 
    time_limit: int
) -> str:
    """
    Create a message for an active quiz with participants list.
    
    Args:
        quiz_id: Quiz ID
        user_id: User ID (creator)
        topic_name: Topic name
        question_count: Question count
        time_limit: Time limit
        
    Returns:
        str: Formatted message with participants list
    """
    participants_count = len(active_quizzes[quiz_id]["participants"])
    participants_list = format_participants_list(active_quizzes[quiz_id]["participants"], user_id)
    
    message_text = COMMON_MESSAGES["quiz_info_with_participants"].format(
        topic_name=escape(topic_name),
        question_count=question_count,
        time_limit=time_limit,
        participant_count=participants_count,
        participants_list=participants_list
    )
    
    current_time = datetime.now().strftime("%H:%M:%S")
    return message_text + COMMON_MESSAGES["last_updated"].format(update_time=current_time)


async def update_quiz_settings(
    callback, 
    topic_id: str, 
    user_id: str, 
    quiz_id: str, 
    question_count: int, 
    time_limit: int
) -> None:
    """
    Update quiz settings and refresh the inline message with new information.
    
    This function:
    1. Updates the settings in memory stores (active_quizzes, quiz_settings)
    2. Creates a new message text based on current state
    3. Updates the inline message with new text and keyboard
    
    Args:
        callback: Callback query object with bot and inline_message_id
        topic_id: Topic ID
        user_id: User ID (creator)
        quiz_id: Quiz ID 
        question_count: Selected question count
        time_limit: Selected time limit per question in seconds
    
    Raises:
        Exception: Any error during update process
    """
    try:
        topic_name, topic_description = await get_topic_name(topic_id)
        
        quiz_settings[quiz_id] = {
            "question_count": question_count,
            "time_limit": time_limit
        }
        
        if quiz_id in active_quizzes:
            active_quizzes[quiz_id]["question_count"] = question_count
            active_quizzes[quiz_id]["time_limit"] = time_limit
            
            message_text = get_message_for_active_quiz(
                quiz_id, user_id, topic_name, question_count, time_limit
            )
        else:
            message_text = create_quiz_message(
                topic_name=topic_name,
                topic_description=topic_description,
                question_count=question_count,
                time_limit=time_limit
            )
        
        keyboard = create_quiz_keyboard_for_existing(
            topic_id=topic_id,
            user_id=user_id,
            quiz_id=quiz_id,
            question_count=question_count,
            time_limit=time_limit
        )
        
        if not hasattr(callback, 'inline_message_id') or not callback.inline_message_id:
            logger.warning("Cannot update message: No inline_message_id available")
            return
            
        await callback.bot.edit_message_text(
            inline_message_id=callback.inline_message_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error updating quiz settings: {e}")
        raise
