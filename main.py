from aiogram import Bot, Dispatcher, types, F
from dotenv import load_dotenv
import os

from llm import generate_reply
from state import (
    get_user_state,
    update_stage,
    set_language,
    set_style,
    set_raw_preferences,
    set_location,
)
from data_gyumri import get_nearby_places, format_places_for_user


# Инициализация
load_dotenv()  # загружаем переменные из .env

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


def _detect_language(message: types.Message, text: str) -> str:
    """
    Простая эвристика:
    - если в тексте есть кириллица — считаем, что это русский;
    - иначе смотрим на language_code Telegram;
    - по умолчанию — английский.
    """
    if any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in text):
        return "ru"

    code = (message.from_user.language_code or "en").lower()
    return "ru" if code.startswith("ru") else "en"


def _normalize_style_choice(text: str) -> str:
    t = text.strip().lower()
    if any(k in t for k in ("1", "эмо", "эмоцион", "emotional")):
        return "emotional"
    if any(k in t for k in ("2", "строг", "formal", "strict")):
        return "strict"
    if any(k in t for k in ("3", "весел", "fun", "развлек")):
        return "fun"
    return "emotional"


@dp.message(F.text)
async def handle_message(message: types.Message):
    user_input = message.text or ""
    user_id = message.from_user.id

    state = get_user_state(user_id)
    print("=== STATE DEBUG: current user state ===")
    print(state)
    print("=== END STATE DEBUG ===")

    # Новый пользователь — приветствие и выбор стиля
    if state.stage == "NEW_USER":
        lang = _detect_language(message, user_input)
        set_language(user_id, lang)

        if lang == "ru":
            await message.answer(
                "Привет! Я твой виртуальный гид по Гюмри.\n\n"
                "Сначала выберем стиль общения:\n"
                "1 — эмоциональный\n"
                "2 — строгий\n"
                "3 — развлекающий\n\n"
                "Напиши номер или опиши, как тебе комфортнее 🙂"
            )
        else:
            await message.answer(
                "Hi! I'm your virtual guide in Gyumri.\n\n"
                "First, let's choose the communication style:\n"
                "1 — emotional\n"
                "2 — strict / formal\n"
                "3 — fun / entertaining\n\n"
                "Type the number or briefly describe your preferred style 🙂"
            )

        update_stage(user_id, "ASK_STYLE")
        return

    # Пользователь выбирает стиль
    if state.stage == "ASK_STYLE":
        style = _normalize_style_choice(user_input)
        set_style(user_id, style)

        if state.language == "ru":
            await message.answer(
                "Отлично, запомнил стиль общения.\n\n"
                "Теперь расскажи, пожалуйста, что бы ты хотел(а) увидеть или попробовать в Гюмри "
                "и сколько у тебя примерно есть времени (в часах/днях)."
            )
        else:
            await message.answer(
                "Great, I've saved your preferred style.\n\n"
                "Now please tell me what you would like to see or try in Gyumri "
                "and roughly how much time you have (hours/days)."
            )

        update_stage(user_id, "ASK_PREFERENCES")
        return

    # Пользователь описывает пожелания и ограничения по времени
    if state.stage == "ASK_PREFERENCES":
        set_raw_preferences(user_id, user_input)

        # По требованиям MVP: геолокация обязательна для построения маршрута.
        if state.language == "ru":
            await message.answer(
                "Спасибо! Я запомнил твои пожелания.\n\n"
                "Чтобы я мог построить маршрут от твоей текущей точки, пожалуйста, "
                "отправь геолокацию через кнопку 📎 → «Геопозиция».\n\n"
                "Без геолокации я не смогу предложить маршрут."
            )
        else:
            await message.answer(
                "Thank you! I've saved your preferences.\n\n"
                "To build a route from your current position, please send your location "
                "via the 📎 → “Location” button.\n\n"
                "Without your location I can't suggest a route."
            )

        update_stage(user_id, "ASK_LOCATION_REQUIRED")
        return

    # Ждём геолокацию, без неё не переходим в основной режим
    if state.stage == "ASK_LOCATION_REQUIRED":
        if state.language == "ru":
            await message.answer(
                "Пожалуйста, отправь геолокацию через 📎 → «Геопозиция», "
                "и я подберу места и маршрут рядом с тобой."
            )
        else:
            await message.answer(
                "Please send your location via 📎 → “Location”, and I will suggest places and a route nearby."
            )
        return

    # Основной режим общения: учитываем язык, стиль и базовые пожелания
    print(f"[{state.language}/{state.style}] Пользователь {user_id}: {user_input}")
    reply_text = generate_reply(user_id=user_id, user_input=user_input, user_state=state)
    print(f"Ответ от модели: {reply_text}")

    await message.answer(reply_text)


@dp.message(F.location)
async def handle_location(message: types.Message):
    """
    Обработка геолокации пользователя: сохраняем в состоянии и предлагаем ближайшие места.
    """
    user_id = message.from_user.id
    state = get_user_state(user_id)
    print("=== STATE DEBUG: before location update ===")
    print(state)

    loc = message.location
    if loc is None:
        return

    lat = loc.latitude
    lon = loc.longitude
    set_location(user_id, lat, lon)

    # Если мы ждали гео как обязательный шаг — переходим дальше.
    # Следующий этап (программы/маршрут) добавим отдельно; пока переводим в общий режим.
    if state.stage == "ASK_LOCATION_REQUIRED":
        update_stage(user_id, "FREE_CHAT")

    state = get_user_state(user_id)
    print("=== STATE DEBUG: after location update ===")
    print(state)

    nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=5)
    print(f"=== LOCATION DEBUG: found {len(nearby)} nearby places ===")
    text = format_places_for_user(nearby, language=state.language)

    await message.answer(text)

    # Подсказка, что можно делать дальше
    if state.language == "ru":
        await message.answer(
            "Отлично! Теперь можешь написать, что ты хочешь сделать дальше (например: "
            "«покажи маршрут на 2 часа», «где поесть рядом», «что рядом интересного?»)."
        )
    else:
        await message.answer(
            "Great! Now tell me what you'd like to do next (e.g. "
            "“build me a 2-hour route”, “places to eat nearby”, “what sights are around?”)."
        )


if __name__ == "__main__":
    dp.run_polling(bot)
