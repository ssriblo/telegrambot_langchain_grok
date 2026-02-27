import json
import math
import os
from typing import Any, Dict, List, Optional, Set, Tuple


_PLACES: List[Dict[str, Any]] = []


def _load_places() -> List[Dict[str, Any]]:
    global _PLACES
    if _PLACES:
        return _PLACES

    base_dir = os.path.dirname(__file__)

    # По умолчанию используем компактную MVP-базу с заполненными описаниями.
    # Можно переопределить через переменную окружения PLACES_JSON.
    env_path = os.environ.get("PLACES_JSON")
    candidates = [
        env_path,
        os.path.join(base_dir, "places_gyumri_mvp.json"),
        os.path.join(base_dir, "places_gyumri.json"),
    ]

    path = next((p for p in candidates if p and os.path.exists(p)), None)
    if path is None:
        raise FileNotFoundError(
            "Places database not found. Tried PLACES_JSON, places_gyumri_mvp.json, places_gyumri.json"
        )

    with open(path, "r", encoding="utf-8") as f:
        _PLACES = json.load(f)

    return _PLACES


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Приближённое расстояние между двумя точками на сфере в километрах.
    Для нашего города этого более чем достаточно.
    """
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def get_nearby_places(
    lat: float,
    lon: float,
    max_distance_km: float = 2.0,
    limit: int = 5,
    categories: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Возвращает ближайшие к пользователю места в пределах max_distance_km.
    """
    places = _load_places()

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for p in places:
        p_lat = p.get("lat")
        p_lon = p.get("lon")
        if p_lat is None or p_lon is None:
            continue

        if categories is not None:
            cat = p.get("category")
            if cat not in categories:
                continue

        dist = _haversine_km(lat, lon, float(p_lat), float(p_lon))
        if dist <= max_distance_km:
            scored.append((dist, p))

    scored.sort(key=lambda x: x[0])
    top = scored[:limit]

    result: List[Dict[str, Any]] = []
    for dist, p in top:
        copy = dict(p)
        copy["_distance_km"] = round(dist, 2)
        result.append(copy)

    return result


def get_place_by_id(place_id: str) -> Optional[Dict[str, Any]]:
    places = _load_places()
    for p in places:
        if str(p.get("id")) == str(place_id):
            return p
    return None


def format_places_for_user(places: List[Dict[str, Any]], language: str) -> str:
    """
    Делает человекочитаемый список мест с учётом языка.
    """
    if not places:
        if language == "ru":
            return "Рядом со тобой я не нашёл подходящих интересных мест в пределах заданного радиуса."
        return "I couldn't find interesting places nearby within the selected radius."

    lines: List[str] = []
    if language == "ru":
        lines.append("Вот несколько мест недалеко от тебя:")
    else:
        lines.append("Here are some places not far from you:")

    for idx, p in enumerate(places, start=1):
        name = p.get("name_ru") if language == "ru" else p.get("name_en")
        if not name:
            name = p.get("name_en") or p.get("name_ru") or "Unknown place"

        desc_key = "short_description_ru" if language == "ru" else "short_description_en"
        descr = p.get(desc_key) or ""
        dist = p.get("_distance_km", "?")

        if language == "ru":
            line = f"{idx}. {name} — примерно {dist} км от тебя.\n{descr}"
        else:
            line = f"{idx}. {name} — about {dist} km from you.\n{descr}"

        lines.append(line)

    return "\n\n".join(lines)

