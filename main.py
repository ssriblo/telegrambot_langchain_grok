from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import os

from llm import generate_reply
from state import get_user_state, update_stage, set_language


# Инициализация
load_dotenv()  # загружаем переменные из .env

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message()
async def handle_message(message: types.Message):
    user_input = message.text or ""
    user_id = message.from_user.id

    state = get_user_state(user_id)

    # Первое сообщение пользователя: настраиваем язык и стадию
    if state.stage == "NEW_USER":
        tg_lang = (message.from_user.language_code or "en").lower()
        if tg_lang.startswith("ru"):
            set_language(user_id, "ru")
        else:
            set_language(user_id, "en")

        update_stage(user_id, "FREE_CHAT")  # пока просто общение, позже добавим анкету/маршруты

    print(f"[{state.language}] Получено сообщение от пользователя {user_id}: {user_input}")

    # Пока вся логика ответа — в llm.generate_reply
    reply_text = generate_reply(user_id=user_id, user_input=user_input)

    print(f"Ответ от модели: {reply_text}")
    await message.answer(reply_text)


if __name__ == "__main__":
    dp.run_polling(bot)
