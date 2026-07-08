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
    (re.compile(r'\b(сделай|убавь|потише|тише|уменьши громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("down"), "Громкость уменьшена.")),
    (re.compile(r'\b(громче|прибавь|сделай громче|увеличь громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("up"), "Громкость увеличена.")),
    (re.compile(r'\b(выключи звук|включи звук|муте|мьют)\b', re.IGNORECASE), 
     lambda m: (change_volume("mute"), "Состояние звука изменено.")),
     
    (re.compile(r'\b(сколько времени|который час|время|точное время)\b', re.IGNORECASE), 
     lambda m: (None, get_current_time())),
     
    (re.compile(r'\bсверни\s+(все\s+)?окна\b', re.IGNORECASE), 
     lambda m: (manage_windows("minimize_all"), "Сворачиваю окна.")),
    (re.compile(r'\bзакрыв(ай|аем|ить)\s+окно\b', re.IGNORECASE), 
     lambda m: (manage_windows("close_current"), "Закрываю активное окно.")),
]

def check_instant_app_launch(user_text: str, app_launcher) -> tuple[bool, str]:
    """Мгновенно находит и запускает ярлык в обход нейросети"""
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
    for pattern, action in FAST_COMMAND_PATTERNS:
        match = pattern.search(user_text)
        if match:
            _, speech_text = action(match)
            return True, speech_text
    return False, ""