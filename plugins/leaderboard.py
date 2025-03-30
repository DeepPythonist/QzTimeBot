from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from bot import db
from .start_bot import main_menu_keyboard
from utils import limit_user_requests
import config

logger = logging.getLogger(__name__)

# Leaderboard router
leaderboard_router = Router(name="leaderboard")

# Sponsor footer for consistent messaging
SPONSOR_FOOTER = f" "

# Constant messages
MESSAGES = {
    "global_leaderboard_title": "🌎 <b>۲۰ قهرمان برتر کوئیز</b> 🌎\n\n",
    "user_stats_row": "{position}. {full_name}: {score} امتیاز (✓{correct} ✗{wrong} 📊{total})\n",
    "empty_leaderboard": "❗ هنوز هیچ کاربری در کوئیزها شرکت نکرده است!" + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داد: {error}" + SPONSOR_FOOTER,
    "back": "🏠 بازگشت به منوی اصلی",
    "personal_stats_title": "📊 <b>آمار کوئیز شما</b> 📊\n\n",
    "personal_stats": """
📝 تعداد کل کوئیزها: <b>{total_quiz}</b>
✅ پاسخ‌های صحیح: <b>{total_correct}</b>
❌ پاسخ‌های اشتباه: <b>{total_wrong}</b>
💯 نرخ دقت: <b>{accuracy}%</b>
🏆 امتیاز کل: <b>{total_points}</b>
🌟 امتیاز نهایی: <b>{score}</b>

📝 <b>مشارکت‌های شما:</b>
🧩 کوئیزهای ایجاد شده: <b>{quiz_created}</b>
❓ سؤالات ارسال شده: <b>{questions_submitted}</b>

<i>رتبه شما در میان تمام بازیکنان: <b>{rank}</b></i>
""" + SPONSOR_FOOTER,
    "no_stats": "⚠️ شما هنوز در هیچ کوئیزی شرکت نکرده‌اید! برای مشاهده آمار خود، در چند کوئیز شرکت کنید." + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    "stats_error": "❌ آمار شما یافت نشد" + SPONSOR_FOOTER
}

def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    Create a keyboard with a back button to main menu
    
    Returns:
        InlineKeyboardMarkup: Keyboard with back button
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["back"], callback_data="leaderboard_back_to_menu")
    return kb.as_markup()


def calculate_user_score(user_stats: Dict[str, Any]) -> float:
    """
    Calculate a user's total score based on their stats.
    
    Formula weights:
    - 60% for total_points
    - 30% for correct_ratio (correct answers / total questions)
    - 10% for total_quiz (participation)
    
    Args:
        user_stats: Dictionary containing user statistics
        
    Returns:
        float: Calculated score
    """
    total_quiz = user_stats.get("total_quiz", 0)
    total_correct = user_stats.get("total_correct", 0)
    total_wrong = user_stats.get("total_wrong", 0)
    total_points = user_stats.get("total_points", 0)
    
    # Return 0 if user hasn't participated in any quizzes
    if total_quiz == 0:
        return 0
    
    # Calculate correct answer ratio
    total_questions = total_correct + total_wrong
    correct_ratio = total_correct / total_questions if total_questions > 0 else 0
    
    # Final formula with different weights
    score = (
        (0.6 * total_points) +  # 60% total points
        (0.3 * 100 * correct_ratio) +  # 30% correct ratio
        (0.1 * total_quiz * 5)  # 10% participation (5 points per quiz)
    )
    
    return round(score, 1)


def calculate_user_rank(user_id: Union[str, int]) -> int:
    """
    Calculate a user's rank among all users
    
    Args:
        user_id: The user ID to calculate rank for
        
    Returns:
        int: User's rank (position) or 0 if user has no stats
    """
    try:
        # Get all users
        all_users = db.get_all_users()
        
        # Calculate score for each user
        users_with_scores = []
        for user in all_users:
            if "stats" in user:
                score = calculate_user_score(user["stats"])
                if score > 0:  # Only include users with score > 0
                    users_with_scores.append({
                        "user_id": user["user_id"],
                        "score": score
                    })
        
        # Sort users by score in descending order
        sorted_users = sorted(users_with_scores, key=lambda x: x["score"], reverse=True)
        
        # Find user's rank
        for i, user in enumerate(sorted_users, 1):
            if str(user["user_id"]) == str(user_id):
                return i
                
        # If user not in list (score is 0)
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating user rank: {e}")
        return 0


def get_top_users(limit: int = 20) -> Dict[str, Any]:
    """
    Get the top users based on calculated scores.
    
    Args:
        limit: Number of top users to return
        
    Returns:
        dict: Status and list of top users with their scores
    """
    try:
        # Get all users
        all_users = db.get_all_users()
        
        # Calculate score for each user
        users_with_scores = []
        for user in all_users:
            if "stats" in user:
                score = calculate_user_score(user["stats"])
                # Exclude users with score 0
                if score > 0:
                    users_with_scores.append({
                        "user_id": user["user_id"],
                        "full_name": user.get("full_name", "User"),
                        "score": score,
                        "stats": user["stats"]
                    })
        
        # Sort users by score in descending order
        sorted_users = sorted(users_with_scores, key=lambda x: x["score"], reverse=True)
        
        # Limit to requested number
        top_users = sorted_users[:limit]
        
        return {"status": "success", "users": top_users}
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        return {"status": "error", "message": str(e)}


