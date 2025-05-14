from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
import logging
import config
from bot import db, bot
from utils import limit_user_requests
from .join_quiz import active_quizzes
import random
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Union, Optional

logger = logging.getLogger(__name__)


start_quiz_router = Router(name="start_quiz")

SPONSOR_FOOTER = f" "


MESSAGES = {
    "invalid_format": "❌ فرمت کوئیز نامعتبر است، لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "creator_only": "⚠️ فقط سازنده کوئیز می‌تواند کوئیز را شروع کند.",
    "need_players": "👥 برای شروع کوئیز، حداقل به ۲ شرکت‌کننده نیاز است.",
    "quiz_not_found": "⚠️ این کوئیز هیچ شرکت‌کننده‌ای ندارد.\nابتدا به کوئیز بپیوندید." + SPONSOR_FOOTER,
    "error_general": "❌ خطایی رخ داده است. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "not_enough_questions": "⚠️ تعداد سؤالات کافی در این موضوع وجود ندارد." + SPONSOR_FOOTER,
    
    "invalid_data": "❌ داده نامعتبر",
    "quiz_not_found_alert": "❌ کوئیز یافت نشد",
    "quiz_not_active": "⚠️ کوئیز در حال حاضر فعال نیست",
    "question_not_active": "⏱ این سؤال دیگر فعال نیست",
    "not_a_participant": "👤 شما در این کوئیز شرکت نکرده‌اید",
    "already_answered": "🔄 شما قبلاً به این سؤال پاسخ داده‌اید",
    "answer_error": "❌ خطا در پردازش پاسخ شما",
    
    "correct_answer": "✅ پاسخ صحیح! شما {points} امتیاز کسب کردید.",
    "wrong_answer": "❌ پاسخ اشتباه. گزینه صحیح {correct_option} بود.",
    
    "quiz_started": "🎮 کوئیز تا ۳ ثانیه دیگر شروع می‌شود..." + SPONSOR_FOOTER,
    "question_prompt": """
📝 <b>سوال {current}/{total}:</b>

{question_text}

<b>گزینه‌ها:</b>
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

⏱ زمان باقیمانده: {time_limit} ثانیه""" + SPONSOR_FOOTER,
    "time_expired": "⏱ زمان تمام شد! پاسخ صحیح گزینه {correct_option} بود." + SPONSOR_FOOTER,
    "quiz_completed": """
🏁 <b>کوییز پایان یافت!</b>

<b>🏆 جدول امتیازات:</b>
{leaderboard}

🙏 با تشکر از شرکت شما!""" + SPONSOR_FOOTER,
    "waiting_for_next": """⏳ سوال بعدی در {seconds} ثانیه دیگر...

<b>🏆 رده‌بندی فعلی:</b>
{top_players}""" + SPONSOR_FOOTER
}

def get_options_keyboard(quiz_id: str, question_id: str) -> InlineKeyboardMarkup:

    kb = InlineKeyboardBuilder()
    
    for i in range(4):
        kb.button(
            text=str(i + 1),
            callback_data=f"quiz_answer:{quiz_id}:{question_id}:{i}"
        )
    
    kb.adjust(4)
    return kb.as_markup()

def get_final_keyboard(topic_id: str) -> InlineKeyboardMarkup:

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🔄 بازی مجدد",
                switch_inline_query_current_chat=f"quiz_{topic_id}"
            ),
            InlineKeyboardButton(
                text=f"👑 {config.SPONSOR_CHANNEL_NAME}",
                url=config.SPONSOR_CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{config.BOT_NAME}",
                url=f"https://t.me/{config.BOT_USERNAME}"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_leaderboard(participants: Dict[int, Dict[str, Any]]) -> str:
 
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1]["total_points"],
        reverse=True
    )
    
    leaderboard_lines = []
    for i, (user_id, user_data) in enumerate(sorted_participants):
        medal = ""
        if i == 0: medal = "🥇 "
        elif i == 1: medal = "🥈 "
        elif i == 2: medal = "🥉 "
        
        line = f"{medal}{i+1}. {user_data['full_name']}: {user_data['total_points']} ⭐️ ({user_data['total_correct']} ✔️ {user_data['total_wrong']} ✖️)"
        leaderboard_lines.append(line)
    
    return "\n".join(leaderboard_lines)

def format_top_players(participants: Dict[int, Dict[str, Any]], max_players: int = 10) -> str:
 
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1]["total_points"],
        reverse=True
    )
    
    total_participants = len(sorted_participants)
    
    top_participants = sorted_participants[:max_players]
    
    leaderboard_lines = []
    for i, (user_id, user_data) in enumerate(top_participants):
        medal = ""
        if i == 0: medal = "🥇 "
        elif i == 1: medal = "🥈 "
        elif i == 2: medal = "🥉 "
        
        line = f"{medal}{i+1}. {user_data['full_name']}: {user_data['total_points']} ⭐️"
        leaderboard_lines.append(line)
    
    leaderboard_text = "\n".join(leaderboard_lines)
    
    remaining_count = total_participants - min(max_players, total_participants)
    remaining_text = f"\n+ {remaining_count} کاربر دیگر" if remaining_count > 0 else ""
    
    return leaderboard_text + remaining_text

