from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

import config
from bot import db, bot
import logging
from typing import Optional, Dict, Any, List, Union
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)

delete_question_router = Router(name="delete_question")

class DeleteQuestionStates(StatesGroup):
    selecting_topic = State()
    viewing_questions = State()

SPONSOR_FOOTER = f" "

MESSAGES = {
    "select_topic": "🔍 لطفاً موضوع مورد نظر برای مشاهده سوالات آن را انتخاب کنید:" + SPONSOR_FOOTER,
    "no_topics": "📭 هیچ موضوعی یافت نشد. لطفاً ابتدا با استفاده از دستور /add_topic موضوع اضافه کنید." + SPONSOR_FOOTER,
    "no_questions": "📝 هیچ سوالی برای این موضوع یافت نشد." + SPONSOR_FOOTER,
    "view_question": """
📊 سوال {current_idx}/{total}:

🔖 موضوع: {topic_name}

❓ سوال: 
{question_text}

🔢 گزینه‌ها:
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

✅ گزینه صحیح: {correct_option}

👤 ایجاد شده توسط: {creator_info}
🕒 تاریخ ایجاد: {created_at}
🆔 شناسه سوال: {question_id}
⚡ تأیید شده: {is_approved}
""" + SPONSOR_FOOTER,
    "confirm_delete": "⚠️ آیا از حذف این سوال اطمینان دارید؟" + SPONSOR_FOOTER,
    "deleted": "✅ سوال با موفقیت حذف شد." + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داده است: {error}" + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    
    "btn_prev": "◀️ قبلی",
    "btn_next": "بعدی ▶️",
    "btn_delete": "🗑️ حذف این سوال",
    "btn_back_to_topics": "🔙 بازگشت به موضوعات",
    "btn_cancel": "❌ لغو",
    "btn_confirm_delete": "✅ تأیید حذف",
}


async def safe_edit_message(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:

    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("Message not modified, content is the same")
            return True
        else:
            logger.error(f"Error editing message: {e}")
            return False
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False

def get_topics_keyboard() -> Optional[InlineKeyboardMarkup]:

    topics = db.get_all_topics()
    if not topics:
        return None
        
    kb = InlineKeyboardBuilder()
    for topic in topics:
        if topic.get("is_active", True):  # Only show active topics
            kb.button(text=topic["name"], callback_data=f"delete_question_topic_{topic['topic_id']}")
    
    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_question_cancel")
    kb.adjust(2)
    return kb.as_markup()

def get_question_navigation_keyboard(current_idx: int, total_questions: int, question_id: str) -> InlineKeyboardMarkup:
  
    kb = InlineKeyboardBuilder()
    
    if total_questions > 1:
        if current_idx > 0:
            kb.button(text=MESSAGES["btn_prev"], callback_data=f"delete_question_nav_prev_{current_idx}")
        
        if current_idx < total_questions - 1:
            kb.button(text=MESSAGES["btn_next"], callback_data=f"delete_question_nav_next_{current_idx}")
    
    kb.button(text=MESSAGES["btn_delete"], callback_data=f"delete_question_confirm_{question_id}")
    
    kb.button(text=MESSAGES["btn_back_to_topics"], callback_data="delete_question_back_to_topics")
    kb.button(text=MESSAGES["btn_cancel"], callback_data="delete_question_cancel")
    
    if total_questions > 1:
        if current_idx > 0 and current_idx < total_questions - 1:
            kb.adjust(2, 1, 1, 1)
        else:
            kb.adjust(1, 1, 1, 1)
    else:
        kb.adjust(1, 1, 1)
        
    return kb.as_markup()

def get_confirmation_keyboard(question_id: str) -> InlineKeyboardMarkup:
 
    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_confirm_delete"], callback_data=f"delete_question_delete_{question_id}")
    kb.button(text=MESSAGES["btn_cancel"], callback_data=f"delete_question_view_{question_id}")
    kb.adjust(2)
    return kb.as_markup()

@delete_question_router.message(Command("delete_question"), F.from_user.id == config.ADMIN_ID)
async def cmd_delete_question(message: Message, state: FSMContext) -> None:

    try:
        await state.clear()
        
        keyboard = get_topics_keyboard()
        if not keyboard:
            await message.answer(
                MESSAGES["no_topics"],
                parse_mode=ParseMode.HTML
            )
            return
            
        await state.set_state(DeleteQuestionStates.selecting_topic)
        await message.answer(
            MESSAGES["select_topic"],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} initiated question deletion")
    except Exception as e:
        logger.error(f"Error in delete_question command: {e}")

@delete_question_router.callback_query(F.data == "delete_question_cancel")
async def cancel_delete_question(callback: CallbackQuery, state: FSMContext) -> None:

    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it might be too old")
        
    try:
        await callback.message.answer(
            text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} cancelled question deletion")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")

