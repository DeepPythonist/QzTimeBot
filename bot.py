from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
import config
import asyncio
import logging
from db import Database
from typing import Union, Callable, Any
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


dp = Dispatcher()
bot = Bot(token=config.BOT_TOKEN)
db = Database()




async def main():
    logger.info("Bot initialization started...")
    bot.delete_webhook(drop_pending_updates=True)
    
    
    logger.info("Loading routers...")
    # Import routers
    logger.info("Loading start_router...")
    from plugins.start_bot import start_router
    
    logger.info("Loading add_topic_router...")
    from plugins.add_topic import add_topic_router
    
    logger.info("Loading edit_topic_router...")
    from plugins.edit_topic import edit_topic_router
    
    logger.info("Loading delete_topic_router...")
    from plugins.delete_topic import delete_topic_router
    
    logger.info("Loading add_question_router...")
    from plugins.add_question import add_question_router
    
    logger.info("Loading delete_question_router...")
    from plugins.delete_question import delete_question_router
    
    logger.info("Loading pending_questions_router...")
    from plugins.pending_questions import pending_questions_router
    
    logger.info("Loading leaderboard_router...")
    from plugins.leaderboard import leaderboard_router
    
    logger.info("Loading quiz_router...")
    from plugins.quiz import quiz_router
    
    logger.info("Loading search_quiz_router...")
    from plugins.search_quiz import search_quiz_router
    
    logger.info("Loading join_quiz_router...")
    from plugins.join_quiz import join_quiz_router
    
    logger.info("Loading start_quiz_router...")
    from plugins.start_quiz import start_quiz_router
    
    logger.info("Loading admin_stats_router...")
    from plugins.admin_stats import admin_stats_router
    
    logger.info("Loading help_router...")
    from plugins.help_bot import help_router

    logger.info("Loading admin_help_router...")
    from plugins.admin_help import admin_help_router
    
    # Include routers
    logger.info("Including routers in dispatcher...")
    dp.include_router(start_router)
    dp.include_router(add_topic_router)
    dp.include_router(edit_topic_router)
    dp.include_router(delete_topic_router)
    dp.include_router(add_question_router)
    dp.include_router(delete_question_router)
    dp.include_router(pending_questions_router)
    dp.include_router(leaderboard_router)
    dp.include_router(quiz_router)
    dp.include_router(search_quiz_router)
    dp.include_router(join_quiz_router)
    dp.include_router(start_quiz_router)
    dp.include_router(admin_stats_router)
    dp.include_router(help_router)
    dp.include_router(admin_help_router)
    logger.info("All routers loaded successfully. Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())