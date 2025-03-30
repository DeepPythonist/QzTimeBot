from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from html import escape
import config
from aiogram.fsm.storage.memory import MemoryStorage
from bot import db, bot
from datetime import datetime
from aiogram.enums import ParseMode
from utils import limit_user_requests, active_quizzes, quiz_settings, SPONSOR_FOOTER, format_participants_list, COMMON_MESSAGES
from typing import Dict, List, Any, Optional, Union, Tuple
from plugins.search_quiz import update_quiz_settings

logger = logging.getLogger(__name__)

# Join quiz router
join_quiz_router = Router(name="join_quiz")

# Constant messages
MESSAGES = {
    "topic_not_found": "❌ موضوع مورد نظر یافت نشد! لطفاً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "quiz_not_found": "❌ کوئیز مورد نظر یافت نشد! لطفاً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "already_joined": "⚠️ شما قبلاً به این کوئیز پیوسته‌اید!" + SPONSOR_FOOTER,
    "join_success": "✅ شما با موفقیت به کوئیز پیوستید!",
    "creator_message": "👑 شما سازنده این کوئیز هستید و در حال حاضر در آن شرکت دارید!" + SPONSOR_FOOTER,
    "sponsor_required": "🔒 ابتدا در کانال اسپانسر عضو شوید سپس مجددا برای عضویت در کوییز تلاش",
    "invalid_quiz_data": "❌ اطلاعات کوئیز نامعتبر است",
    "no_participants": "👥 هنوز شرکت‌کننده‌ای وجود ندارد",
    "other_participants": "... و {count} نفر دیگر",
    "creator_label": "{name} 👑 (سازنده)"
}

# استفاده از پیام‌های مشترک
MESSAGES.update({
    "start_quiz": COMMON_MESSAGES["start_quiz"],
    "join_quiz": COMMON_MESSAGES["join_quiz"],
    "sponsor_channel": COMMON_MESSAGES["sponsor_channel"],
    "last_updated": COMMON_MESSAGES["last_updated"]
})


