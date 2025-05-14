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
from .start_bot import main_menu_keyboard, welcome_message
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


pending_questions_router = Router(name="pending_questions")


class PendingQuestionStates(StatesGroup):
    viewing_questions = State()


SPONSOR_FOOTER = f" "


MESSAGES = {
    "no_pending_questions": "📭 هیچ سؤال در انتظار بررسی یافت نشد." + SPONSOR_FOOTER,
    "view_question": """
📋 سؤال در انتظار بررسی {current_idx}/{total}:

🔍 موضوع: {topic_name}

❓ سؤال: 
{question_text}

🔢 گزینه‌ها:
1. {option_1}
2. {option_2}
3. {option_3}
4. {option_4}

✅ گزینه صحیح: {correct_option}

👤 ایجاد شده توسط: {creator_info}
🕒 تاریخ ایجاد: {created_at}
🆔 شناسه سؤال: {question_id}
""" + SPONSOR_FOOTER,
    "approved": "✅ سؤال با موفقیت تأیید شد." + SPONSOR_FOOTER,
    "rejected": "❌ سؤال رد شده و حذف گردید." + SPONSOR_FOOTER,
    "error": "❗ خطایی رخ داد: {error}" + SPONSOR_FOOTER,
    "approving": "⏳ در حال تأیید سؤال..." + SPONSOR_FOOTER,
    "rejecting": "⏳ در حال رد کردن سؤال..." + SPONSOR_FOOTER,
    "error_question_not_found": "❌ خطا: سؤال یافت نشد." + SPONSOR_FOOTER,
    "error_question_not_approved": "❌ خطا: سؤال نمی‌تواند تأیید شود." + SPONSOR_FOOTER,
    "error_question_not_deleted": "❌ خطا: سؤال یافت نشد یا امکان حذف آن وجود ندارد." + SPONSOR_FOOTER,
    "invalid_index": "⚠️ شاخص سؤال نامعتبر است. بازگشت به سؤال اول." + SPONSOR_FOOTER,
    "processing": "⏳ در حال پردازش...",
    
    "previous": "◀️ قبلی",
    "next": "بعدی ▶️",
    "approve": "✅ تأیید",
    "reject": "❌ رد",
    "cancel": "❌ لغو",
    
    "welcome_back": "🔙 بازگشت به منوی اصلی"
}



def get_question_keyboard(current_idx: int, total_questions: int, question_id: str) -> InlineKeyboardMarkup:
 
    kb = InlineKeyboardBuilder()
    
    if total_questions > 1:
        if current_idx > 0:
            kb.button(text=MESSAGES["previous"], callback_data=f"pending_nav_prev_{current_idx}")
        
        if current_idx < total_questions - 1:
            kb.button(text=MESSAGES["next"], callback_data=f"pending_nav_next_{current_idx}")
    
    kb.button(text=MESSAGES["approve"], callback_data=f"pending_approve_{question_id}")
    kb.button(text=MESSAGES["reject"], callback_data=f"pending_reject_{question_id}")
    kb.button(text=MESSAGES["cancel"], callback_data="pending_cancel")
    
    if total_questions > 1 and current_idx > 0 and current_idx < total_questions - 1:
        kb.adjust(2, 2, 1)
    elif total_questions > 1:
        kb.adjust(1, 2, 1)
    else:
        kb.adjust(2, 1)
        
    return kb.as_markup()


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


@pending_questions_router.message(Command("pending_questions"), F.from_user.id == config.ADMIN_ID)
async def cmd_pending_questions(message: Message, state: FSMContext) -> None:

    await state.clear()
    
    try:
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        if not pending_questions:
            await message.answer(
                MESSAGES["no_pending_questions"],
                parse_mode=ParseMode.HTML
            )
            return
        
        await state.update_data(questions=pending_questions, current_idx=0)
        await state.set_state(PendingQuestionStates.viewing_questions)
        
        await display_question(message, pending_questions[0], 0, len(pending_questions), is_new_message=True)
        logger.info(f"Admin started reviewing {len(pending_questions)} pending questions")
    except Exception as e:
        logger.error(f"Error in pending_questions command: {e}")


