from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

from bot import db, bot
import config
import logging
from typing import Optional, Dict, Any, Union, List
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)

edit_topic_router = Router(name="edit_topic")


class EditTopicStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()


SPONSOR_FOOTER = f" "

MESSAGES = {
    "not_found": "📭 هیچ موضوعی یافت نشد" + SPONSOR_FOOTER,
    "select_topic": "🔍 لطفاً موضوع مورد نظر برای ویرایش را انتخاب کنید:" + SPONSOR_FOOTER,
    "enter_name": "✏️ لطفاً نام جدید موضوع را وارد کنید:" + SPONSOR_FOOTER,
    "enter_description": "📝 لطفاً توضیحات جدید موضوع را وارد کنید:" + SPONSOR_FOOTER,
    "name_updated": "✅ نام موضوع با موفقیت به‌روزرسانی شد!" + SPONSOR_FOOTER,
    "description_updated": "✅ توضیحات موضوع با موفقیت به‌روزرسانی شد!" + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داده است: {error}" + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    "name_empty": "⚠️ نام موضوع نمی‌تواند خالی باشد." + SPONSOR_FOOTER,
    "name_length": "⚠️ طول نام موضوع باید بین {min} و {max} کاراکتر باشد." + SPONSOR_FOOTER,
    "name_exists": "⚠️ موضوعی با این نام قبلاً وجود دارد. لطفاً نام دیگری انتخاب کنید." + SPONSOR_FOOTER,
    "desc_empty": "⚠️ توضیحات موضوع نمی‌تواند خالی باشد." + SPONSOR_FOOTER, 
    "desc_length": "⚠️ طول توضیحات موضوع باید بین {min} و {max} کاراکتر باشد." + SPONSOR_FOOTER,
    "only_text": "⚠️ لطفاً برای {field} موضوع، فقط پیام متنی ارسال کنید." + SPONSOR_FOOTER,
    "status_changed": "🔄 وضعیت فعال بودن به: {status} تغییر یافت" + SPONSOR_FOOTER,
    "topic_info": """
🔖 نام موضوع: 
{name}

📄 توضیحات موضوع: 
{description}

⚡ وضعیت فعال: 
{is_active}

🕒 تاریخ ایجاد: 
{created_at}

🔄 تاریخ به‌روزرسانی: 
{updated_at}
""" + SPONSOR_FOOTER,

    "btn_edit_name": "✏️ ویرایش نام",
    "btn_edit_desc": "📝 ویرایش توضیحات",
    "btn_toggle_status": "🔄 تغییر وضعیت فعال",
    "btn_cancel": "❌ لغو",
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


def get_topic_info(topic: Dict[str, Any]) -> str:

    return MESSAGES["topic_info"].format(
        name=topic['name'],
        description=topic['description'],
        is_active=topic['is_active'],
        created_at=topic['created_at'],
        updated_at=topic['updated_at']
    )


def get_topic_edit_keyboard(topic_id: str) -> InlineKeyboardMarkup:

    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_edit_name"], callback_data=f"edit_name_{topic_id}")
    kb.button(text=MESSAGES["btn_edit_desc"], callback_data=f"edit_desc_{topic_id}")
    kb.button(text=MESSAGES["btn_toggle_status"], callback_data=f"toggle_{topic_id}")
    kb.button(text=MESSAGES["btn_cancel"], callback_data="edit_cancel")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def get_topics_list_keyboard() -> Optional[InlineKeyboardMarkup]:
 
    topics = db.get_all_topics()
    if not topics:
        return None

    kb = InlineKeyboardBuilder()
    for topic in topics:
        kb.button(text=topic["name"], callback_data=f"view_{topic['topic_id']}")

    kb.button(text=MESSAGES["btn_cancel"], callback_data="edit_cancel")
    kb.adjust(2)
    return kb.as_markup()


@edit_topic_router.message(Command("edit_topic"), F.from_user.id == config.ADMIN_ID)
async def cmd_edit_topic(message: Message) -> None:

    try:
        keyboard = get_topics_list_keyboard()
        if not keyboard:
            await message.answer(
                MESSAGES["not_found"],
                parse_mode=ParseMode.HTML
            )
            return

        await message.answer(
            MESSAGES["select_topic"], 
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} initiated topic editing")
    except Exception as e:
        logger.error(f"Error in edit_topic command: {e}")



@edit_topic_router.callback_query(F.data == "edit_cancel")
async def cancel_edit(callback: CallbackQuery, state: FSMContext) -> None:

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
        logger.info(f"Admin {callback.from_user.id} cancelled topic editing")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")


@edit_topic_router.callback_query(F.data.startswith("view_"))
async def view_topic(callback: CallbackQuery) -> None:

    topic_id = callback.data.split("_")[1]

    try:
        response = db.get_topic_by_id(topic_id)
        if response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["not_found"]
            )
            await callback.answer()
            return

        topic = response["topic"]
        info_text = get_topic_info(topic)

        await safe_edit_message(
            callback.message,
            text=info_text,
            reply_markup=get_topic_edit_keyboard(topic_id)
        )
        
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewing topic {topic_id}")
    except Exception as e:
        logger.error(f"Error viewing topic: {e}")
        await callback.answer()