@start_quiz_router.callback_query(F.data.startswith("quiz_start"))
@limit_user_requests(seconds=2)
async def start_quiz(callback: CallbackQuery) -> None:

    try:
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer(MESSAGES["invalid_format"], show_alert=True)
            return
       
        quiz_topic_id = parts[1]
        quiz_creator_id = parts[2]
        quiz_id = parts[3]
        
        quiz_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]  # مقدار پیش‌فرض
        quiz_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]  # مقدار پیش‌فرض
        
        if len(parts) >= 6:
            try:
                quiz_question_count = int(parts[4])
                quiz_time_limit = int(parts[5])
                
                if quiz_question_count not in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
                    quiz_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
                
                if quiz_time_limit not in config.QUIZ_TIME_LIMIT_LIST:
                    quiz_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
            except (ValueError, IndexError) as e:
                logger.error(f"Error extracting settings: {e}")
        
        current_user_id = callback.from_user.id
        if str(current_user_id) != str(quiz_creator_id):
            await callback.answer(MESSAGES["creator_only"], show_alert=True)
            return
       
        if quiz_id not in active_quizzes:
            await callback.answer(MESSAGES["quiz_not_found"], show_alert=True)
            return
       
        participants = active_quizzes[quiz_id]["participants"]
        if len(participants) < 2:
            await callback.answer(MESSAGES["need_players"], show_alert=True)
            return
       
        get_questions = db.get_questions_by_topic(quiz_topic_id)
       
        if get_questions.get("status") == "error":
            await bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text=MESSAGES["error_general"],
                parse_mode=ParseMode.HTML
            )
            return
       
        questions = get_questions.get("questions")
        if len(questions) < quiz_question_count:
            await bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text=MESSAGES["not_enough_questions"],
                parse_mode=ParseMode.HTML
            )
            return
       
        random.shuffle(questions)
        selected_questions = questions[:quiz_question_count]
        active_quizzes[quiz_id]["questions"] = selected_questions
        
        active_quizzes[quiz_id]["question_count"] = quiz_question_count
        active_quizzes[quiz_id]["time_limit"] = quiz_time_limit

        db.update_quiz_created(quiz_creator_id)
        db.update_topic_played(quiz_topic_id)
        await asyncio.create_task(send_quiz_message(active_quizzes[quiz_id], callback))
    except Exception as e:
        logger.error(f"Error starting quiz: {e}")

@start_quiz_router.callback_query(F.data.startswith("quiz_answer:"))
@limit_user_requests(seconds=2)
async def process_answer(callback: CallbackQuery) -> None:
    try:
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(MESSAGES["invalid_data"], show_alert=True)
            return
            
        quiz_id = parts[1]
        question_id = parts[2]
        selected_option = int(parts[3])
        
        if quiz_id not in active_quizzes:
            await callback.answer(MESSAGES["quiz_not_found_alert"], show_alert=True)
            return
            
        quiz_data = active_quizzes[quiz_id]
        if "current_question" not in quiz_data:
            await callback.answer(MESSAGES["quiz_not_active"], show_alert=True)
            return
            
        if quiz_data["current_question"]["id"] != question_id:
            await callback.answer(MESSAGES["question_not_active"], show_alert=True)
            return
            
        user_id = callback.from_user.id
        if user_id not in quiz_data["participants"]:
            await callback.answer(MESSAGES["not_a_participant"], show_alert=True)
            return
            
        if user_id in quiz_data["current_question"]["answered_users"]:
            await callback.answer(MESSAGES["already_answered"], show_alert=True)
            return
            
        quiz_data["current_question"]["answered_users"].append(user_id)
        
        correct_option = quiz_data["current_question"]["correct_option"]
        is_correct = selected_option == correct_option
        
        now = datetime.now().timestamp()
        elapsed_time = now - quiz_data["current_question"]["start_time"]
        
        time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
        remaining_time = max(0, time_limit - int(elapsed_time))
        
        if is_correct:
            points = 1 + remaining_time
            quiz_data["participants"][user_id]["total_correct"] += 1
            quiz_data["participants"][user_id]["total_points"] += points
            await callback.answer(MESSAGES["correct_answer"].format(points=points), show_alert=True)
        else:
            quiz_data["participants"][user_id]["total_wrong"] += 1
            await callback.answer(MESSAGES["wrong_answer"].format(correct_option=correct_option + 1), show_alert=True)
        
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        await callback.answer(MESSAGES["answer_error"], show_alert=True)

