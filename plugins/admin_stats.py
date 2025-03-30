from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import Command
import logging
from datetime import datetime
from html import escape

from bot import db
import config

logger = logging.getLogger(__name__)

# Admin Stats router
admin_stats_router = Router(name="admin_stats")

# Sponsor footer for consistent messaging
SPONSOR_FOOTER = f" "

# Constant messages
MESSAGES = {
    # Basic messages
    "only_admin": "🔒 این دستور فقط برای مدیران ربات در دسترس است." + SPONSOR_FOOTER,
    "statistics_title": "📊 <b>آمار ربات</b> 📊\n\n",
    "error": "❌ خطایی هنگام دریافت آمار رخ داد: {error}" + SPONSOR_FOOTER,
    "processing_error": "❌ خطایی هنگام پردازش آمار رخ داد. لطفاً بعداً دوباره امتحان کنید." + SPONSOR_FOOTER,
    
    # User statistics section
    "user_stats": """👥 <b>آمار کاربران:</b>
• کل کاربران: <b>{total}</b>
• کاربران فعال: <b>{started}</b>
• کاربران جدید (۲۴ ساعت گذشته): <b>{new_24h}</b>
""",
    
    # Topic statistics section
    "topic_stats": """🔠 <b>آمار موضوعات:</b>
• کل موضوعات: <b>{total}</b>
• موضوعات فعال: <b>{active}</b>
""",
    
    # Question statistics section
    "question_stats": """❓ <b>آمار سوالات:</b>
• کل سوالات: <b>{total}</b> (شامل تأیید نشده‌ها)
• سوالات تأیید شده: <b>{approved}</b>
""",
    
    # Invalid questions section
    "invalid_questions_title": "⚠️ <b>سوالات با موضوعات نامعتبر:</b>",
    "invalid_question_row": "• سوال {question_id} با موضوع نامعتبر {topic_id}",
    "no_invalid_questions": "• هیچ سوالی با موضوع نامعتبر یافت نشد",
    "invalid_questions_count": "• <b>{count}</b> سوال با موضوع نامعتبر یافت شد",
    
    # Popular topics section
    "popular_topics_title": "🔝 <b>موضوعات فعال:</b>",
    "popular_topic_row": "• {name}: <b>{count}</b> بار بازی شده",
    "no_popular_topics": "• هنوز هیچ موضوعی بازی نشده است",
    
    # Top question submitters section
    "top_submitters_title": "👑 <b>برترین ارسال‌کنندگان سوال:</b>",
    "top_submitter_row": "• {name} (شناسه: {user_id}): <b>{count}</b> سوال",
    "no_submitters": "• هنوز هیچ کاربری سوالی ارسال نکرده است",
    
    # Top quiz creators section
    "top_creators_title": "🎮 <b>برترین سازندگان آزمون:</b>",
    "top_creator_row": "• {name} (شناسه: {user_id}): <b>{count}</b> آزمون",
    "no_creators": "• هنوز هیچ کاربری آزمونی نساخته است",
    
    # Questions per topic section
    "questions_per_topic_title": "📚 <b>سوالات به تفکیک موضوع:</b>",
    "question_per_topic_row": "• {name}: <b>{count}</b> سوال",
    
    # User display formats
    "unknown_user": "کاربر با شناسه {user_id}"
}