# Safe message editing helper
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


@leaderboard_router.message(F.text == config.MAIN_MENU_LEADERBOARD_BUTTON)
@limit_user_requests(seconds=5)
async def show_personal_stats(message: Message) -> None:
    """
    Handle the Leaderboard button from the main menu - shows personal stats
    
    Args:
        message: User's message with the Leaderboard command
    """
    try:
        db.create_user(user_id=message.from_user.id, 
                       username=message.from_user.username if message.from_user.username else None,
                       full_name=message.from_user.full_name if message.from_user.full_name else "",
                       has_start=True)
        user_id = message.from_user.id
        
        # Get user information
        user_data = db.get_user_by_id(user_id)
        
        if user_data["status"] == "error" or "stats" not in user_data["user"]:
            await message.answer(
                text=MESSAGES["stats_error"],
                reply_markup=get_back_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return
            
        user_stats = user_data["user"]["stats"]
        
        # Check if user has participated in any quizzes
        if user_stats.get("total_quiz", 0) == 0:
            await message.answer(
                text=MESSAGES["no_stats"],
                reply_markup=get_back_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return
            
        # Calculate score and rank
        score = calculate_user_score(user_stats)
        rank = calculate_user_rank(user_id)
        
        # Calculate accuracy
        total_questions = user_stats.get("total_correct", 0) + user_stats.get("total_wrong", 0)
        accuracy = round((user_stats.get("total_correct", 0) / total_questions) * 100, 1) if total_questions > 0 else 0
        
        # Get questions submitted count
        questions_submitted_result = db.get_user_submitted_questions_count(str(user_id))
        questions_submitted = questions_submitted_result["count"] if questions_submitted_result["status"] == "success" else 0
        
        # Create personal stats text
        stats_text = MESSAGES["personal_stats_title"]
        stats_text += MESSAGES["personal_stats"].format(
            total_quiz=user_stats.get("total_quiz", 0),
            total_correct=user_stats.get("total_correct", 0),
            total_wrong=user_stats.get("total_wrong", 0),
            accuracy=accuracy,
            total_points=user_stats.get("total_points", 0),
            score=score,
            rank=f"{rank}" if rank > 0 else "N/A",
            quiz_created=user_stats.get("quiz_created", 0),
            questions_submitted=questions_submitted
        )
        
        # Send personal stats
        await message.answer(
            text=stats_text,
            reply_markup=get_back_keyboard(),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {user_id} viewed personal stats")
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error displaying personal stats: {e}")


@leaderboard_router.message(F.text == config.MAIN_MENU_GLOBAL_LEADERBOARD_BUTTON)
@limit_user_requests(seconds=10)
async def show_global_leaderboard(message: Message) -> None:
    """
    Handle the Global Leaderboard button from the main menu - shows top 20 users
    
    Args:
        message: User's message with the Global Leaderboard command
    """
    try:
        db.create_user(user_id=message.from_user.id, 
                       username=message.from_user.username if message.from_user.username else None,
                       full_name=message.from_user.full_name if message.from_user.full_name else "",
                       has_start=True)
        result = get_top_users(limit=20)
        
        if result["status"] == "error":
            # Just log error, don't send to user
            logger.error(f"Error getting top users: {result['message']}")
            return
            
        users = result["users"]
        
        if not users:
            await message.answer(
                text=MESSAGES["empty_leaderboard"], 
                reply_markup=get_back_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return
            
        # Create global leaderboard text
        leaderboard_text = MESSAGES["global_leaderboard_title"]
        
        for i, user in enumerate(users, 1):
            # Add user info to text
            stats = user["stats"]
            leaderboard_text += MESSAGES["user_stats_row"].format(
                position=i,
                full_name=user["full_name"],
                score=user["score"],
                correct=stats["total_correct"],
                wrong=stats["total_wrong"],
                total=stats["total_quiz"]
            )
            
            # Add newline between users
            if i < len(users):
                leaderboard_text += "\n"
        
        # Add sponsor footer
        leaderboard_text += SPONSOR_FOOTER
        
        # Send leaderboard message with back keyboard
        await message.answer(
            text=leaderboard_text,
            reply_markup=get_back_keyboard(),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {message.from_user.id} viewed global leaderboard")
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error displaying global leaderboard: {e}")


@leaderboard_router.callback_query(F.data == "leaderboard_back_to_menu")
@limit_user_requests(seconds=1)
async def back_to_menu(callback: CallbackQuery) -> None:
    """
    Handle back to main menu button
    
    Args:
        callback: Callback query from back button
    """
    try:
        # Delete previous message
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it might be too old")
        
    # Send main menu
    try:
        await callback.message.answer(
            text=MESSAGES["welcome_back"].format(full_name=callback.from_user.full_name),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} returned to main menu")
    except Exception as e:
        # Just log the error, don't send anything to user
        logger.error(f"Error returning to main menu: {e}")
