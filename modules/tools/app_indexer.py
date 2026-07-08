import os
import logging
from typing import Optional, Tuple
from difflib import get_close_matches

logger = logging.getLogger("AppIndexer")

# Системные процессы Windows, у которых обычно нет ярлыков .lnk
SYSTEM_FALLBACKS = {
    "explorer": "explorer.exe",
    "проводник": "explorer.exe",
    "notepad": "notepad.exe",
    "блокнот": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "калькулятор": "calc.exe",
    "cmd": "cmd.exe",
    "консоль": "cmd.exe",
    "taskmgr": "taskmgr.exe",
    "диспетчер задач": "taskmgr.exe"
}

RUSSIAN_ALIASES = {
    "обсидиан": "obsidian", "обсидиана": "obsidian", "обсидиану": "obsidian", "обсядем": "obsidian",
    "дискорд": "discord", "дискорда": "discord", "дискорду": "discord",
    "хром": "google chrome", "хрома": "google chrome", "хрому": "google chrome", "гугл": "google chrome", "браузер": "google chrome",
    "стим": "steam", "стима": "steam", "стиму": "steam",
    "телеграм": "telegram", "телеграма": "telegram", "телеграму": "telegram", "телега": "telegram", "телегу": "telegram",
    "спотифай": "spotify", "спотифая": "spotify", "спотифаю": "spotify",
    "проводник": "explorer", "проводника": "explorer", "проводнику": "explorer",
    "блокнот": "notepad", "блокнота": "notepad", "блокноту": "notepad",
    "калькулятор": "calculator", "калькулятора": "calculator", "калькуле": "calculator",
    "вс код": "visual studio code", "код": "visual studio code"
}

class WindowsAppIndexer:
    def __init__(self):
        self.apps_cache = {}
        self.index_all_apps()

    def index_all_apps(self):
        user_start_menu = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        common_start_menu = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
        scan_paths = [user_start_menu, common_start_menu]
        
        for base_path in scan_paths:
            if not os.path.exists(base_path):
                continue
            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.endswith(".lnk"):
                        app_name = file[:-4].lower().strip()
                        full_path = os.path.join(root, file)
                        self.apps_cache[app_name] = full_path

        for ru_alias, target_en_name in RUSSIAN_ALIASES.items():
            if target_en_name in self.apps_cache:
                self.apps_cache[ru_alias] = self.apps_cache[target_en_name]
        logger.info(f"Индексация ПО завершена. Найдено ярлыков: {len(self.apps_cache)}")

    def find_app_path(self, query: str) -> Optional[str]:
        query_clean = query.lower().strip()
        
        # 1. Сначала проверяем жестко заданные системные утилиты
        if query_clean in SYSTEM_FALLBACKS:
            return SYSTEM_FALLBACKS[query_clean]
            
        # 2. Затем ищем по кэшу ярлыков .lnk
        if query_clean in self.apps_cache:
            return self.apps_cache[query_clean]
            
        matches = get_close_matches(query_clean, self.apps_cache.keys(), n=1, cutoff=0.55)
        if matches:
            return self.apps_cache[matches[0]]
        return None

    def launch_by_name(self, app_name: str) -> Tuple[bool, str]:
        path = self.find_app_path(app_name)
        if not path:
            return False, f"Приложение '{app_name}' не найдено."
        try:
            os.startfile(path)
            # Извлекаем чистое имя для озвучки (без расширения .exe)
            clean_name = os.path.basename(path)[:-4] if "." in path else path
            return True, f"Запускаю {clean_name}."
        except Exception as e:
            logger.error(f"Ошибка запуска {app_name}: {e}")
            return False, "Ошибка при запуске."