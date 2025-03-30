from aiogram import Router, F
from aiogram.types import Message
import config
from aiogram.filters import Command


admin_help_router = Router(name="admin_help")


admin_help_message = """
📊 <b>دستورات مدیریتی:</b>

🔍 /stats - مشاهده آمار سرور

📝 /add_topic - اضافه کردن موضوع جدید
🗑️ /delete_topic - حذف موضوع انتخابی
✏️ /edit_topic - ویرایش موضوع موجود

❓ /add_question - اضافه کردن سوال جدید
🗑️ /delete_question - حذف سوال انتخابی
🔄 /pending_questions - مشاهده سوالات در انتظار تایید

"""


@admin_help_router.message(Command("help"), F.from_user.id == config.ADMIN_ID)
async def show_admin_help(message: Message) -> None:
    await message.answer(admin_help_message)