async def format_statistics(stats):
    """
    Format the statistics data into a readable text
    
    Args:
        stats (dict): Statistics data structure from get_bot_statistics function
        
    Returns:
        str: Formatted statistics text for display
    """
    text = MESSAGES["statistics_title"]
    
    # User stats
    text += MESSAGES["user_stats"].format(
        total=stats["users"]["total"],
        started=stats["users"]["started"],
        new_24h=stats["users"]["new_24h"]  # Use today key as new_24h
    )
    
    text += "\n"
    
    # Topic stats
    text += MESSAGES["topic_stats"].format(
        total=stats["topics"]["total"],
        active=stats["topics"]["active"]
    )
    
    text += "\n"
    
    # Question stats
    text += MESSAGES["question_stats"].format(
        total=stats["questions"]["total"],
        approved=stats["questions"]["approved"]
    )
    
    text += "\n"
    
    # Popular topics
    text += MESSAGES["popular_topics_title"] + "\n"
    if "popular" in stats["topics"] and stats["topics"]["popular"]:
        # Display maximum 3 topics
        top_topics = stats["topics"]["popular"][:3]
        for topic in top_topics:
            text += MESSAGES["popular_topic_row"].format(
                name=escape(topic["topic_name"]),
                count=topic["play_count"]
            ) + "\n"
    else:
        text += MESSAGES["no_popular_topics"] + "\n"
    text += "\n"
    
    # Top submitters
    text += MESSAGES["top_submitters_title"] + "\n"
    if "top_submitters" in stats["questions"] and stats["questions"]["top_submitters"]:
        for submitter in stats["questions"]["top_submitters"]:
            # Get user display name
            user_name = get_user_display_name(submitter)
                
            text += MESSAGES["top_submitter_row"].format(
                name=user_name,
                user_id=submitter["user_id"],
                count=submitter["question_count"]
            ) + "\n"
    else:
        text += MESSAGES["no_submitters"] + "\n"
    text += "\n"
    
    # Top quiz creators - if available
    text += MESSAGES["top_creators_title"] + "\n"
    if "top_creators" in stats["questions"] and stats["questions"]["top_creators"]:
        for creator in stats["questions"]["top_creators"]:
            # Get user display name
            user_name = get_user_display_name(creator)
                
            text += MESSAGES["top_creator_row"].format(
                name=user_name,
                user_id=creator["user_id"],
                count=creator.get("quiz_count", 0)
            ) + "\n"
    else:
        text += MESSAGES["no_creators"] + "\n"
    text += "\n"
    
    # Questions per topic
    if "per_topic" in stats["questions"] and stats["questions"]["per_topic"]:
        text += MESSAGES["questions_per_topic_title"] + "\n"
        # Sort by question count descending
        sorted_topics = sorted(stats["questions"]["per_topic"], 
                               key=lambda x: x["question_count"], 
                               reverse=True)
        
        for topic in sorted_topics:
            text += MESSAGES["question_per_topic_row"].format(
                name=escape(topic["topic_name"]),
                count=topic["question_count"]
            ) + "\n"
    
    # Invalid topics questions
    if "invalid_topics" in stats["questions"] and stats["questions"]["invalid_topics"]:
        text += "\n" + MESSAGES["invalid_questions_title"] + "\n"
        invalid_count = len(stats["questions"]["invalid_topics"])
        text += MESSAGES["invalid_questions_count"].format(count=invalid_count) + "\n"
    
    # Add sponsor footer
    text += SPONSOR_FOOTER
    
    return text


def get_user_display_name(user_data):
    """
    Get a proper display name for a user
    
    Args:
        user_data (dict): User data dictionary containing user information
        
    Returns:
        str: Formatted and escaped display name
    """
    user_name = user_data.get("full_name", "")
    if not user_name or user_name.strip() == "":
        user_name = MESSAGES["unknown_user"].format(user_id=user_data["user_id"])
    else:
        user_name = escape(user_name)
    
    return user_name


def sanitize_text_data(data_dict):
    """
    Sanitize all text values in a complex data structure
    
    Args:
        data_dict (dict): Statistics data dictionary
    """
    # Sanitize topic names in popular_topics
    if "topics" in data_dict and "popular" in data_dict["topics"]:
        for topic in data_dict["topics"]["popular"]:
            if "topic_name" in topic and topic["topic_name"]:
                topic["topic_name"] = escape(str(topic["topic_name"]))
    
    # Sanitize user names in top_submitters
    if "questions" in data_dict and "top_submitters" in data_dict["questions"]:
        for submitter in data_dict["questions"]["top_submitters"]:
            if "full_name" in submitter and submitter["full_name"]:
                submitter["full_name"] = escape(str(submitter["full_name"]))
    
    # Sanitize user names in top_creators (if exists)
    if "questions" in data_dict and "top_creators" in data_dict["questions"]:
        for creator in data_dict["questions"]["top_creators"]:
            if "full_name" in creator and creator["full_name"]:
                creator["full_name"] = escape(str(creator["full_name"]))
    
    # Sanitize topic names in per_topic
    if "questions" in data_dict and "per_topic" in data_dict["questions"]:
        for topic in data_dict["questions"]["per_topic"]:
            if "topic_name" in topic and topic["topic_name"]:
                topic["topic_name"] = escape(str(topic["topic_name"]))


@admin_stats_router.message(Command("stats"), F.from_user.id == config.ADMIN_ID)
async def show_admin_statistics(message: Message) -> None:
    """
    Handle the /stats command - shows comprehensive bot statistics
    
    Args:
        message (Message): Message received from the admin user
    """
    user_id = message.from_user.id
    
    # Get bot statistics
    try:
        stats_result = db.get_bot_statistics()
        
        if stats_result["status"] == "error":
            await message.answer(
                text=MESSAGES["error"].format(error=escape(stats_result["message"])),
                parse_mode=ParseMode.HTML
            )
            logger.error(f"Error retrieving statistics: {stats_result['message']}")
            return
        
        # Sanitize text data to prevent HTML injection
        sanitize_text_data(stats_result["statistics"])
        
        # Format statistics
        stats_text = await format_statistics(stats_result["statistics"])
        
        # Send statistics
        await message.answer(
            text=stats_text,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Statistics displayed for admin {user_id}")
        
    except Exception as e:
        # Send a user-friendly error message, log the actual error
        await message.answer(
            text=MESSAGES["processing_error"],
            parse_mode=ParseMode.HTML
        )
        logger.error(f"Error processing statistics: {e}") 