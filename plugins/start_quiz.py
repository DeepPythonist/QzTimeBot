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

# روتر شروع کوییز
start_quiz_router = Router(name="start_quiz")

# فوتر اسپانسر که به انتهای همه پیام‌ها اضافه می‌شود
SPONSOR_FOOTER = f" "

# پیام‌های ثابت
MESSAGES = {
    # پیام‌های خطا و اطلاع‌رسانی
    "invalid_format": "❌ فرمت کوئیز نامعتبر است، لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "creator_only": "⚠️ فقط سازنده کوئیز می‌تواند کوئیز را شروع کند.",
    "need_players": "👥 برای شروع کوئیز، حداقل به ۲ شرکت‌کننده نیاز است.",
    "quiz_not_found": "⚠️ این کوئیز هیچ شرکت‌کننده‌ای ندارد.\nابتدا به کوئیز بپیوندید." + SPONSOR_FOOTER,
    "error_general": "❌ خطایی رخ داده است. لطفاً بعداً دوباره تلاش کنید." + SPONSOR_FOOTER,
    "not_enough_questions": "⚠️ تعداد سؤالات کافی در این موضوع وجود ندارد." + SPONSOR_FOOTER,
    
    # پیام‌های پاسخ callback
    "invalid_data": "❌ داده نامعتبر",
    "quiz_not_found_alert": "❌ کوئیز یافت نشد",
    "quiz_not_active": "⚠️ کوئیز در حال حاضر فعال نیست",
    "question_not_active": "⏱ این سؤال دیگر فعال نیست",
    "not_a_participant": "👤 شما در این کوئیز شرکت نکرده‌اید",
    "already_answered": "🔄 شما قبلاً به این سؤال پاسخ داده‌اید",
    "answer_error": "❌ خطا در پردازش پاسخ شما",
    
    # پیام‌های پاسخ به کاربر
    "correct_answer": "✅ پاسخ صحیح! شما {points} امتیاز کسب کردید.",
    "wrong_answer": "❌ پاسخ اشتباه. گزینه صحیح {correct_option} بود.",
    
    # پیام‌های کوییز
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

# ساخت کیبورد گزینه‌ها
def get_options_keyboard(quiz_id: str, question_id: str) -> InlineKeyboardMarkup:
    """
    Create a keyboard for question options with buttons from 1 to 4.
    
    Args:
        quiz_id: Unique quiz identifier
        question_id: Unique question identifier
        
    Returns:
        InlineKeyboardMarkup: Keyboard with option buttons
    """
    kb = InlineKeyboardBuilder()
    
    # دکمه‌های گزینه‌ها با شماره 1 تا 4
    for i in range(4):
        kb.button(
            text=str(i + 1),
            callback_data=f"quiz_answer:{quiz_id}:{question_id}:{i}"
        )
    
    kb.adjust(4)  # 4 دکمه در یک ردیف
    return kb.as_markup()

# ساخت کیبورد پایان کوییز با دکمه اسپانسر و بازی مجدد
def get_final_keyboard(topic_id: str) -> InlineKeyboardMarkup:
    """
    Create a final keyboard with replay and sponsor buttons.
    
    Args:
        topic_id: Topic ID for the quiz
        
    Returns:
        InlineKeyboardMarkup: Keyboard with replay and sponsor buttons
    """
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
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# فرمت‌بندی جدول امتیازات نهایی
def format_leaderboard(participants: Dict[int, Dict[str, Any]]) -> str:
    """
    Create a formatted text of final leaderboard sorted by points.
    
    Args:
        participants: Dictionary of participants and their information
        
    Returns:
        str: Formatted leaderboard text
    """
    # مرتب‌سازی براساس امتیاز کل
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1]["total_points"],
        reverse=True
    )
    
    leaderboard_lines = []
    for i, (user_id, user_data) in enumerate(sorted_participants):
        # افزودن مدال برای سه نفر اول
        medal = ""
        if i == 0: medal = "🥇 "
        elif i == 1: medal = "🥈 "
        elif i == 2: medal = "🥉 "
        
        line = f"{medal}{i+1}. {user_data['full_name']}: {user_data['total_points']} امتیاز ({user_data['total_correct']} صحیح، {user_data['total_wrong']} غلط)"
        leaderboard_lines.append(line)
    
    return "\n".join(leaderboard_lines)

