# modules/brain/bypass.py
import re
from modules.tools.os_utils import change_volume, close_application, get_current_time, manage_windows

LAUNCH_VERBS = [
    "запусти", "запустить", "запускай", "запускаю", "запустил",
    "открой", "открыть", "открывай", "открываю", "открыл",
    "включи", "включить", "включай", "включаю", "включил", "запуск"
]

CLOSE_VERBS = [
    "выключи", "выключить", "выключай", "выключаю", "выключил",
    "закрой", "закрыть", "закрывай", "закрываю", "закрыл",
    "прибей", "прибить", "убей", "убить", "заверши", "завершить"
]

# Быстрый Regex Bypass (время, системная громкость, окна)
FAST_COMMAND_PATTERNS = [
    # 1. Изменение громкости на конкретное число (например, "звук на 40", "громкость 80")
    (re.compile(r'\b(?:установи|сделай|поставь)?\s*(?:громкость|звук)\s*(?:на\s+)?(\d+)\b', re.IGNORECASE),
     lambda m: (change_volume(m.group(1)), f"Громкость установлена на {m.group(1)}%.")),
     
    # 2. Относительное изменение громкости
    (re.compile(r'\b(сделай|убавь|потише|тише|уменьши громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("down"), "Громкость уменьшена.")),
    (re.compile(r'\b(громче|прибавь|сделай громче|увеличь громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("up"), "Громкость увеличена.")),
    (re.compile(r'\b(выключи звук|включи звук|муте|мьют)\b', re.IGNORECASE), 
     lambda m: (change_volume("mute"), "Состояние звука изменено.")),
     
    # 3. Точное время
    (re.compile(r'\b(сколько времени|который час|время|точное время)\b', re.IGNORECASE), 
     lambda m: (None, get_current_time())),
     
    # 4. Управление окнами
    (re.compile(r'\bсверни\s+(все\s+)?окна\b', re.IGNORECASE), 
     lambda m: (manage_windows("minimize_all"), "Сворачиваю окна.")),
    (re.compile(r'\bзакрыв(ай|аем|ить)\s+окно\b', re.IGNORECASE), 
     lambda m: (manage_windows("close_current"), "Закрываю активное окно.")),
]

def check_instant_app_launch(user_text: str, app_launcher) -> tuple[bool, str]:
    """Мгновенно находит и запускает ярлык в обход нейросети"""
    if is_complex_request(user_text):
        return False, ""
    text_clean = user_text.lower().strip()
    for verb in LAUNCH_VERBS:
        pattern = rf'\b{verb}\s+(.+)'
        match = re.search(pattern, text_clean)
        if match:
            extracted_app_name = match.group(1).strip().rstrip(".!?")
            success, message = app_launcher.launch_by_name(extracted_app_name)
            if success:
                return True, message
    return False, ""

def check_instant_app_close(user_text: str) -> tuple[bool, str]:
    """Мгновенно находит процесс программы и завершает его локально за 5 мс"""
    if is_complex_request(user_text):
        return False, ""
    text_clean = user_text.lower().strip()
    for verb in CLOSE_VERBS:
        pattern = rf'\b{verb}\s+(.+)'
        match = re.search(pattern, text_clean)
        if match:
            extracted_app_name = match.group(1).strip().rstrip(".!?")
            message = close_application(extracted_app_name)
            if "не найдено" not in message:
                return True, message
    return False, ""

def check_fast_commands(user_text: str) -> tuple[bool, str]:
    """Проверяет фразы на соответствие быстрым системным паттернам"""
    if is_complex_request(user_text):
        return False, ""
    for pattern, action in FAST_COMMAND_PATTERNS:
        match = pattern.search(user_text)
        if match:
            _, speech_text = action(match)
            return True, speech_text
    return False, ""

def is_complex_request(user_text: str) -> bool:
    """
    Проверяет, содержит ли фраза составные команды.
    Если да — возвращает True, заставляя систему передать управление LLM.
    """
    text = user_text.lower().strip()
    # Если в запросе есть связующие союзы или знаки препинания
    complex_markers = [",", " и потом", " а потом", " затем", " после чего", " а также"]
    if any(marker in text for marker in complex_markers):
        return True
        
    # Считаем количество глаголов действий во фразе
    all_verbs = LAUNCH_VERBS + CLOSE_VERBS + ["сделай", "поставь", "установи", "сверни", "закрой"]
    verb_count = sum(1 for verb in all_verbs if f" {verb} " in f" {text} ")
    if verb_count > 1:
        return True
        
    return False

def determine_model_by_complexity(user_text: str, has_image: bool, needs_tools: bool) -> str:
    """
    Анализирует запрос и выбирает оптимальную по соотношению скорость/интеллект модель.
    """
    from core.config import MODEL_CV_BASE, MODEL_BASIC_TOOLS, MODEL_COMPLEX_TOOLS
    
    # Уровень 1: Базовые вопросы, обычный чат или анализ экрана (CV) -> Llama 4 Scout
    if has_image or not needs_tools:
        return MODEL_CV_BASE
        
    # Уровень 3: Многоступенчатый тул-коллинг (сложные составные запросы) -> GPT OSS 120B
    if is_complex_request(user_text):
        return MODEL_COMPLEX_TOOLS
        
    # Уровень 2: Базовый одиночный тул-коллинг -> GPT OSS 20B
    return MODEL_BASIC_TOOLS