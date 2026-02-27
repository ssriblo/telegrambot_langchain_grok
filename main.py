from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from data_gyumri import _haversine_km
import os

from llm import generate_reply
from state import (
    get_user_state,
    update_stage,
    set_language,
    set_style,
    set_raw_preferences,
    set_location,
    set_program,
    save_generated_programs,
    reset_user_state,
    mark_place_visited
)
from data_gyumri import get_nearby_places, format_places_for_user, get_place_by_id
from routing import generate_programs, format_program_options

load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def _detect_language(message: types.Message, text: str) -> str:
    if any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in text):
        return "ru"
    code = (message.from_user.language_code or "en").lower()
    return "ru" if code.startswith("ru") else "en"

def get_style_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Эмоциональный 🎭", callback_data="style_emotional")],
            [InlineKeyboardButton(text="Строгий 📝", callback_data="style_strict")],
            [InlineKeyboardButton(text="Развлекающий 🎉", callback_data="style_fun")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Emotional 🎭", callback_data="style_emotional")],
            [InlineKeyboardButton(text="Strict 📝", callback_data="style_strict")],
            [InlineKeyboardButton(text="Fun 🎉", callback_data="style_fun")]
        ])

def get_program_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏛 Классический", callback_data="prog_classic")],
            [InlineKeyboardButton(text="🍽 Фуд-тур", callback_data="prog_food")],
            [InlineKeyboardButton(text="🍃 Спокойная прогулка", callback_data="prog_chill")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏛 Classic", callback_data="prog_classic")],
            [InlineKeyboardButton(text="🍽 Food Tour", callback_data="prog_food")],
            [InlineKeyboardButton(text="🍃 Chill Walk", callback_data="prog_chill")]
        ])

def get_on_route_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Следующая точка", callback_data="route_next")],
            [InlineKeyboardButton(text="⏭ Пропустить точку", callback_data="route_skip")],
            [InlineKeyboardButton(text="🗺 Текущий маршрут", callback_data="route_show")],
            [InlineKeyboardButton(text="🍽 Где поесть рядом?", callback_data="route_eat_nearby")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Next Place", callback_data="route_next")],
            [InlineKeyboardButton(text="⏭ Skip Place", callback_data="route_skip")],
            [InlineKeyboardButton(text="🗺 Show Route", callback_data="route_show")],
            [InlineKeyboardButton(text="🍽 Eat Nearby", callback_data="route_eat_nearby")]
        ])


async def _send_place_navigation(
    target,  # message or callback_query.message
    place: dict,
    state,
    prefix_ru: str = "📍 Следующая точка:",
    prefix_en: str = "📍 Next stop:",
    show_route_kb: bool = True,
):
    """
    Sends a place card with:
    1. Text description + Google Maps link + distance from user
    2. Telegram venue (native map pin that opens in any navigator)
    3. On-route keyboard buttons
    """
    lang = state.language
    name = place.get(f"name_{lang}") or place.get("name_en") or "Unknown"
    desc = place.get(f"short_description_{lang}") or place.get("short_description_en") or ""
    lat = place.get("lat")
    lon = place.get("lon")

    prefix = prefix_ru if lang == "ru" else prefix_en

    # Build text with Google Maps link
    lines = [f"{prefix} <b>{name}</b>", ""]
    if desc:
        lines.append(desc)
        lines.append("")

    # Distance from user
    if state.last_location and lat and lon:
        user_lat, user_lon = state.last_location
        dist = _haversine_km(user_lat, user_lon, float(lat), float(lon))
        dist_text = f"~{dist:.1f} км от тебя" if lang == "ru" else f"~{dist:.1f} km from you"
        lines.append(f"📏 {dist_text}")

    # Google Maps link
    if lat and lon:
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=walking"
        link_label = "🗺 Открыть в Google Maps (пешком)" if lang == "ru" else "🗺 Open in Google Maps (walking)"
        lines.append(f'<a href="{maps_url}">{link_label}</a>')

    text = "\n".join(lines)
    kb = get_on_route_keyboard(lang) if show_route_kb else None
    await target.answer(text, parse_mode="HTML", reply_markup=kb)

    # Send Telegram venue (native navigable pin)
    if lat and lon:
        await target.answer_venue(
            latitude=float(lat),
            longitude=float(lon),
            title=name,
            address=desc[:100] if desc else name,
        )