def get_quiz_keyboard(creator_id: Union[int, str], topic_id: str, quiz_id: str) -> InlineKeyboardMarkup:
    """
    Create a keyboard for quiz with start, join, and sponsor buttons
    
    Args:
        creator_id: ID of the user who created the quiz
        topic_id: Topic ID
        quiz_id: Quiz ID
        
    Returns:
        InlineKeyboardMarkup: Prepared keyboard with buttons
    """
    # استخراج تنظیمات از active_quizzes
    question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
    time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
    
    # اگر کوییز در active_quizzes وجود دارد، تنظیمات را از آن بگیریم
    if quiz_id in active_quizzes:
        question_count = active_quizzes[quiz_id].get("question_count", question_count)
        time_limit = active_quizzes[quiz_id].get("time_limit", time_limit)
        
    # Create main buttons
    buttons = [
        [
            InlineKeyboardButton(
                text=MESSAGES["start_quiz"],
                callback_data=f"quiz_start:{topic_id}:{creator_id}:{quiz_id}:{question_count}:{time_limit}"
            ),
            InlineKeyboardButton(
                text=MESSAGES["join_quiz"],
                callback_data=f"quiz_join:{topic_id}:{creator_id}:{quiz_id}"
            )
        ]
    ]
    
    # افزودن دکمه‌های تعداد سوالات با نشانگر انتخاب فعلی
    question_count_buttons = []
    for count in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
        selected = "✅" if count == question_count else ""
        button = InlineKeyboardButton(
            text=COMMON_MESSAGES["question_count_btn"].format(count=count, selected=selected),
            callback_data=f"quiz_qcount:{topic_id}:{creator_id}:{quiz_id}:{count}"
        )
        question_count_buttons.append(button)
    
    # افزودن دکمه‌های تعداد سوالات
    if question_count_buttons:
        buttons.append(question_count_buttons)
    
    # افزودن دکمه‌های محدودیت زمانی با نشانگر انتخاب فعلی
    time_limit_buttons = []
    for limit in config.QUIZ_TIME_LIMIT_LIST:
        selected = "✅" if limit == time_limit else ""
        button = InlineKeyboardButton(
            text=COMMON_MESSAGES["time_limit_btn"].format(limit=limit, selected=selected),
            callback_data=f"quiz_tlimit:{topic_id}:{creator_id}:{quiz_id}:{limit}"
        )
        time_limit_buttons.append(button)
    
    # افزودن دکمه‌های محدودیت زمانی
    if time_limit_buttons:
        buttons.append(time_limit_buttons)
    
    # افزودن دکمه اسپانسر
    buttons.append([
        InlineKeyboardButton(
            text=MESSAGES["sponsor_channel"],
            url=f"{config.SPONSOR_CHANNEL_URL}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_topic_info(topic_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get topic information from the database
    
    Args:
        topic_id: Topic ID to retrieve
        
    Returns:
        Tuple[Optional[Dict], Optional[str]]: Topic data and topic name or None if not found
    """
    topic_result = db.get_topic_by_id(topic_id)
    
    if topic_result.get("status") != "success":
        return None, None
    
    topic = topic_result["topic"]
    topic_name = topic.get("name", "Unknown Topic")
    
    # If name is still not found, use a default based on topic ID
    if not topic_name or topic_name == "Unknown Topic":
        topic_name = f"Topic {topic_id[:6]}"
    
    return topic, topic_name


async def update_quiz_message(callback: CallbackQuery, quiz_id: str, topic_name: str, creator_id: Union[int, str]) -> None:
    """
    Update the quiz message with current information
    
    Args:
        callback: Callback query that triggered the update
        quiz_id: ID of the quiz to update
        topic_name: Name of the quiz topic
        creator_id: ID of the quiz creator
    """
    try:
        # Get data from cache
        quiz_data = active_quizzes[quiz_id]

        
        # Question count and time limit from quiz data or config
        question_count = quiz_data.get("question_count", config.QUIZ_COUNT_OF_QUESTIONS_LIST[0])
        time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT_LIST[0])
        
        # Format participant list and count
        participants_count = len(quiz_data["participants"])
        participants_list = format_participants_list(quiz_data["participants"], creator_id)
        
        # Complete message text
        message_text = COMMON_MESSAGES["quiz_info_with_participants"].format(
            topic_name=escape(topic_name),
            question_count=question_count,
            time_limit=time_limit,
            participant_count=participants_count,
            participants_list=participants_list
        )
        
        # Add timestamp
        current_time = datetime.now().strftime("%H:%M:%S")
        message_text += MESSAGES["last_updated"].format(update_time=current_time)
        
        # Quiz keyboard
        reply_markup = get_quiz_keyboard(creator_id, quiz_data["topic_id"], quiz_id)
        
        # Update message using the appropriate method
        try:
            # Method 1: Use message in callback
            if hasattr(callback, 'message') and callback.message:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            # Method 2: Use inline_message_id
            elif hasattr(callback, 'inline_message_id') and callback.inline_message_id:
                await callback.bot.edit_message_text(
                    inline_message_id=callback.inline_message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            # Method 3: Send new message to user
            elif hasattr(callback, 'from_user'):
                user_id = callback.from_user.id
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        except Exception as edit_error:
            # Log error but don't send to user
            logger.error(f"Failed to update message: {edit_error}")
            
    except Exception as e:
        logger.error(f"Error updating quiz message: {e}")


@join_quiz_router.callback_query(F.data.startswith("quiz_join:"))
@limit_user_requests(seconds=2)
async def join_quiz(callback: CallbackQuery) -> None:
    """
    Handle join quiz button click
    
    Args:
        callback: Callback query from the join button
    """
    # Immediately answer callback to prevent timeout error
    success_message = MESSAGES["join_success"]
    
    try:
        # Extract information from callback data
        data = callback.data.split(":")
        if len(data) < 4:
            await callback.answer(MESSAGES["invalid_quiz_data"], show_alert=True)
            return
        
        # Check user membership in sponsor channel
        is_member = await check_user_membership(callback.from_user.id)
        if not is_member:
            # User is not a member of sponsor channel - show alert message
            await callback.answer(MESSAGES["sponsor_required"], show_alert=True)
            return
        
        topic_id = data[1]
        creator_id = int(data[2])  # Convert to integer
        quiz_id = data[3]

        if quiz_id in active_quizzes:
            if callback.from_user.id in active_quizzes[quiz_id]["participants"]:
                await callback.answer(MESSAGES["already_joined"], show_alert=True)
                return
        
        # Show success message to user (before lengthy operations)
        await callback.answer(success_message, show_alert=True)
        
        # Create user in database if needed
        db.create_user(user_id=callback.from_user.id, 
                       username=callback.from_user.username if callback.from_user.username else None,
                       full_name=callback.from_user.full_name if callback.from_user.full_name else "",
                       has_start=None)
            
        
        # Current user information
        current_user_id = callback.from_user.id
        current_user_full_name = callback.from_user.full_name or f"User {current_user_id}"
        
        # Check if user is the creator
        is_creator = current_user_id == creator_id
        
        # Check if quiz exists in memory
        if quiz_id in active_quizzes:
            # If user is the creator
            if is_creator:
                # Update creator name if it was unknown
                creator_info = active_quizzes[quiz_id]["participants"].get(creator_id, {})
                if creator_info.get("full_name") == f"User {creator_id}" or creator_info.get("full_name") == "Quiz Creator":
                    active_quizzes[quiz_id]["participants"][creator_id]["full_name"] = current_user_full_name
                
                # User already received the message, just update it
                await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
                return
                
            # Check if already joined
            if current_user_id in active_quizzes[quiz_id]["participants"]:
                # User already joined, just update the message
                await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
                return
                
            # Get topic information (if needed)
            topic_name = active_quizzes[quiz_id]["topic_name"]
            if not topic_name or topic_name == "Unknown Topic":
                # If topic name is not saved, get from database
                _, new_topic_name = get_topic_info(topic_id)
                if new_topic_name:
                    active_quizzes[quiz_id]["topic_name"] = new_topic_name
                    topic_name = new_topic_name
        else:
            # Get topic information from database for new quiz
            _, topic_name = get_topic_info(topic_id)
            if topic_name is None:
                logger.error(f"Topic {topic_id} not found when creating new quiz")
                return
            
            # Set creator name
            creator_full_name = current_user_full_name if is_creator else f"User {creator_id}"
            
            # استفاده از تنظیمات موجود در quiz_settings اگر وجود داشته باشد
            default_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
            default_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
            
            if quiz_id in quiz_settings:
                question_count = quiz_settings[quiz_id].get("question_count", default_question_count)
                time_limit = quiz_settings[quiz_id].get("time_limit", default_time_limit)
            else:
                question_count = default_question_count
                time_limit = default_time_limit
            
            # Create new quiz in memory
            active_quizzes[quiz_id] = {
                "creator_id": creator_id,
                "topic_id": topic_id,
                "topic_name": topic_name,
                # Store creator's Telegram ID
                "creator_telegram_id": current_user_id if is_creator else creator_id,
                # استفاده از تنظیمات ذخیره شده به جای مقادیر پیش‌فرض
                "question_count": question_count,
                "time_limit": time_limit,
                "participants": {
                    creator_id: {  # Creator is already a member
                        "full_name": creator_full_name,
                        "total_correct": 0,
                        "total_wrong": 0,
                        "total_points": 0,
                    }
                }
            }
            
            # If current user is creator, show appropriate message and exit
            if is_creator:
                await update_quiz_message(callback, quiz_id, topic_name, creator_id)
                return
        
        # Add user to participant list
        active_quizzes[quiz_id]["participants"][current_user_id] = {
            "full_name": current_user_full_name,
            "total_correct": 0,
            "total_wrong": 0,
            "total_points": 0,
        }
        
        # Print information for debugging
        logger.debug(f"Added user to quiz: {active_quizzes[quiz_id]}")
        
        # Update message with quiz details
        await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
        
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error in join_quiz: {e}")


async def check_bot_is_admin(channel_id=config.SPONSOR_CHANNEL_ID) -> bool:
    """
    Check if the bot is an admin in the specified channel.
    
    Args:
        channel_id: ID of the channel to check
        
    Returns:
        bool: True if bot is admin, False otherwise
    """
    try:
        bot_is_admin = await bot.get_chat_member(chat_id=channel_id, user_id=config.BOT_USER_ID)
        if bot_is_admin.status in ["administrator", "creator"]:
            return True
        else:
            logger.warning(f"Bot is not admin in channel {channel_id}")
            return False
    except Exception as e:
        logger.error(f"Error checking bot admin status: {e}")
        return False
    

async def check_user_membership(user_id: int, channel_id=config.SPONSOR_CHANNEL_ID) -> bool:
    """
    Check if the user is a member of the specified channel.
    
    Args:
        user_id: User ID to check
        channel_id: ID of the channel to check
        
    Returns:
        bool: True if user is a member or bot is not admin, False otherwise
    """
    try:
        # First check if bot is admin in the channel
        if await check_bot_is_admin(channel_id):
            # Bot is admin, so we can check user membership
            user_status = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if user_status.status in ["member", "administrator", "creator"]:
                logger.info(f"User {user_id} is a member of channel {channel_id}")
                return True
            else:
                logger.info(f"User {user_id} is NOT a member of channel {channel_id}")
                return False
        else:
            # Bot is not admin, assume user is a member
            logger.warning(f"Cannot check membership of user {user_id} because bot is not admin")
            return True
    except Exception as e:
        logger.error(f"Error checking user membership: {e}")
        return False
    
    