@pending_questions_router.callback_query(F.data.startswith("pending_nav_prev_"))
async def nav_prev(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer()
    
    current_idx = int(callback.data.split("_")[3]) - 1
    await navigate_to_question(callback, state, current_idx)
    logger.info(f"Admin navigated to previous question (index: {current_idx})")

@pending_questions_router.callback_query(F.data.startswith("pending_nav_next_"))
async def nav_next(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer()
    
    current_idx = int(callback.data.split("_")[3]) + 1
    await navigate_to_question(callback, state, current_idx)
    logger.info(f"Admin navigated to next question (index: {current_idx})")

@pending_questions_router.callback_query(F.data == "pending_cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer()
    
    await state.clear()
    
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it may have been deleted already")
    
    await callback.message.answer(
        text=welcome_message.format(full_name=callback.from_user.full_name),
        reply_markup=main_menu_keyboard,
        parse_mode=ParseMode.HTML
    )
    logger.info(f"Admin cancelled pending questions review")


@pending_questions_router.callback_query(F.data.startswith("pending_approve_"))
async def approve_question(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer(MESSAGES["processing"])
    
    question_id = callback.data.split("_")[2]
    
    await safe_edit_message(
        callback.message,
        MESSAGES["approving"]
    )
    
    try:
        result = db.questions.update_one(
            {"question_id": question_id},
            {"$set": {"is_approved": True}}
        )
        
        if result.modified_count == 0:
            if not db.questions.find_one({"question_id": question_id}):
                await safe_edit_message(
                    callback.message,
                    MESSAGES["error_question_not_found"]
                )
                return
            else:
                await safe_edit_message(
                    callback.message,
                    MESSAGES["error_question_not_approved"]
                )
                return
        
        data = await state.get_data()
        current_idx = data.get("current_idx", 0)
        
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        await state.update_data(questions=pending_questions)
        
        await safe_edit_message(
            callback.message,
            MESSAGES["approved"]
        )
        logger.info(f"Question {question_id} approved successfully")
        
        if not pending_questions:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
        
        if current_idx >= len(pending_questions):
            current_idx = len(pending_questions) - 1
        
        await state.update_data(current_idx=current_idx)
        
        await display_question(callback.message, pending_questions[current_idx], current_idx, len(pending_questions))
    except Exception as e:
        logger.error(f"Error approving question: {e}")

@pending_questions_router.callback_query(F.data.startswith("pending_reject_"))
async def reject_question(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer(MESSAGES["processing"])
    
    question_id = callback.data.split("_")[2]
    
    await safe_edit_message(
        callback.message,
        MESSAGES["rejecting"]
    )
    
    try:
        result = db.questions.delete_one({"question_id": question_id})
        
        if result.deleted_count == 0:
            await safe_edit_message(
                callback.message,
                MESSAGES["error_question_not_deleted"]
            )
            return
        
        data = await state.get_data()
        current_idx = data.get("current_idx", 0)
        
        pending_questions = list(db.questions.find({"is_approved": False}))
        
        await state.update_data(questions=pending_questions)
        
        await safe_edit_message(
            callback.message,
            MESSAGES["rejected"]
        )
        logger.info(f"Question {question_id} rejected and deleted")
        
        if not pending_questions:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
        
        if current_idx >= len(pending_questions):
            current_idx = len(pending_questions) - 1
        
        await state.update_data(current_idx=current_idx)
        
        await display_question(callback.message, pending_questions[current_idx], current_idx, len(pending_questions))
    except Exception as e:
        logger.error(f"Error rejecting question: {e}")


async def navigate_to_question(callback: CallbackQuery, state: FSMContext, current_idx: int) -> None:

    data = await state.get_data()
    questions = data.get("questions", [])
    
    if current_idx < 0 or current_idx >= len(questions):
        logger.warning(f"Invalid question index: {current_idx}, max: {len(questions)-1}")
        await safe_edit_message(
            callback.message,
            MESSAGES["invalid_index"]
        )
        current_idx = 0
        if len(questions) == 0:
            await safe_edit_message(
                callback.message,
                MESSAGES["no_pending_questions"]
            )
            await state.clear()
            return
    
    await state.update_data(current_idx=current_idx)
    
    await display_question(callback.message, questions[current_idx], current_idx, len(questions))

async def display_question(message_obj: Message, question: Dict[str, Any], idx: int, total: int, is_new_message: bool = False) -> None:

    try:
        topic_info = db.topics.find_one({"topic_id": question["topic_id"]})
        topic_name = topic_info["name"] if topic_info else "Unknown"
        
        creator_id = question["created_by"]
        creator_info = f"User ID: {creator_id}"
        
        creator = db.users.find_one({"user_id": creator_id})
        if creator:
            username = creator.get("username", "")
            full_name = creator.get("full_name", "")
            
            if username and full_name:
                creator_info = f"{full_name} (@{username}, ID: {creator_id})"
            elif username:
                creator_info = f"@{username} (ID: {creator_id})"
            elif full_name:
                creator_info = f"{full_name} (ID: {creator_id})"
        
        question_text = MESSAGES["view_question"].format(
            current_idx=idx + 1,
            total=total,
            topic_name=topic_name,
            question_text=question["text"],
            option_1=question["options"][0],
            option_2=question["options"][1],
            option_3=question["options"][2],
            option_4=question["options"][3],
            correct_option=question["correct_option"] + 1,  # Convert from 0-based to 1-based
            creator_info=creator_info,
            created_at=question["created_at"],
            question_id=question["question_id"]
        )
        
        keyboard = get_question_keyboard(idx, total, question["question_id"])
        
        if is_new_message:
            await message_obj.answer(
                question_text, 
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            await safe_edit_message(
                message_obj,
                question_text,
                keyboard
            )
    except Exception as e:
        logger.error(f"Error displaying question: {e}")