# فرمت‌بندی 10 نفر برتر موقت
def format_top_players(participants: Dict[int, Dict[str, Any]], max_players: int = 10) -> str:
    """
    Create a formatted text of top players sorted by points.
    
    Args:
        participants: Dictionary of participants and their information
        max_players: Maximum number of players to display
        
    Returns:
        str: Formatted top players text with remaining count
    """
    # مرتب‌سازی براساس امتیاز کل
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1]["total_points"],
        reverse=True
    )
    
    # تعداد کل شرکت‌کنندگان
    total_participants = len(sorted_participants)
    
    # محدود کردن به تعداد مشخص شده
    top_participants = sorted_participants[:max_players]
    
    # ساخت لیست نفرات برتر
    leaderboard_lines = []
    for i, (user_id, user_data) in enumerate(top_participants):
        # افزودن مدال برای سه نفر اول
        medal = ""
        if i == 0: medal = "🥇 "
        elif i == 1: medal = "🥈 "
        elif i == 2: medal = "🥉 "
        
        line = f"{medal}{i+1}. {user_data['full_name']}: {user_data['total_points']} امتیاز"
        leaderboard_lines.append(line)
    
    # متن لیست
    leaderboard_text = "\n".join(leaderboard_lines)
    
    # اطلاعات سایر کاربران
    remaining_count = total_participants - min(max_players, total_participants)
    remaining_text = f"\n+ {remaining_count} کاربر دیگر" if remaining_count > 0 else ""
    
    return leaderboard_text + remaining_text

@start_quiz_router.callback_query(F.data.startswith("quiz_start"))
@limit_user_requests(seconds=2)
async def start_quiz(callback: CallbackQuery) -> None:
    """
    Start a new quiz in response to the start button click.
    
    Args:
        callback: Callback query object from Telegram
    """
    try:
        # استخراج اطلاعات از callback data
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer(MESSAGES["invalid_format"], show_alert=True)
            return
       
        quiz_topic_id = parts[1]
        quiz_creator_id = parts[2]
        quiz_id = parts[3]
        
        # استخراج تنظیمات از callback data
        quiz_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]  # مقدار پیش‌فرض
        quiz_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]  # مقدار پیش‌فرض
        
        # اگر تعداد سوالات و زمان در callback وجود دارد، استفاده کن
        if len(parts) >= 6:
            try:
                quiz_question_count = int(parts[4])
                quiz_time_limit = int(parts[5])
                
                # بررسی معتبر بودن مقادیر
                if quiz_question_count not in config.QUIZ_COUNT_OF_QUESTIONS_LIST:
                    quiz_question_count = config.QUIZ_COUNT_OF_QUESTIONS_LIST[0]
                
                if quiz_time_limit not in config.QUIZ_TIME_LIMIT_LIST:
                    quiz_time_limit = config.QUIZ_TIME_LIMIT_LIST[0]
            except (ValueError, IndexError) as e:
                logger.error(f"Error extracting settings: {e}")
                # در صورت خطا از مقادیر پیش‌فرض استفاده می‌کنیم
        
        # بررسی دسترسی کاربر
        current_user_id = callback.from_user.id
        if str(current_user_id) != str(quiz_creator_id):
            await callback.answer(MESSAGES["creator_only"], show_alert=True)
            return
       
        # بررسی وجود کوییز
        if quiz_id not in active_quizzes:
            await callback.answer(MESSAGES["quiz_not_found"], show_alert=True)
            return
       
        # بررسی تعداد شرکت‌کنندگان
        participants = active_quizzes[quiz_id]["participants"]
        if len(participants) < 2:
            await callback.answer(MESSAGES["need_players"], show_alert=True)
            return
       
        # دریافت سوالات از دیتابیس
        get_questions = db.get_questions_by_topic(quiz_topic_id)
       
        if get_questions.get("status") == "error":
            await bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text=MESSAGES["error_general"],
                parse_mode=ParseMode.HTML
            )
            return
       
        # بررسی کافی بودن تعداد سوالات
        questions = get_questions.get("questions")
        if len(questions) < quiz_question_count:
            await bot.edit_message_text(
                inline_message_id=callback.inline_message_id,
                text=MESSAGES["not_enough_questions"],
                parse_mode=ParseMode.HTML
            )
            return
       
        # انتخاب تصادفی سوالات
        random.shuffle(questions)
        selected_questions = questions[:quiz_question_count]
        active_quizzes[quiz_id]["questions"] = selected_questions
        
        # ذخیره تنظیمات انتخاب شده در active_quizzes
        active_quizzes[quiz_id]["question_count"] = quiz_question_count
        active_quizzes[quiz_id]["time_limit"] = quiz_time_limit

        db.update_quiz_created(quiz_creator_id)
        db.update_topic_played(quiz_topic_id)
        # شروع فرآیند کوییز
        await asyncio.create_task(send_quiz_message(active_quizzes[quiz_id], callback))
    except Exception as e:
        logger.error(f"Error starting quiz: {e}")
        # سعی می‌کنیم خطا را به کاربر نشان ندهیم و صرفاً لاگ کنیم