@delete_question_router.callback_query(F.data == "delete_question_back_to_topics")
async def back_to_topics(callback: CallbackQuery, state: FSMContext) -> None:


    try:
        keyboard = get_topics_keyboard()
        if not keyboard:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_topics"]
            )
            await state.clear()
            return
            
        await state.set_state(DeleteQuestionStates.selecting_topic)
        await safe_edit_message(
            callback.message,
            MESSAGES["select_topic"],
            keyboard
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} went back to topics list")
    except Exception as e:
        logger.error(f"Error going back to topics: {e}")
        await callback.answer()

@delete_question_router.callback_query(F.data.startswith("delete_question_topic_"))
async def topic_selected(callback: CallbackQuery, state: FSMContext) -> None:

    topic_id = callback.data.split("_")[3]
    
    try:
        topic_response = db.get_topic_by_id(topic_id)
        if topic_response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["error"].format(error=topic_response["message"])
            )
            await state.clear()
            return
            
        topic = topic_response["topic"]
        topic_name = topic["name"]
        

        questions_response = db.get_questions_by_topic(topic_id)
        if questions_response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await callback.answer()
            return
            
        questions = questions_response["questions"]
        
        await state.update_data(
            topic_id=topic_id,
            topic_name=topic_name,
            current_idx=0,
            questions=questions
        )
        
        await state.set_state(DeleteQuestionStates.viewing_questions)
        await show_question(callback, state, 0)
        logger.info(f"Admin {callback.from_user.id} selected topic {topic_id} ({topic_name}) with {len(questions)} questions")
    except Exception as e:
        logger.error(f"Error selecting topic: {e}")
        await callback.answer()

@delete_question_router.callback_query(F.data.startswith("delete_question_nav_prev_"))
async def navigate_to_prev(callback: CallbackQuery, state: FSMContext) -> None:

    current_idx = int(callback.data.split("_")[4])
    await show_question(callback, state, current_idx - 1)
    logger.info(f"Admin {callback.from_user.id} navigated to previous question (index {current_idx-1})")

@delete_question_router.callback_query(F.data.startswith("delete_question_nav_next_"))
async def navigate_to_next(callback: CallbackQuery, state: FSMContext) -> None:

    current_idx = int(callback.data.split("_")[4])
    await show_question(callback, state, current_idx + 1)
    logger.info(f"Admin {callback.from_user.id} navigated to next question (index {current_idx+1})")

@delete_question_router.callback_query(F.data.startswith("delete_question_view_"))
async def view_specific_question(callback: CallbackQuery, state: FSMContext) -> None:

    try:
        data = await state.get_data()
        questions = data.get("questions", [])
        current_idx = data.get("current_idx", 0)
        
        await state.set_state(DeleteQuestionStates.viewing_questions)
        
        await show_question(callback, state, current_idx)
        logger.info(f"Admin {callback.from_user.id} cancelled question deletion and returned to view")
    except Exception as e:
        logger.error(f"Error viewing specific question: {e}")
        await callback.answer()


