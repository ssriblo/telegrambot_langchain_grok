from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class UserPreferences:
    interests: List[str] = field(default_factory=list)
    time_available_hours: Optional[float] = None
    budget_level: Optional[str] = None  # "low" | "medium" | "high" | None


@dataclass
class UserState:
    user_id: int
    stage: str = "NEW_USER"
    style: str = "emotional"  # "emotional" | "strict" | "fun"
    language: str = "ru"      # "ru" | "en"
    preferences: UserPreferences = field(default_factory=UserPreferences)
    last_location: Optional[Tuple[float, float]] = None
    current_route: List[str] = field(default_factory=list)
    visited_places: List[str] = field(default_factory=list)
    history_summary: Optional[str] = None


_user_states: Dict[int, UserState] = {}


def get_user_state(user_id: int) -> UserState:
    state = _user_states.get(user_id)
    if state is None:
        state = UserState(user_id=user_id)
        _user_states[user_id] = state
    return state


def save_user_state(state: UserState) -> None:
    _user_states[state.user_id] = state


def update_stage(user_id: int, stage: str) -> None:
    state = get_user_state(user_id)
    state.stage = stage
    save_user_state(state)


def set_style(user_id: int, style: str) -> None:
    state = get_user_state(user_id)
    state.style = style
    save_user_state(state)


def set_language(user_id: int, language: str) -> None:
    state = get_user_state(user_id)
    state.language = language
    save_user_state(state)


def set_raw_preferences(user_id: int, text: str) -> None:
    """
    Черновой способ сохранить пожелания пользователя:
    всю фразу кладём в interests как один элемент.
    Потом это можно заменить на более структурированный парсинг.
    """
    state = get_user_state(user_id)
    state.preferences.interests = [text.strip()] if text.strip() else []
    save_user_state(state)


def set_location(user_id: int, lat: float, lon: float) -> None:
    state = get_user_state(user_id)
    state.last_location = (lat, lon)
    save_user_state(state)