@start_quiz_router.callback_query(F.data.startswith("quiz_answer:"))
@limit_user_requests(seconds=2)
async def process_answer(callback: CallbackQuery) -> None:
    """
    Process user's answer to a quiz question.
    
    Args:
        callback: Callback query object from Telegram
    """
    try:
        # Extract callback data
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(MESSAGES["invalid_data"], show_alert=True)
            return
            
        quiz_id = parts[1]
        question_id = parts[2]
        selected_option = int(parts[3])
        
        # Check if quiz exists
        if quiz_id not in active_quizzes:
            await callback.answer(MESSAGES["quiz_not_found_alert"], show_alert=True)
            return
            
        # Check quiz current state
        quiz_data = active_quizzes[quiz_id]
        if "current_question" not in quiz_data:
            await callback.answer(MESSAGES["quiz_not_active"], show_alert=True)
            return
            
        # Check if this is the current question
        if quiz_data["current_question"]["id"] != question_id:
            await callback.answer(MESSAGES["question_not_active"], show_alert=True)
            return
            
        # Check if user is a participant
        user_id = callback.from_user.id
        if user_id not in quiz_data["participants"]:
            await callback.answer(MESSAGES["not_a_participant"], show_alert=True)
            return
            
        # Check if already answered
        if user_id in quiz_data["current_question"]["answered_users"]:
            await callback.answer(MESSAGES["already_answered"], show_alert=True)
            return
            
        # Register user's answer
        quiz_data["current_question"]["answered_users"].append(user_id)
        
        # Check answer correctness
        correct_option = quiz_data["current_question"]["correct_option"]
        is_correct = selected_option == correct_option
        
        # Calculate remaining time and points
        now = datetime.now().timestamp()
        elapsed_time = now - quiz_data["current_question"]["start_time"]
        
        # Get custom time limit from quiz data or use default
        time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
        remaining_time = max(0, time_limit - int(elapsed_time))
        
        # Update user stats
        if is_correct:
            # Points = 1 for correct answer + remaining time
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
    """
    Execute a complete quiz from start to finish, showing questions, collecting answers, and displaying results.
    
    Args:
        quiz_data: Quiz information including questions and participants
        callback: Callback query object from Telegram for updating messages
    """
    try:
        # دریافت اطلاعات اولیه کوییز
        questions_list = quiz_data["questions"]
        quiz_id = list(active_quizzes.keys())[list(active_quizzes.values()).index(quiz_data)]
        topic_id = quiz_data["topic_id"]
        
        # استفاده از مقادیر سفارشی یا پیش‌فرض
        quiz_time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
        
        # اعلام شروع کوییز
        await update_quiz_message(
            callback=callback,
            text=MESSAGES["quiz_started"]
        )
        
        # مکث قبل از شروع سوالات
        await asyncio.sleep(3)
        
        # پردازش هر سوال به ترتیب
        for index, question in enumerate(questions_list):
            # اطلاعات سوال فعلی
            question_number = index + 1
            total_questions = len(questions_list)
            question_text = question["text"]
            options = question["options"]
            correct_option = question["correct_option"]
            question_id = f"{quiz_id}_{question_number}"
            
            # آماده‌سازی و نمایش سوال
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
            
            # انتظار برای زمان پاسخگویی (استفاده از زمان سفارشی)
            await asyncio.sleep(quiz_time_limit)
            
            # بررسی و ثبت کاربرانی که پاسخ نداده‌اند
            for user_id in quiz_data["participants"]:
                if user_id not in quiz_data["current_question"]["answered_users"]:
                    # ثبت پاسخ اشتباه برای کاربرانی که پاسخ نداده‌اند
                    quiz_data["participants"][user_id]["total_wrong"] += 1
            
            # اگر سوال آخر نیست، نمایش وضعیت میانی
            if question_number < total_questions:
                await show_intermediate_results(
                    callback=callback,
                    quiz_data=quiz_data,
                    pause_seconds=2  # مکث 2 ثانیه بین سوالات
                )
        
        # نمایش نتایج نهایی کوییز
        await show_final_results(
            callback=callback,
            quiz_data=quiz_data,
            quiz_id=quiz_id,
            topic_id=topic_id
        )
        
        # به‌روز‌رسانی آمار کاربران در پایگاه داده
        await update_users_statistics(quiz_data)
        
        # پاکسازی داده‌ها
        cleanup_quiz_data(quiz_data, quiz_id)
        
        logger.info(f"Quiz {quiz_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error sending quiz message: {e}")
        # تلاش برای اطلاع‌رسانی به کاربران با ویرایش پیام
        try:
            await update_quiz_message(
                callback=callback,
                text=MESSAGES["error_general"]
            )
        except:
            logger.error("Failed to send error message")


