from typing import Dict, List, Any
from data_gyumri import get_nearby_places, _load_places

def generate_programs(lat: float, lon: float, time_hours: float = 4.0) -> Dict[str, List[Dict[str, Any]]]:
    """
    Генерирует 3 варианта программы тура (Classic, Food, Chill walk).
    Возвращает словарь { program_id: [place_dict, ...] }
    """
    # Определяем сколько мест включить в маршрут на основе времени.
    # Допустим: 1 место ~ 45 минут + время на дорогу.
    target_places_count = max(2, int((time_hours * 60) / 60))

    # Вытягиваем места поблизости с бОльшим радиусом (чтобы было из чего строить маршрут)
    nearby_all = get_nearby_places(lat, lon, max_distance_km=10.0, limit=50)

    programs = {
        "classic": [],
        "food": [],
        "chill": []
    }

    # 1. Classic (Архитектура, Музеи, Достопримечательности)
    classic_candidates = [p for p in nearby_all if p.get("category") in ("sight", "museum", "historic_architecture")]
    # Берём ближе к старту, limit by time
    programs["classic"] = classic_candidates[:target_places_count + 1]

    # 2. Food (Упор на еду + 1-2 достопримечательности для прогулки)
    food_candidates = [p for p in nearby_all if p.get("category") == "food"]
    food_program = []
    if food_candidates:
        food_program.append(food_candidates[0]) # Start with food or have food near start
    
    # Добавим немного classic
    if len(classic_candidates) > 0:
        food_program.append(classic_candidates[0])
    if len(food_candidates) > 1:
        food_program.append(food_candidates[1])
    if len(classic_candidates) > 1 and len(food_program) < target_places_count:
        food_program.append(classic_candidates[1])

    programs["food"] = food_program[:target_places_count]

    # 3. Chill walk (Рядом со стартом, медленный темп - меньше точек)
    chill_count = max(2, target_places_count - 1)
    chill_candidates = [p for p in nearby_all if p.get("_distance_km", 999) < 1.5]
    programs["chill"] = chill_candidates[:chill_count]

    return programs

def format_program_options(programs: Dict[str, List[Dict[str, Any]]], language: str = "ru") -> str:
    """
    Формирует текст с кратким описанием 3 маршрутов на выбор.
    """
    lines = []
    
    title_map = {
        "classic": {"ru": "🏛 Классический маршрут", "en": "🏛 Classic Route"},
        "food": {"ru": "🍽 Фуд-тур + Прогулка", "en": "🍽 Food Tour + Walk"},
        "chill": {"ru": "🍃 Спокойная прогулка (рядом)", "en": "🍃 Chill Walk (Nearby)"}
    }

    if language == "ru":
        lines.append("Я подготовил несколько вариантов программы специально для тебя:")
    else:
        lines.append("I have prepared several program options just for you:")

    lines.append("")

    for prog_id, places in programs.items():
        if not places:
            continue
        
        title = title_map.get(prog_id, {}).get(language, prog_id)
        
        # Получаем названия мест
        place_names = []
        for p in places:
            name = p.get(f"name_{language}") or p.get("name_en") or p.get("name_ru") or "Unknown"
            place_names.append(name)
        
        points_str = " -> ".join(place_names)
        
        lines.append(f"**{title}**")
        lines.append(f"Маршрут: {points_str}" if language == "ru" else f"Route: {points_str}")
        lines.append("")

    if language == "ru":
        lines.append("Какой вариант тебе больше по душе?")
    else:
        lines.append("Which option do you prefer?")

    return "\n".join(lines)