@edit_topic_router.callback_query(F.data.startswith("edit_name_"))
async def edit_name(callback: CallbackQuery, state: FSMContext) -> None:

    try:
        topic_id = callback.data.split("_")[2]

        await state.update_data(topic_id=topic_id)
        await state.set_state(EditTopicStates.waiting_for_name)

        await safe_edit_message(
            callback.message,
            MESSAGES["enter_name"]
        )
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} started editing name of topic {topic_id}")
    except Exception as e:
        logger.error(f"Error starting name edit: {e}")
        await callback.answer()


@edit_topic_router.callback_query(F.data.startswith("edit_desc_"))
async def edit_description(callback: CallbackQuery, state: FSMContext) -> None:

    try:
        topic_id = callback.data.split("_")[2]

        await state.update_data(topic_id=topic_id)
        await state.set_state(EditTopicStates.waiting_for_description)

        await safe_edit_message(
            callback.message,
            MESSAGES["enter_description"]
        )
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} started editing description of topic {topic_id}")
    except Exception as e:
        logger.error(f"Error starting description edit: {e}")
        await callback.answer()


@edit_topic_router.callback_query(F.data.startswith("toggle_"))
async def toggle_active_status(callback: CallbackQuery) -> None:

    try:
        topic_id = callback.data.split("_")[1]

        response = db.get_topic_by_id(topic_id)
        if response["status"] == "error":
            await safe_edit_message(
                callback.message,
                MESSAGES["not_found"]
            )
            await callback.answer()
            return

        topic = response["topic"]
        new_status = not topic["is_active"]

        db.edit_topic_active_status(topic_id, new_status)

        updated_response = db.get_topic_by_id(topic_id)
        updated_topic = updated_response["topic"]

        await safe_edit_message(
            callback.message,
            text=get_topic_info(updated_topic),
            reply_markup=get_topic_edit_keyboard(topic_id)
        )
        await callback.answer(MESSAGES["status_changed"].format(status=new_status))
        logger.info(f"Admin {callback.from_user.id} changed active status of topic {topic_id} to {new_status}")
    except Exception as e:
        logger.error(f"Error toggling active status: {e}")
        await callback.answer()



@edit_topic_router.message(EditTopicStates.waiting_for_name, F.text)
async def process_new_name(message: Message, state: FSMContext) -> None:

    try:
        data = await state.get_data()
        topic_id = data.get("topic_id")
        new_name = message.text.strip()

        if not new_name:
            await message.answer(
                MESSAGES["name_empty"],
                parse_mode=ParseMode.HTML
            )
            return

        if len(new_name) < config.TOPIC_NAME_MIN_LENGTH or len(new_name) > config.TOPIC_NAME_MAX_LENGTH:
            await message.answer(
                MESSAGES["name_length"].format(
                    min=config.TOPIC_NAME_MIN_LENGTH,
                    max=config.TOPIC_NAME_MAX_LENGTH
                ),
                parse_mode=ParseMode.HTML
            )
            return

        existing_topic = db.get_topic_by_name(new_name)
        if existing_topic["status"] == "success" and existing_topic["topic"]["topic_id"] != topic_id:
            await message.answer(
                MESSAGES["name_exists"],
                parse_mode=ParseMode.HTML
            )
            return

        db.edit_topic_name(topic_id, new_name)

        await state.clear()

        await message.answer(
            MESSAGES["name_updated"],
            parse_mode=ParseMode.HTML
        )

        response = db.get_topic_by_id(topic_id)
        topic = response["topic"]

        await message.answer(
            text=get_topic_info(topic),
            reply_markup=get_topic_edit_keyboard(topic_id),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} updated name of topic {topic_id} to '{new_name}'")
    except Exception as e:
        logger.error(f"Error updating topic name: {e}")
        await state.clear()



@edit_topic_router.message(EditTopicStates.waiting_for_name)
async def process_invalid_name_input(message: Message) -> None:

    await message.answer(
        MESSAGES["only_text"].format(field="name"),
        parse_mode=ParseMode.HTML
    )


@edit_topic_router.message(EditTopicStates.waiting_for_description, F.text)
async def process_new_description(message: Message, state: FSMContext) -> None:

    try:
        data = await state.get_data()
        topic_id = data.get("topic_id")
        new_description = message.text.strip()

        if not new_description:
            await message.answer(
                MESSAGES["desc_empty"],
                parse_mode=ParseMode.HTML
            )
            return

        if len(new_description) < config.TOPIC_DESCRIPTION_MIN_LENGTH or len(
                new_description) > config.TOPIC_DESCRIPTION_MAX_LENGTH:
            await message.answer(
                MESSAGES["desc_length"].format(
                    min=config.TOPIC_DESCRIPTION_MIN_LENGTH,
                    max=config.TOPIC_DESCRIPTION_MAX_LENGTH
                ),
                parse_mode=ParseMode.HTML
            )
            return

        db.edit_topic_description(topic_id, new_description)

        await state.clear()

        await message.answer(
            MESSAGES["description_updated"],
            parse_mode=ParseMode.HTML
        )

        response = db.get_topic_by_id(topic_id)
        topic = response["topic"]

        await message.answer(
            text=get_topic_info(topic),
            reply_markup=get_topic_edit_keyboard(topic_id),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} updated description of topic {topic_id}")
    except Exception as e:
        logger.error(f"Error updating topic description: {e}")
        await state.clear()



@edit_topic_router.message(EditTopicStates.waiting_for_description)
async def process_invalid_description_input(message: Message) -> None:

    await message.answer(
        MESSAGES["only_text"].format(field="description"),
        parse_mode=ParseMode.HTML
    )
