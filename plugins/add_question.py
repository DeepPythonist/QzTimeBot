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
from typing import Optional, Dict, Any, List, Union, Tuple
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)


add_question_router = Router(name="add_question")


class AddQuestionStates(StatesGroup):
    selecting_topic = State()
    entering_question = State()
    entering_option_1 = State()
    entering_option_2 = State()
    entering_option_3 = State()
    entering_option_4 = State()
    selecting_correct_option = State()


SPONSOR_FOOTER = f" "


MESSAGES = {
    "select_topic": "🔍 لطفاً موضوع سوال خود را انتخاب کنید:" + SPONSOR_FOOTER,
    "no_topics": "📭 هیچ موضوعی یافت نشد. لطفاً ابتدا با استفاده از دستور /add_topic موضوع اضافه کنید." + SPONSOR_FOOTER,
    "enter_question": "❓ لطفاً متن سوال خود را وارد کنید:" + SPONSOR_FOOTER,
    "question_too_short": f"⚠️ سوال خیلی کوتاه است. طول آن باید حداقل {config.QUESTION_MIN_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "question_too_long": f"⚠️ سوال خیلی طولانی است. طول آن باید حداکثر {config.QUESTION_MAX_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "enter_option": "🔢 لطفاً گزینه #{} سوال خود را وارد کنید:" + SPONSOR_FOOTER,
    "option_too_short": f"⚠️ گزینه خیلی کوتاه است. طول آن باید حداقل {config.OPTION_MIN_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "option_too_long": f"⚠️ گزینه خیلی طولانی است. طول آن باید حداکثر {config.OPTION_MAX_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "select_correct_option": "✅ لطفاً گزینه صحیح را انتخاب کنید:" + SPONSOR_FOOTER,
    "question_submitted": "📤 سوال شما برای بررسی ارسال شد. با تشکر!" + SPONSOR_FOOTER,
    "question_added": "✅ سوال با موفقیت اضافه شد." + SPONSOR_FOOTER,
    "cancel_prompt": "🚫 عملیات لغو شد. آیا می‌خواهید به منوی اصلی بازگردید؟" + SPONSOR_FOOTER,
    "only_text": "⚠️ لطفاً فقط پیام متنی ارسال کنید." + SPONSOR_FOOTER,
    "error_general": "❌ خطایی رخ داده است. لطفاً بعداً دوباره امتحان کنید." + SPONSOR_FOOTER,
    "error_question_not_found": "❌ این سوال دیگر در دسترس نیست. ممکن است قبلاً پردازش شده باشد." + SPONSOR_FOOTER,
    "error_db_operation": "❌ در حال حاضر امکان پردازش این درخواست وجود ندارد. لطفاً بعداً دوباره امتحان کنید." + SPONSOR_FOOTER,
    "admin_new_question": """
📩 سوال جدید توسط کاربر {user_name} (شناسه: {user_id}):

🔖 موضوع: {topic_name}

❓ سوال: 
{question_text}

🔢 گزینه‌ها:
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

✅ گزینه صحیح: {correct_option}
""" + SPONSOR_FOOTER,
    "question_approved": """
✅ سوال شما توسط مدیر تأیید و به آزمون اضافه شد!

🔖 موضوع: {topic_name}

❓ سوال: 
{question_text}

🔢 گزینه‌ها:
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

✅ گزینه صحیح: {correct_option}
""" + SPONSOR_FOOTER,
    "question_rejected": """
❌ سوال شما توسط مدیر رد شد.

🔖 موضوع: {topic_name}

❓ سوال: 
{question_text}

🔢 گزینه‌ها:
1️⃣ {option_1}
2️⃣ {option_2}
3️⃣ {option_3}
4️⃣ {option_4}

✅ گزینه صحیح: {correct_option}

لطفاً سوال دیگری ارسال کنید.
""" + SPONSOR_FOOTER,
    "admin_question_approved": "✅ سوال با موفقیت تأیید شد." + SPONSOR_FOOTER,
    "admin_question_rejected": "❌ سوال رد شد." + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    
    # Keyboard button texts
    "btn_cancel": "❌ لغو",
    "btn_approve": "✅ تأیید",
    "btn_reject": "❌ رد",
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

    try:
        topics = db.get_all_topics()
        if not topics:
            return None

        kb = InlineKeyboardBuilder()
        for topic in topics:
            if topic.get("is_active", True):
                kb.button(text=topic["name"], callback_data=f"add_question_topic_{topic['topic_id']}")

        kb.button(text=MESSAGES["btn_cancel"], callback_data="add_question_cancel")
        kb.adjust(2) 
        return kb.as_markup()
    except Exception as e:
        logger.error(f"Error creating topics keyboard: {e}")
        return None


def get_options_keyboard(options: List[str]) -> InlineKeyboardMarkup:
  
    kb = InlineKeyboardBuilder()
    for i, option in enumerate(options):
        display_text = option if len(option) <= 20 else option[:17] + "..."
        kb.button(text=f"{i + 1}. {display_text}", callback_data=f"add_question_correct_{i}")

    kb.button(text=MESSAGES["btn_cancel"], callback_data="add_question_cancel")
    kb.adjust(1) 
    return kb.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:

    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_cancel"], callback_data="add_question_cancel")
    return kb.as_markup()


def get_admin_approval_keyboard(question_id: str) -> InlineKeyboardMarkup:

    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_approve"], callback_data=f"approve_question_{question_id}")
    kb.button(text=MESSAGES["btn_reject"], callback_data=f"reject_question_{question_id}")
    kb.adjust(2) 
    return kb.as_markup()


@add_question_router.message(Command("add_question"), F.from_user.id == config.ADMIN_ID)
async def cmd_add_question_admin(message: Message, state: FSMContext) -> None:


    try:
        await state.clear()

        await state.update_data(is_admin=True)
        
        await start_question_adding_process(message, state)
        logger.info(f"Admin {message.from_user.id} initiated question creation")
    except Exception as e:
        logger.error(f"Error in add_question command: {e}")


@add_question_router.message(F.text == config.MAIN_MENU_SUBMIT_QUESTION_BUTTON)
async def cmd_submit_question_user(message: Message, state: FSMContext) -> None:

    try:
        await state.clear()
        await state.update_data(is_admin=False)
        await start_question_adding_process(message, state)
        logger.info(f"User {message.from_user.id} initiated question submission")
    except Exception as e:
        logger.error(f"Error in submit question button: {e}")


async def start_question_adding_process(message: Message, state: FSMContext) -> None:

    try:
        keyboard = get_topics_keyboard()
        if not keyboard:
            await message.answer(
                MESSAGES["no_topics"],
                parse_mode=ParseMode.HTML
            )
            return

        await state.set_state(AddQuestionStates.selecting_topic)
        await message.answer(
            MESSAGES["select_topic"],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error starting question adding process: {e}")
       


@add_question_router.callback_query(F.data == "add_question_cancel")
async def cancel_add_question(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer()
    
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
        logger.info(f"User {callback.from_user.id} cancelled question creation")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")



@add_question_router.callback_query(F.data.startswith("add_question_topic_"))
async def topic_selected(callback: CallbackQuery, state: FSMContext) -> None:
 
    await callback.answer()
    
    topic_id = callback.data.split("_")[3]

    try:
        await state.update_data(topic_id=topic_id)

        response = db.get_topic_by_id(topic_id)
        if response["status"] == "error":
            logger.error(f"Error getting topic by ID: {response['message']}")
            await safe_edit_message(
                callback.message,
                MESSAGES["error_general"]
            )
            await state.clear()
            return

        topic = response["topic"]
        await state.update_data(topic_name=topic["name"])

        await state.set_state(AddQuestionStates.entering_question)

        await safe_edit_message(
            callback.message,
            MESSAGES["enter_question"],
            get_cancel_keyboard()
        )
        logger.info(f"User {callback.from_user.id} selected topic: {topic['name']} (ID: {topic_id})")
    except Exception as e:
        logger.error(f"Error in topic selection: {e}")
        await callback.answer()



async def validate_text_input(message: Message, min_length: int, max_length: int, 
                             too_short_message: str, too_long_message: str) -> Tuple[bool, Optional[str]]:
   
    text = message.text.strip()
    
    if len(text) < min_length:
        await message.answer(
            too_short_message, 
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return False, None
        
    if len(text) > max_length:
        await message.answer(
            too_long_message, 
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return False, None
        
    return True, text


async def handle_invalid_input(message: Message) -> None:
 
    await message.answer(
        MESSAGES["only_text"], 
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    logger.warning(f"User {message.from_user.id} sent non-text message when text was expected")



@add_question_router.message(AddQuestionStates.entering_question, F.text)
async def process_question_text(message: Message, state: FSMContext) -> None:
   
    try:
        valid, question_text = await validate_text_input(
            message=message,
            min_length=config.QUESTION_MIN_LENGTH,
            max_length=config.QUESTION_MAX_LENGTH,
            too_short_message=MESSAGES["question_too_short"],
            too_long_message=MESSAGES["question_too_long"]
        )
        
        if not valid:
            return

        await state.update_data(question_text=question_text)
        await state.set_state(AddQuestionStates.entering_option_1)

        await message.answer(
            MESSAGES["enter_option"].format(1),
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"User {message.from_user.id} entered question text: {question_text[:30]}...")
    except Exception as e:
        logger.error(f"Error processing question text: {e}")


@add_question_router.message(AddQuestionStates.entering_question)
async def invalid_question_input(message: Message) -> None:

    await handle_invalid_input(message)



async def process_option_input(message: Message, state: FSMContext, option_number: int, next_state: State) -> None:

    try:
        valid, option_text = await validate_text_input(
            message=message,
            min_length=config.OPTION_MIN_LENGTH,
            max_length=config.OPTION_MAX_LENGTH,
            too_short_message=MESSAGES["option_too_short"],
            too_long_message=MESSAGES["option_too_long"]
        )
        
        if not valid:
            return

        await state.update_data({f"option_{option_number}": option_text})
        await state.set_state(next_state)

        if next_state != AddQuestionStates.selecting_correct_option:
            next_option_number = option_number + 1
            await message.answer(
                MESSAGES["enter_option"].format(next_option_number),
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"User {message.from_user.id} entered option {option_number}: {option_text[:20]}...")
        else:
            data = await state.get_data()
            
            options = [
                data["option_1"],
                data["option_2"],
                data["option_3"],
                data["option_4"]
            ]
            
            await state.update_data(options=options)
            
            await message.answer(
                MESSAGES["select_correct_option"],
                reply_markup=get_options_keyboard(options),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"User {message.from_user.id} entered all options, prompting for correct option")
    except Exception as e:
        logger.error(f"Error processing option {option_number}: {e}")


@add_question_router.message(AddQuestionStates.entering_option_1, F.text)
async def process_option_1(message: Message, state: FSMContext) -> None:
    await process_option_input(message, state, 1, AddQuestionStates.entering_option_2)


@add_question_router.message(AddQuestionStates.entering_option_2, F.text)
async def process_option_2(message: Message, state: FSMContext) -> None:
    await process_option_input(message, state, 2, AddQuestionStates.entering_option_3)


@add_question_router.message(AddQuestionStates.entering_option_3, F.text)
async def process_option_3(message: Message, state: FSMContext) -> None:
    await process_option_input(message, state, 3, AddQuestionStates.entering_option_4)


@add_question_router.message(AddQuestionStates.entering_option_4, F.text)
async def process_option_4(message: Message, state: FSMContext) -> None:
    await process_option_input(message, state, 4, AddQuestionStates.selecting_correct_option)


@add_question_router.message(AddQuestionStates.entering_option_1)
@add_question_router.message(AddQuestionStates.entering_option_2)
@add_question_router.message(AddQuestionStates.entering_option_3)
@add_question_router.message(AddQuestionStates.entering_option_4)
async def invalid_option_input(message: Message) -> None:

    await handle_invalid_input(message)



@add_question_router.callback_query(F.data.startswith("add_question_correct_"))
async def correct_option_selected(callback: CallbackQuery, state: FSMContext) -> None:

    await callback.answer()
    
    correct_option = int(callback.data.split("_")[3])

    try:
        data = await state.get_data()
        topic_id = data["topic_id"]
        topic_name = data["topic_name"]
        question_text = data["question_text"]
        options = data["options"]
        is_admin = data.get("is_admin", False)

        user_id = str(callback.from_user.id)
        user_name = callback.from_user.username or callback.from_user.full_name or user_id
        
        response = db.create_question(
            topic_id=topic_id,
            question_text=question_text,
            options=options,
            correct_option=correct_option,
            created_by=user_id,
            is_approved=is_admin
        )

        await state.clear()

        if response["status"] == "error":
            logger.error(f"Error creating question: {response['message']}")
            await safe_edit_message(
                callback.message,
                MESSAGES["error_general"]
            )
            return

        if is_admin:
            await safe_edit_message(
                callback.message,
                MESSAGES["question_added"]
            )
            logger.info(f"Admin {callback.from_user.id} added question directly: {question_text[:30]}...")
        else:
            await safe_edit_message(
                callback.message,
                MESSAGES["question_submitted"]
            )
            logger.info(f"User {callback.from_user.id} submitted question for approval: {question_text[:30]}...")

            question_id = response["question"]["question_id"]
            await notify_admin_for_approval(
                user_id=user_id,
                user_name=user_name,
                topic_name=topic_name,
                question_text=question_text,
                options=options,
                correct_option=correct_option + 1,  
                question_id=question_id
            )

        try:
            await callback.message.answer(
                text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
                reply_markup=main_menu_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error returning to main menu: {e}")
    except Exception as e:
        logger.error(f"Error creating question: {e}")
        await callback.answer()


async def notify_admin_for_approval(user_id: str, user_name: str, topic_name: str, 
                                  question_text: str, options: List[str], 
                                  correct_option: int, question_id: str) -> None:

    try:
        admin_message = MESSAGES["admin_new_question"].format(
            user_id=user_id,
            user_name=user_name,
            topic_name=topic_name,
            question_text=question_text,
            option_1=options[0],
            option_2=options[1],
            option_3=options[2],
            option_4=options[3],
            correct_option=correct_option
        )

        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=admin_message,
            reply_markup=get_admin_approval_keyboard(question_id),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Sent approval notification to admin for question ID {question_id}")
    except Exception as e:
        logger.error(f"Error sending question approval notification to admin: {e}")




async def process_question_decision(callback: CallbackQuery, is_approve: bool) -> None:

    await callback.answer()
    
    action = "approve" if is_approve else "reject"
    question_id = callback.data.split("_")[2]
    
    try:
        question_data = db.get_question_by_id(question_id)

        if question_data["status"] != "success":
            logger.error(f"Question not found during {action} process: {question_id}")
            await safe_edit_message(
                callback.message,
                f"{callback.message.text}\n\n{MESSAGES['error_question_not_found']}"
            )
            return

        question = question_data["question"]
        user_id = question["created_by"]

        topic_response = db.get_topic_by_id(question["topic_id"])
        if topic_response["status"] != "success":
            logger.error(f"Topic not found during question {action}: {question['topic_id']}")
            topic_name = "Unknown"
        else:
            topic_name = topic_response["topic"]["name"]

        try:
            message_key = "question_approved" if is_approve else "question_rejected"
            await bot.send_message(
                chat_id=int(user_id),
                text=MESSAGES[message_key].format(
                    topic_name=topic_name,
                    question_text=question["text"],
                    option_1=question["options"][0],
                    option_2=question["options"][1],
                    option_3=question["options"][2],
                    option_4=question["options"][3],
                    correct_option=question["correct_option"] + 1  
                ),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Sent {action} notification to user {user_id}")
        except Exception as e:
            logger.error(f"Error notifying user about question {action}: {e}")

        db_method = db.approve_question if is_approve else db.reject_question
        response = db_method(question_id)

        if response["status"] == "error":
            logger.error(f"Database error during question {action}: {response['message']}")
            await safe_edit_message(
                callback.message,
                f"{callback.message.text}\n\n{MESSAGES['error_db_operation']}"
            )
            return

        message_key = "admin_question_approved" if is_approve else "admin_question_rejected"
        symbol = "✅" if is_approve else "❌"
        await safe_edit_message(
            callback.message,
            f"{callback.message.text}\n\n{symbol} {MESSAGES[message_key]}"
        )
        logger.info(f"Admin {callback.from_user.id} {action}d question {question_id}")
    except Exception as e:
        logger.error(f"Error {action}ing question: {e}")
        await callback.answer()


@add_question_router.callback_query(F.data.startswith("approve_question_"))
async def approve_question_callback(callback: CallbackQuery) -> None:
    await process_question_decision(callback, is_approve=True)


@add_question_router.callback_query(F.data.startswith("reject_question_"))
async def reject_question_callback(callback: CallbackQuery) -> None:
    await process_question_decision(callback, is_approve=False)
