import os
from typing import Dict, List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq


load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise RuntimeError("GROQ_API_KEY is not set in environment variables.")


# Инициализация модели
model = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile")


# Настройки контекста
MAX_TURNS_FOR_MODEL = 8          # сколько последних сообщений посылать в модель каждый раз
MAX_STORED_MESSAGES = 40         # после какого размера истории делать суммаризацию
KEEP_RECENT_AFTER_SUMMARY = 6    # сколько последних сообщений оставлять “как есть” рядом с саммари


# Хранилище истории диалогов в памяти процесса:
# ключ — user_id, значение — список сообщений (HumanMessage/AIMessage)
_user_conversations: Dict[int, List] = {}


def summarize_dialog(messages):
    """
    Делает краткую выжимку по длинному диалогу.
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


def generate_reply(user_id: int, user_input: str) -> str:
    """
    Обновляет историю диалога пользователя и возвращает текст ответа модели.
    """
    # 1. Достаем полную историю этого пользователя и добавляем текущее сообщение
    full_history = _user_conversations.get(user_id, [])
    full_history = full_history + [HumanMessage(content=user_input)]

    # 2. Формируем укороченную историю, которую реально пошлём в модель
    history_for_model = full_history[-MAX_TURNS_FOR_MODEL:]

    # 3. Прогоняем через модель только последние сообщения
    response = model.invoke(history_for_model)
    full_history = full_history + [response]

    # 4. При необходимости — суммаризируем “старую” часть диалога, чтобы не росла бесконечно
    if len(full_history) > MAX_STORED_MESSAGES:
        old_part = full_history[:-KEEP_RECENT_AFTER_SUMMARY]
        recent_part = full_history[-KEEP_RECENT_AFTER_SUMMARY:]

        summary_text = summarize_dialog(old_part)
        summary_message = HumanMessage(
            content=f"Краткая выжимка предыдущего диалога:\n{summary_text}"
        )

        # В истории остаётся одно саммари + несколько последних “сырых” сообщений
        full_history = [summary_message] + recent_part

    # 5. Сохраняем обновлённую историю пользователя
    _user_conversations[user_id] = full_history

    return response.content