async def send_quiz_message(quiz_data: Dict[str, Any], callback: CallbackQuery) -> None:

    try:
        questions_list = quiz_data["questions"]
        quiz_id = list(active_quizzes.keys())[list(active_quizzes.values()).index(quiz_data)]
        topic_id = quiz_data["topic_id"]
        
        quiz_time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
        
        await update_quiz_message(
            callback=callback,
            text=MESSAGES["quiz_started"]
        )
        
        await asyncio.sleep(3)
        
        for index, question in enumerate(questions_list):
            question_number = index + 1
            total_questions = len(questions_list)
            question_text = question["text"]
            options = question["options"]
            correct_option = question["correct_option"]
            question_id = f"{quiz_id}_{question_number}"
            
            await show_question(
                callback=callback,
                quiz_data=quiz_data,
                question_number=question_number,
                total_questions=total_questions,
                question_text=question_text,
                options=options,
                correct_option=correct_option,
                question_id=question_id
            )
            
            await asyncio.sleep(quiz_time_limit)
            
            for user_id in quiz_data["participants"]:
                if user_id not in quiz_data["current_question"]["answered_users"]:
                    quiz_data["participants"][user_id]["total_wrong"] += 1
            
            if question_number < total_questions:
                await show_intermediate_results(
                    callback=callback,
                    quiz_data=quiz_data,
                    pause_seconds=2
                )
        
        await show_final_results(
            callback=callback,
            quiz_data=quiz_data,
            quiz_id=quiz_id,
            topic_id=topic_id
        )
        
        await update_users_statistics(quiz_data)
        
        cleanup_quiz_data(quiz_data, quiz_id)
        
        logger.info(f"Quiz {quiz_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error sending quiz message: {e}")
        try:
            await update_quiz_message(
                callback=callback,
                text=MESSAGES["error_general"]
            )
        except:
            logger.error("Failed to send error message")


async def update_quiz_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:

    try:
        if callback.inline_message_id:
            await callback.bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif callback.message:
            await callback.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    except TelegramBadRequest as e:
        logger.warning(f"Failed to update quiz message: {e}")


async def show_question(callback: CallbackQuery, quiz_data: Dict[str, Any], question_number: int, 
                        total_questions: int, question_text: str, options: List[str], 
                        correct_option: int, question_id: str) -> None:
 
    time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
    
    question_message = MESSAGES["question_prompt"].format(
        current=question_number,
        total=total_questions,
        question_text=question_text,
        option_1=options[0],
        option_2=options[1],
        option_3=options[2],
        option_4=options[3],
        time_limit=time_limit
    )
    
    keyboard = get_options_keyboard(quiz_id=question_id.split('_')[0], question_id=question_id)
    
    quiz_data["current_question"] = {
        "id": question_id,
        "correct_option": correct_option,
        "start_time": datetime.now().timestamp(),
        "answered_users": []
    }
    
    await update_quiz_message(callback, question_message, keyboard)


async def show_intermediate_results(callback: CallbackQuery, quiz_data: Dict[str, Any], pause_seconds: int) -> None:

    top_players = format_top_players(quiz_data["participants"])
    
    waiting_message = MESSAGES["waiting_for_next"].format(
        seconds=pause_seconds,
        top_players=top_players
    )
    
    await update_quiz_message(callback, waiting_message)
    await asyncio.sleep(pause_seconds)


async def show_final_results(callback: CallbackQuery, quiz_data: Dict[str, Any], quiz_id: str, topic_id: str) -> None:

    leaderboard = format_leaderboard(quiz_data["participants"])
    final_message = MESSAGES["quiz_completed"].format(leaderboard=leaderboard)
    

    final_keyboard = get_final_keyboard(topic_id)
    

    await update_quiz_message(callback, final_message, final_keyboard)


async def update_users_statistics(quiz_data: Dict[str, Any]) -> None:

    for user_id, user_data in quiz_data["participants"].items():
        result = db.update_user_stats(
            user_id=str(user_id),
            correct_count=user_data["total_correct"],
            wrong_count=user_data["total_wrong"],
            points=user_data["total_points"]
        )
        if result.get("status") != "success":
            logger.warning(f"Failed to update stats for user {user_id}: {result.get('message')}")
        else:
            logger.info(f"Updated stats for user {user_id}")


def cleanup_quiz_data(quiz_data: Dict[str, Any], quiz_id: str) -> None:

    if "current_question" in quiz_data:
        del quiz_data["current_question"]
    
    if quiz_id in active_quizzes:
        del active_quizzes[quiz_id]
        logger.info(f"Quiz {quiz_id} removed from active quizzes")