# توابع کمکی تفکیک‌شده
async def update_quiz_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    """
    Update quiz message with new text and keyboard.
    
    Args:
        callback: Callback query object
        text: New message text
        reply_markup: New keyboard (if needed)
    """
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
    """
    Display a quiz question to users.
    
    Args:
        callback: Callback query object
        quiz_data: Quiz information
        question_number: Current question number
        total_questions: Total number of questions
        question_text: Question text
        options: Question options
        correct_option: Correct option number
        question_id: Question identifier
    """
    # استفاده از زمان سفارشی یا پیش‌فرض
    time_limit = quiz_data.get("time_limit", config.QUIZ_TIME_LIMIT)
    
    # ساخت پیام سوال
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
    
    # ساخت کیبورد گزینه‌ها
    keyboard = get_options_keyboard(quiz_id=question_id.split('_')[0], question_id=question_id)
    
    # ذخیره اطلاعات سوال فعلی در کوییز
    quiz_data["current_question"] = {
        "id": question_id,
        "correct_option": correct_option,
        "start_time": datetime.now().timestamp(),
        "answered_users": []
    }
    
    # ویرایش پیام اصلی برای نمایش سوال فعلی
    await update_quiz_message(callback, question_message, keyboard)


async def show_intermediate_results(callback: CallbackQuery, quiz_data: Dict[str, Any], pause_seconds: int) -> None:
    """
    Display intermediate results between questions.
    
    Args:
        callback: Callback query object
        quiz_data: Quiz information
        pause_seconds: Pause duration between questions
    """
    # دریافت لیست 10 نفر برتر تا این لحظه
    top_players = format_top_players(quiz_data["participants"])
    
    # ویرایش پیام برای نمایش انتظار تا سوال بعدی و 10 نفر برتر
    waiting_message = MESSAGES["waiting_for_next"].format(
        seconds=pause_seconds,
        top_players=top_players
    )
    
    await update_quiz_message(callback, waiting_message)
    await asyncio.sleep(pause_seconds)


async def show_final_results(callback: CallbackQuery, quiz_data: Dict[str, Any], quiz_id: str, topic_id: str) -> None:
    """
    Display final quiz results.
    
    Args:
        callback: Callback query object
        quiz_data: Quiz information
        quiz_id: Quiz identifier
        topic_id: Topic identifier
    """
    # ایجاد متن جدول امتیازات
    leaderboard = format_leaderboard(quiz_data["participants"])
    final_message = MESSAGES["quiz_completed"].format(leaderboard=leaderboard)
    
    # ساخت کیبورد پایانی با دکمه‌های بازی مجدد و اسپانسر
    final_keyboard = get_final_keyboard(topic_id)
    
    # ویرایش پیام اصلی برای نمایش نتایج
    await update_quiz_message(callback, final_message, final_keyboard)


async def update_users_statistics(quiz_data: Dict[str, Any]) -> None:
    """
    Update user statistics in the database.
    
    Args:
        quiz_data: Quiz information containing user statistics
    """
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
    """
    Clean up quiz data after completion.
    
    Args:
        quiz_data: Quiz information
        quiz_id: Quiz identifier
    """
    # پاکسازی داده‌های موقت
    if "current_question" in quiz_data:
        del quiz_data["current_question"]
    
    # پاک کردن کوییز از دیکشنری active_quizzes
    if quiz_id in active_quizzes:
        del active_quizzes[quiz_id]
        logger.info(f"Quiz {quiz_id} removed from active quizzes")



