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

join_quiz_router = Router(name="join_quiz")

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


MESSAGES.update({
    "start_quiz": COMMON_MESSAGES["start_quiz"],
    "join_quiz": COMMON_MESSAGES["join_quiz"],
    "sponsor_channel": COMMON_MESSAGES["sponsor_channel"],
    "last_updated": COMMON_MESSAGES["last_updated"]
})


def get_quiz_keyboard(creator_id: Union[int, str], topic_id: str, quiz_id: str) -> InlineKeyboardMarkup:

    question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
    time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
    
    if quiz_id in active_quizzes:
        question_count = active_quizzes[quiz_id].get("question_count", question_count)
        time_limit = active_quizzes[quiz_id].get("time_limit", time_limit)
        

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
    
    question_count_buttons = []
    for count in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
        selected = "✅" if count == question_count else ""
        button = InlineKeyboardButton(
            text=COMMON_MESSAGES["question_count_btn"].format(count=count, selected=selected),
            callback_data=f"quiz_qcount:{topic_id}:{creator_id}:{quiz_id}:{count}"
        )
        question_count_buttons.append(button)
    
    if question_count_buttons:
        buttons.append(question_count_buttons)
    
    time_limit_buttons = []
    for limit in config.QUIZ_TIME_LIMIT_LIST:
        selected = "✅" if limit == time_limit else ""
        button = InlineKeyboardButton(
            text=COMMON_MESSAGES["time_limit_btn"].format(limit=limit, selected=selected),
            callback_data=f"quiz_tlimit:{topic_id}:{creator_id}:{quiz_id}:{limit}"
        )
        time_limit_buttons.append(button)
    
    if time_limit_buttons:
        buttons.append(time_limit_buttons)
    
    buttons.append([
        InlineKeyboardButton(
            text=MESSAGES["sponsor_channel"],
            url=f"{config.SPONSOR_CHANNEL_URL}"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_topic_info(topic_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:

    topic_result = db.get_topic_by_id(topic_id)
    
    if topic_result.get("status") != "success":
        return None, None
    
    topic = topic_result["topic"]
    topic_name = topic.get("name", "Unknown Topic")
    
    if not topic_name or topic_name == "Unknown Topic":
        topic_name = f"Topic {topic_id[:6]}"
    
    return topic, topic_name


async def update_quiz_message(callback: CallbackQuery, quiz_id: str, topic_name: str, creator_id: Union[int, str]) -> None:

    try:
        quiz_data = active_quizzes[quiz_id]

        
        question_count = quiz_data.get("question_count", config.QUIZ_COUNT_OF_QUESTIONS_LIST[0])
        time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT_LIST[0])
        
        participants_count = len(quiz_data["participants"])
        participants_list = format_participants_list(quiz_data["participants"], creator_id)
        
        message_text = COMMON_MESSAGES["quiz_info_with_participants"].format(
            topic_name=escape(topic_name),
            question_count=question_count,
            time_limit=time_limit,
            participant_count=participants_count,
            participants_list=participants_list
        )
        
        current_time = datetime.now().strftime("%H:%M:%S")
        message_text += MESSAGES["last_updated"].format(update_time=current_time)
        
        reply_markup = get_quiz_keyboard(creator_id, quiz_data["topic_id"], quiz_id)
        
        try:
            if hasattr(callback, 'message') and callback.message:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            elif hasattr(callback, 'inline_message_id') and callback.inline_message_id:
                await callback.bot.edit_message_text(
                    inline_message_id=callback.inline_message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            elif hasattr(callback, 'from_user'):
                user_id = callback.from_user.id
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        except Exception as edit_error:
            logger.error(f"Failed to update message: {edit_error}")
            
    except Exception as e:
        logger.error(f"Error updating quiz message: {e}")


@join_quiz_router.callback_query(F.data.startswith("quiz_join:"))
@limit_user_requests(seconds=2)
async def join_quiz(callback: CallbackQuery) -> None:

    success_message = MESSAGES["join_success"]
    
    try:
        data = callback.data.split(":")
        if len(data) < 4:
            await callback.answer(MESSAGES["invalid_quiz_data"], show_alert=True)
            return

        is_member = await check_user_membership(callback.from_user.id)
        if not is_member:
            await callback.answer(MESSAGES["sponsor_required"], show_alert=True)
            return
        
        topic_id = data[1]
        creator_id = int(data[2])
        quiz_id = data[3]

        if quiz_id in active_quizzes:
            if callback.from_user.id in active_quizzes[quiz_id]["participants"]:
                await callback.answer(MESSAGES["already_joined"], show_alert=True)
                return
        
        await callback.answer(success_message, show_alert=True)
        
        db.create_user(user_id=callback.from_user.id, 
                       username=callback.from_user.username if callback.from_user.username else None,
                       full_name=callback.from_user.full_name if callback.from_user.full_name else "",
                       has_start=None)
            
        
        current_user_id = callback.from_user.id
        current_user_full_name = callback.from_user.full_name or f"User {current_user_id}"
        
        is_creator = current_user_id == creator_id
        
        if quiz_id in active_quizzes:
            if is_creator:
                creator_info = active_quizzes[quiz_id]["participants"].get(creator_id, {})
                if creator_info.get("full_name") == f"User {creator_id}" or creator_info.get("full_name") == "Quiz Creator":
                    active_quizzes[quiz_id]["participants"][creator_id]["full_name"] = current_user_full_name
                
                await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
                return
                
            if current_user_id in active_quizzes[quiz_id]["participants"]:
                await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
                return
                
            topic_name = active_quizzes[quiz_id]["topic_name"]
            if not topic_name or topic_name == "Unknown Topic":
                _, new_topic_name = get_topic_info(topic_id)
                if new_topic_name:
                    active_quizzes[quiz_id]["topic_name"] = new_topic_name
                    topic_name = new_topic_name
        else:
            _, topic_name = get_topic_info(topic_id)
            if topic_name is None:
                logger.error(f"Topic {topic_id} not found when creating new quiz")
                return
            
            creator_full_name = current_user_full_name if is_creator else f"User {creator_id}"
            
            default_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
            default_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
            
            if quiz_id in quiz_settings:
                question_count = quiz_settings[quiz_id].get("question_count", default_question_count)
                time_limit = quiz_settings[quiz_id].get("time_limit", default_time_limit)
            else:
                question_count = default_question_count
                time_limit = default_time_limit
            
            active_quizzes[quiz_id] = {
                "creator_id": creator_id,
                "topic_id": topic_id,
                "topic_name": topic_name,
                "creator_telegram_id": current_user_id if is_creator else creator_id,
                "question_count": question_count,
                "time_limit": time_limit,
                "participants": {
                    creator_id: {
                        "full_name": creator_full_name,
                        "total_correct": 0,
                        "total_wrong": 0,
                        "total_points": 0,
                    }
                }
            }
            
            if is_creator:
                await update_quiz_message(callback, quiz_id, topic_name, creator_id)
                return
        
        active_quizzes[quiz_id]["participants"][current_user_id] = {
            "full_name": current_user_full_name,
            "total_correct": 0,
            "total_wrong": 0,
            "total_points": 0,
        }
        
        logger.debug(f"Added user to quiz: {active_quizzes[quiz_id]}")
        
        await update_quiz_message(callback, quiz_id, active_quizzes[quiz_id]["topic_name"], creator_id)
        
    except Exception as e:
        logger.error(f"Error in join_quiz: {e}")


async def check_bot_is_admin(channel_id=config.SPONSOR_CHANNEL_ID) -> bool:

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

    try:
        if await check_bot_is_admin(channel_id):
            user_status = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if user_status.status in ["member", "administrator", "creator"]:
                logger.info(f"User {user_id} is a member of channel {channel_id}")
                return True
            else:
                logger.info(f"User {user_id} is NOT a member of channel {channel_id}")
                return False
        else:
            logger.warning(f"Cannot check membership of user {user_id} because bot is not admin")
            return True
    except Exception as e:
        logger.error(f"Error checking user membership: {e}")
        return False
    
    