@delete_question_router.callback_query(F.data.startswith("delete_question_confirm_"))
async def confirm_question_deletion(callback: CallbackQuery, state: FSMContext) -> None:
 
    question_id = callback.data.split("_")[3]
    
    try:
        await safe_edit_message(
            callback.message,
            f"{callback.message.text}\n\n{MESSAGES['confirm_delete']}",
            get_confirmation_keyboard(question_id)
        )
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} requested confirmation for deleting question {question_id}")
    except Exception as e:
        logger.error(f"Error showing delete confirmation: {e}")
        await callback.answer()

@delete_question_router.callback_query(F.data.startswith("delete_question_delete_"))
async def delete_question(callback: CallbackQuery, state: FSMContext) -> None:


    question_id = callback.data.split("_")[3]
    
    try:
        response = db.reject_question(question_id)  
        
        if response["status"] == "error":
            logger.error(f"Error deleting question {question_id}: {response['message']}")
            await safe_edit_message(
                callback.message,
                f"{callback.message.text}\n\nError: {response['message']}"
            )
            await callback.answer()
            return
        
        logger.info(f"Admin {callback.from_user.id} deleted question {question_id}")
        
        data = await state.get_data()
        questions = data.get("questions", [])
        current_idx = data.get("current_idx", 0)
        topic_id = data.get("topic_id")
        
        updated_questions_response = db.get_questions_by_topic(topic_id)
        
        if updated_questions_response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await state.clear()
            await callback.answer()
            return
            
        updated_questions = updated_questions_response["questions"]
        
        await state.update_data(questions=updated_questions)
        
        if current_idx >= len(updated_questions):
            current_idx = max(0, len(updated_questions) - 1)
            await state.update_data(current_idx=current_idx)
        
        await callback.answer(MESSAGES["deleted"])
        
        await show_question(callback, state, current_idx)
    except Exception as e:
        logger.error(f"Error deleting question: {e}")
        await callback.answer()

async def show_question(callback: CallbackQuery, state: FSMContext, idx: int) -> None:

    try:
        data = await state.get_data()
        questions = data.get("questions", [])
        topic_name = data.get("topic_name", "Unknown")
        
        if not questions or idx < 0 or idx >= len(questions):
            await safe_edit_message(
                callback.message,
                MESSAGES["no_questions"]
            )
            await state.clear()
            return
        
        await state.update_data(current_idx=idx)
        
        question = questions[idx]
        question_id = question["question_id"]
        creator_id = question["created_by"]
        
        creator_info = f"User ID {creator_id}"
        try:
            creator_data = db.get_user_by_id(creator_id)
            if creator_data["status"] == "success":
                creator = creator_data["user"]
                username = creator.get("username")
                full_name = creator.get("full_name")
                
                if username and full_name:
                    creator_info = f"{full_name} (@{username}, ID: {creator_id})"
                elif username:
                    creator_info = f"@{username} (ID: {creator_id})"
                elif full_name:
                    creator_info = f"{full_name} (ID: {creator_id})"
        except Exception as e:
            logger.error(f"Error getting creator info: {e}")
        
        question_text = MESSAGES["view_question"].format(
            current_idx=idx + 1,
            total=len(questions),
            topic_name=topic_name,
            question_text=question["text"],
            option_1=question["options"][0],
            option_2=question["options"][1],
            option_3=question["options"][2],
            option_4=question["options"][3],
            correct_option=question["correct_option"] + 1,
            creator_info=creator_info,
            created_at=question["created_at"],
            question_id=question_id,
            is_approved=question["is_approved"]
        )
        
        keyboard = get_question_navigation_keyboard(idx, len(questions), question_id)
        
        await safe_edit_message(
            callback.message,
            question_text,
            keyboard
        )
    except Exception as e:
        logger.error(f"Error showing question: {e}")
