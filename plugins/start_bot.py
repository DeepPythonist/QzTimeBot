from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from bot import db
from utils import limit_user_requests
import config

start_router = Router(name="start_bot")


# Main Menu Buttons
main_menu_start_quiz_button = KeyboardButton(text=config.MAIN_MENU_START_QUIZ_BUTTON)
main_menu_leaderboard_button = KeyboardButton(text=config.MAIN_MENU_LEADERBOARD_BUTTON)
main_menu_global_leaderboard_button = KeyboardButton(text=config.MAIN_MENU_GLOBAL_LEADERBOARD_BUTTON)
main_menu_help_button = KeyboardButton(text=config.MAIN_MENU_HELP_BUTTON)
main_menu_submit_question_button = KeyboardButton(text=config.MAIN_MENU_SUBMIT_QUESTION_BUTTON)


# Main Menu Keyboard    
main_menu_keyboard = ReplyKeyboardMarkup(keyboard=[
    [main_menu_start_quiz_button],
    [main_menu_leaderboard_button, main_menu_global_leaderboard_button],
    [main_menu_help_button, main_menu_submit_question_button],
], resize_keyboard=True)


# main menu texts
welcome_message = """
🎉 *سلام {full_name}!* 🎉

🧠 به ربات هوشمند کوئیز **{bot_name}** خوش آمدید 🧠

با این ربات می‌توانید:
🎯 در کوئیزهای متنوع و چالشی شرکت کنید
📊 آمار عملکرد خود را مشاهده کنید
🌎 در رتبه‌بندی جهانی با دیگران رقابت کنید
✍️ سوالات جدید ارسال کرده و در غنی‌سازی محتوا سهیم باشید

👇 برای شروع، یکی از گزینه‌های زیر را انتخاب کنید 👇

💡 *نکته:* هر چه در بیشتر کوئیزها شرکت کنید و سوالات بیشتری بفرستید، امتیاز بالاتری کسب خواهید کرد!

"""


@start_router.message(F.text == "/start")
@limit_user_requests(seconds=1)
async def start_command(message: Message):
    db.create_user(user_id=message.from_user.id, 
                   username=message.from_user.username if message.from_user.username else None,
                   full_name=message.from_user.full_name if message.from_user.full_name else "",
                   has_start=True)
    
    await message.answer(text=welcome_message.format(full_name=message.from_user.full_name, 
                                                     bot_name=config.BOT_NAME), reply_markup=main_menu_keyboard,
                                                     parse_mode=ParseMode.MARKDOWN)








