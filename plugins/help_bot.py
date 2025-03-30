from aiogram import Router, F
from aiogram.types import Message
from config import MAIN_MENU_HELP_BUTTON
from bot import db
import config
from aiogram.enums import ParseMode
help_router = Router(name="help_bot")


help_message = f"""
<b>🎮 ربات کوییز تلگرامی</b>

این ربات به شما امکان شرکت در کوییزهای متنوع با موضوعات مختلف را می‌دهد. شما می‌توانید کوییزهای جدید ایجاد کنید یا به کوییزهای دوستان خود بپیوندید.

<b>ویژگی‌های اصلی:</b>
• امکان جستجو و انتخاب موضوعات مختلف
• تنظیم تعداد سوالات و زمان پاسخگویی
• رقابت آنلاین با دوستان و سایر کاربران
• مشاهده امتیازات و رتبه‌بندی
• رابط کاربری ساده و روان

برای شروع، از منوی اصلی دکمه <b>{config.MAIN_MENU_START_QUIZ_BUTTON}</b> در پایین استفاده کنید.
"""
@help_router.message(F.text == MAIN_MENU_HELP_BUTTON)
async def help_command(message: Message):
    db.create_user(user_id=message.from_user.id,
                   username=message.from_user.username if message.from_user.username else None,
                   full_name=message.from_user.full_name if message.from_user.full_name else "",
                   has_start=True)
    await message.answer(text=help_message, parse_mode=ParseMode.HTML)





