from aiogram import Bot, Dispatcher, types
from langchain_openai import ChatOpenAI  # или Ollama для бесплатных
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

# Инициализация
load_dotenv()  # загружаем переменные из .env

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

if GROQ_API_KEY is None:
    raise RuntimeError("GROQ_API_KEY is not set in environment variables.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
# model = ChatOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

model = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile")

# Настройки контекста
MAX_TURNS_FOR_MODEL = 8          # сколько последних сообщений посылать в модель каждый раз
MAX_STORED_MESSAGES = 40         # после какого размера истории делать суммаризацию
KEEP_RECENT_AFTER_SUMMARY = 6    # сколько последних сообщений оставлять “как есть” рядом с саммари

# Простое хранилище истории диалогов в памяти процесса:
# ключ — Telegram user_id, значение — список сообщений (HumanMessage/AIMessage)
user_conversations = {}


def summarize_dialog(messages):
    """
    Делает короткую выжимку по длинному диалогу.
    Использует ту же модель, но только один раз на “пакет” старых сообщений.
    """
    if not messages:
        return ""

    summary_prompt = [
        HumanMessage(
            content=(
                "Сделай краткую выжимку предыдущего диалога между пользователем и ассистентом. "
                "Выдели факты, решения и важный контекст, который нужен для продолжения общения. "
                "Ответь одной связной текстовой выжимкой без лишних деталей."
            )
        )
    ] + messages

    summary_response = model.invoke(summary_prompt)
    return summary_response.content


@dp.message()
async def handle_message(message: types.Message):
    # 1. Берем текст от пользователя
    user_input = message.text
    user_id = message.from_user.id
    print(f"Получено сообщение от пользователя {user_id}: {user_input}")

    # 2. Достаем полную историю этого пользователя и добавляем текущее сообщение
    full_history = user_conversations.get(user_id, [])
    full_history = full_history + [HumanMessage(content=user_input)]

    # 3. Формируем укороченную историю, которую реально пошлём в модель
    history_for_model = full_history[-MAX_TURNS_FOR_MODEL:]

    # 4. Прогоняем через модель только последние сообщения
    response = model.invoke(history_for_model)
    full_history = full_history + [response]

    # 5. При необходимости — суммаризируем “старую” часть диалога, чтобы не росла бесконечно
    if len(full_history) > MAX_STORED_MESSAGES:
        old_part = full_history[:-KEEP_RECENT_AFTER_SUMMARY]
        recent_part = full_history[-KEEP_RECENT_AFTER_SUMMARY:]

        summary_text = summarize_dialog(old_part)
        summary_message = HumanMessage(
            content=f"Краткая выжимка предыдущего диалога:\n{summary_text}"
        )

        # В истории остаётся одно саммари + несколько последних “сырых” сообщений
        full_history = [summary_message] + recent_part

    # 6. Сохраняем обновлённую историю пользователя
    user_conversations[user_id] = full_history
    print(f"Ответ от модели: {response.content}")

    # 5. Отправляем ответ в чат
    await message.answer(response.content)

# Запуск бота
if __name__ == "__main__":
    dp.run_polling(bot)