@dp.message(Command("start", "reset"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    reset_user_state(user_id)
    # Simulate NEW_USER
    user_input = message.text or ""
    lang = _detect_language(message, user_input)
    set_language(user_id, lang)

    if lang == "ru":
        await message.answer(
            "Привет! Я твой виртуальный гид по Гюмри.\n\n"
            "Сначала выберем стиль общения:",
            reply_markup=get_style_keyboard(lang)
        )
    else:
        await message.answer(
            "Hi! I'm your virtual guide in Gyumri.\n\n"
            "First, let's choose the communication style:",
            reply_markup=get_style_keyboard(lang)
        )
    update_stage(user_id, "ASK_STYLE")

@dp.message(Command("style"))
async def cmd_style(message: types.Message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    text = "Выбери стиль общения:" if state.language == "ru" else "Choose communication style:"
    await message.answer(text, reply_markup=get_style_keyboard(state.language))

@dp.message(F.text)
async def handle_message(message: types.Message):
    user_input = message.text or ""
    if user_input.startswith("/"):
        return
        
    user_id = message.from_user.id
    state = get_user_state(user_id)

    if state.stage == "NEW_USER":
        await cmd_start(message)
        return

    if state.stage == "ASK_STYLE":
        msg = "Пожалуйста, выбери стиль кнопкой выше." if state.language == "ru" else "Please choose a style using the buttons above."
        await message.answer(msg)
        return

    if state.stage == "ASK_PREFERENCES":
        set_raw_preferences(user_id, user_input)
        if state.language == "ru":
            await message.answer(
                "Спасибо! Я запомнил твои пожелания.\n\n"
                "Чтобы я мог построить маршрут от твоей текущей точки, пожалуйста, "
                "отправь геолокацию через кнопку 📎 → «Геопозиция»."
            )
        else:
            await message.answer(
                "Thank you! I've saved your preferences.\n\n"
                "To build a route from your current position, please send your location "
                "via the 📎 → “Location” button."
            )
        update_stage(user_id, "ASK_LOCATION_REQUIRED")
        return

    if state.stage == "ASK_LOCATION_REQUIRED":
        msg = "Пожалуйста, отправь геолокацию." if state.language == "ru" else "Please send your location."
        await message.answer(msg)
        return

    if state.stage == "SHOW_PROGRAM_OPTIONS":
        msg = "Пожалуйста, выбери маршрут кнопками." if state.language == "ru" else "Please choose a route with the buttons."
        await message.answer(msg)
        return

    # Free chat or On Route
    reply_text = generate_reply(user_id=user_id, user_input=user_input, user_state=state)
    
    if state.stage == "ON_ROUTE":
        await message.answer(reply_text, reply_markup=get_on_route_keyboard(state.language))
    else:
        await message.answer(reply_text)

@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    state = get_user_state(user_id)
    data = callback_query.data

    if data.startswith("style_"):
        style = data.split("_")[1]
        set_style(user_id, style)
        
        await callback_query.message.edit_reply_markup(reply_markup=None)
        if state.stage == "ASK_STYLE":
            if state.language == "ru":
                await callback_query.message.answer(
                    "Отлично, стиль сохранен!\n"
                    "Расскажи, что бы ты хотел увидеть в Гюмри и сколько у тебя времени?"
                )
            else:
                await callback_query.message.answer(
                    "Great, style saved!\n"
                    "Tell me what you'd like to see in Gyumri and how much time you have?"
                )
            update_stage(user_id, "ASK_PREFERENCES")
        else:
            msg = "Стиль изменен!" if state.language == "ru" else "Style changed!"
            await callback_query.answer(msg)
            
    elif data.startswith("prog_"):
        prog_id = data.split("_")[1]
        set_program(user_id, prog_id)
        update_stage(user_id, "ON_ROUTE")
        
        await callback_query.message.edit_reply_markup(reply_markup=None)
        msg = "Маршрут выбран! Погнали!" if state.language == "ru" else "Route selected! Let's go!"
        await callback_query.answer(msg)
        
        state = get_user_state(user_id)
        if state.current_route:
            first_place_id = state.current_route[0]
            place = get_place_by_id(first_place_id)
            if place:
                await _send_place_navigation(
                    callback_query.message, place, state,
                    prefix_ru="📍 Первая точка:",
                    prefix_en="📍 First stop:",
                )
    
    elif data.startswith("route_"):
        action = data.split("_", 1)[1]
        if action == "next" or action == "skip":
            if state.current_route:
                visited_id = state.current_route.pop(0)
                if action == "next":
                    mark_place_visited(user_id, visited_id)
                
            if state.current_route:
                next_place_id = state.current_route[0]
                place = get_place_by_id(next_place_id)
                if place:
                    await _send_place_navigation(callback_query.message, place, state)
            else:
                text = "🎉 Маршрут закончен!" if state.language == "ru" else "🎉 Route finished!"
                update_stage(user_id, "FREE_CHAT")
                await callback_query.message.answer(text)
                
        elif action == "show":
            if not state.current_route:
                text = "Маршрут пуст." if state.language == "ru" else "Route is empty."
            else:
                names = []
                for pid in state.current_route:
                    p = get_place_by_id(pid)
                    if p:
                        names.append(p.get(f"name_{state.language}") or p.get("name_en") or "Unknown")
                text = "🗺 Осталось посетить:\n" + "\n".join([f"- {n}" for n in names]) if state.language == "ru" else "🗺 Left to visit:\n" + "\n".join([f"- {n}" for n in names])
            await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))
            
        elif action == "eat_nearby":
            if state.last_location:
                lat, lon = state.last_location
                nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=3, categories={"food"})
                if nearby:
                    text = format_places_for_user(nearby, state.language)
                else:
                    text = "Еды рядом не найдено." if state.language == "ru" else "No food found nearby."
            else:
                text = "Нужна геопозиция." if state.language == "ru" else "Location needed."
            await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))
            
    await callback_query.answer()

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    state = get_user_state(user_id)
    loc = message.location
    if loc is None:
        return

    lat = loc.latitude
    lon = loc.longitude
    set_location(user_id, lat, lon)

    if state.stage == "ASK_LOCATION_REQUIRED":
        update_stage(user_id, "SHOW_PROGRAM_OPTIONS")
        target_hours = 4.0 # later parse from text if needed
        programs = generate_programs(lat, lon, time_hours=target_hours)
        
        programs_ids = {
            prog_id: [p["id"] for p in places] 
            for prog_id, places in programs.items()
        }
        save_generated_programs(user_id, programs_ids)
        
        text = format_program_options(programs, language=state.language)
        await message.answer(text, reply_markup=get_program_keyboard(state.language))
    else:
        nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=5)
        text = format_places_for_user(nearby, language=state.language)
        if state.stage == "ON_ROUTE":
            await message.answer(text, reply_markup=get_on_route_keyboard(state.language))
        else:
            await message.answer(text)

if __name__ == "__main__":
    dp.run_polling(bot)
