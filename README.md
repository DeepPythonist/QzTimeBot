# 🎮 ربات کوییز تلگرام (QzTimeBot)


<div dir="rtl">

## 📝 توضیحات

ربات کوییز تلگرام یک پلتفرم آموزشی و سرگرمی است که به کاربران امکان می‌دهد کوییزهای تعاملی با موضوعات مختلف ایجاد کنند، در آن‌ها شرکت کنند و با دوستان خود به رقابت بپردازند. این ربات با زبان پایتون و کتابخانه aiogram 3 توسعه یافته است.

## 🚀 ویژگی‌های اصلی

- **ایجاد و مدیریت کوییز**: ایجاد کوییزهای جدید با موضوعات متنوع
- **شخصی‌سازی کوییز**: انتخاب تعداد سوالات و زمان پاسخگویی
- **حالت چند نفره**: امکان شرکت همزمان چندین کاربر در یک کوییز
- **امتیازدهی هوشمند**: سیستم امتیازدهی بر اساس سرعت و صحت پاسخ‌ها
- **رتبه‌بندی**: نمایش رتبه‌بندی شرکت‌کنندگان در پایان هر کوییز
- **آمار کاربران**: نمایش آمار فردی و گروهی کاربران
- **ارسال و مدیریت سوالات**: امکان ارسال سوالات جدید توسط کاربران با تایید ادمین
- **جستجوی کوییز**: یافتن کوییزها بر اساس موضوع

## 🛠️ پیش‌نیازها

- پایتون 3.10 یا بالاتر
- مونگو دیتابیس
- ردیس (برای محدودیت درخواست‌ها و کش کردن)
- توکن ربات تلگرام (از BotFather دریافت می‌شود)

## ⚙️ نصب و راه‌اندازی

1. **کلون کردن مخزن**
   ```bash
   git clone https://github.com/DeepPythonist/QzTimeBot.git
   cd QzTimeBot
   ```

2. **ایجاد محیط مجازی و نصب وابستگی‌ها**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # در لینوکس/مک
   # یا
   .venv\Scripts\activate  # در ویندوز
   
   pip install -r requirements.txt
   ```

3. **تنظیم فایل config.py**
   ```python
   # تنظیم توکن ربات
   BOT_TOKEN = "YOUR_BOT_TOKEN"
   
   # تنظیم کانال اسپانسر
   SPONSOR_CHANNEL_ID = -10012345678
   SPONSOR_CHANNEL_NAME = "نام کانال"
   SPONSOR_CHANNEL_URL = "https://t.me/your_channel"
   
   # تنظیم آیدی ادمین‌ها
   ADMIN_IDS = ["1234567890"]
   ```

4. **اجرای ربات**
   ```bash
   python bot.py
   ```

## 📂 ساختار پروژه

```
EsfiQuizBot/
├── bot.py               # فایل اصلی برای راه‌اندازی ربات
├── config.py            # تنظیمات ربات
├── db.py                # تعاملات با پایگاه داده
├── utils.py             # توابع و ثابت‌های مشترک
├── requirements.txt     # وابستگی‌های پروژه
├── plugins/             # ماژول‌های مختلف ربات
│   ├── start_bot.py     # شروع ربات و منوی اصلی
│   ├── search_quiz.py   # جستجوی کوییز
│   ├── join_quiz.py     # پیوستن به کوییز
│   ├── start_quiz.py    # شروع کوییز
│   └── ...              # سایر ماژول‌ها
└── .gitignore           # فایل‌های نادیده گرفته‌شده در گیت
```

## 📋 دستورات ربات

- **/start** - شروع ربات و بازگشت به منوی اصلی
- **/help** - نمایش راهنمای ربات
- **/search** - جستجوی کوییز براساس موضوع

## 👑 دستورات ادمین

- **/add_topic** - افزودن موضوع جدید
- **/edit_topic** - ویرایش موضوع موجود
- **/delete_topic** - حذف موضوع
- **/pending** - مدیریت سوالات در انتظار تایید
- **/stats** - مشاهده آمار کلی ربات

## 🤝 مشارکت در توسعه

از همکاری شما در توسعه این پروژه استقبال می‌شود! لطفاً pull request‌های خود را برای بررسی ارسال کنید.

### تماس با ما

برای ارتباط با تیم توسعه می‌توانید از تلگرام یا ایمیل استفاده کنید:
- کانال تلگرام: [DeepPythonist](https://t.me/DeepPythonist)
- ایمیل: [mrasolesfandiari@gmail.com](mailto:mrasolesfandiari@gmail.com)

</div>

---

# 🎮 Telegram Quiz Bot (QzTimeBot)


## 📝 Description

Telegram Quiz Bot is an educational and entertainment platform that allows users to create interactive quizzes on various topics, participate in them, and compete with friends. This bot is developed using Python and the aiogram 3 library.

## 🚀 Key Features

- **Quiz Creation and Management**: Create new quizzes on various topics
- **Quiz Customization**: Choose the number of questions and response time
- **Multiplayer Mode**: Multiple users can participate in a quiz simultaneously
- **Smart Scoring**: Scoring system based on speed and accuracy of answers
- **Leaderboards**: Display rankings of participants at the end of each quiz
- **User Statistics**: Display individual and group user statistics
- **Question Submission and Management**: Users can submit new questions, subject to admin approval
- **Quiz Search**: Find quizzes by topic

## 🛠️ Prerequisites

- Python 3.10 or higher
- MongoDB
- Redis (for rate limiting and caching)
- Telegram bot token (obtained from BotFather)

## ⚙️ Installation and Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/DeepPythonist/QzTimeBot.git
   cd QzTimeBot
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   
   pip install -r requirements.txt
   ```

3. **Configure the config.py file**
   ```python
   # Set bot token
   BOT_TOKEN = "YOUR_BOT_TOKEN"
   
   # Set sponsor channel
   SPONSOR_CHANNEL_ID = -10012345678
   SPONSOR_CHANNEL_NAME = "Channel Name"
   SPONSOR_CHANNEL_URL = "https://t.me/your_channel"
   
   # Set admin IDs
   ADMIN_IDS = ["1234567890"]
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## 📂 Project Structure

```
EsfiQuizBot/
├── bot.py               # Main file for launching the bot
├── config.py            # Bot settings
├── db.py                # Database interactions
├── utils.py             # Shared functions and constants
├── requirements.txt     # Project dependencies
├── plugins/             # Various bot modules
│   ├── start_bot.py     # Bot start and main menu
│   ├── search_quiz.py   # Quiz search
│   ├── join_quiz.py     # Joining a quiz
│   ├── start_quiz.py    # Starting a quiz
│   └── ...              # Other modules
└── .gitignore           # Files ignored in git
```

## 📋 Bot Commands

- **/start** - Start the bot and return to the main menu
- **/help** - Display bot help
- **/search** - Search for a quiz by topic

## 👑 Admin Commands

- **/add_topic** - Add a new topic
- **/edit_topic** - Edit an existing topic
- **/delete_topic** - Delete a topic
- **/pending** - Manage pending questions
- **/stats** - View overall bot statistics

## 🤝 Contributing

Your collaboration in developing this project is welcome! Please submit your pull requests for review.

### Contact Us

To contact the development team, you can use Telegram or email:
- Telegram channel: [DeepPythonist](https://t.me/DeepPythonist)
- Email: [mrasolesfandiari@gmail.com](mailto:mrasolesfandiari@gmail.com)

## 📜 License

This project is licensed under the MIT License - see the LICENSE.md file for details. 