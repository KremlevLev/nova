# modules/tools/app_indexer.py
import os
import logging
from typing import Optional, Tuple
from difflib import get_close_matches

logger = logging.getLogger("AppIndexer")

# Расширенный падежный словарь сопоставления русской речи с ярлыками
RUSSIAN_ALIASES = {
    # Obsidian
    "обсидиан": "obsidian",
    "обсидиана": "obsidian",
    "обсидиану": "obsidian",
    "обсядем": "obsidian", # Фонетическая автокоррекция вашей записи
    
    # Discord
    "дискорд": "discord",
    "дискорда": "discord",
    "дискорду": "discord",
    
    # Chrome
    "хром": "google chrome",
    "хрома": "google chrome",
    "хрому": "google chrome",
    "гугл": "google chrome",
    "браузер": "google chrome",
    
    # Steam
    "стим": "steam",
    "стима": "steam",
    "стиму": "steam",
    
    # Telegram
    "телеграм": "telegram",
    "телеграма": "telegram",
    "телеграму": "telegram",
    "телега": "telegram",
    "телегу": "telegram",
    
    # Spotify
    "спотифай": "spotify",
    "спотифая": "spotify",
    "спотифаю": "spotify",
    
    # Explorer (Проводник)
    "проводник": "explorer",
    "проводника": "explorer",
    "проводнику": "explorer",
    
    # Notepad (Блокнот)
    "блокнот": "notepad",
    "блокнота": "notepad",
    "блокноту": "notepad",
    
    # Calculator
    "калькулятор": "calculator",
    "калькулятора": "calculator",
    "калькуле": "calculator",
    
    # VS Code
    "вс код": "visual studio code",
    "код": "visual studio code"
}

class WindowsAppIndexer:
    def __init__(self):
        self.apps_cache = {}  # {lower_name: full_path_to_lnk}
        self.index_all_apps()

    def index_all_apps(self):
        """Сканирует папки меню 'Пуск' Windows на наличие ярлыков (.lnk)"""
        user_start_menu = os.path.join(
            os.environ['USERPROFILE'], 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs'
        )
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

        # Добавляем русскоязычные синонимы со склонениями в кэш
        for ru_alias, target_en_name in RUSSIAN_ALIASES.items():
            if target_en_name in self.apps_cache:
                self.apps_cache[ru_alias] = self.apps_cache[target_en_name]

        logger.info(f"Индексация ПО завершена. Найдено ярлыков: {len(self.apps_cache)}")

    def find_app_path(self, query: str) -> Optional[str]:
        """Ищет ярлык в кэше с использованием нечеткого поиска"""
        query_clean = query.lower().strip()
        
        if query_clean in self.apps_cache:
            return self.apps_cache[query_clean]
            
        matches = get_close_matches(query_clean, self.apps_cache.keys(), n=1, cutoff=0.55)
        if matches:
            matched_name = matches[0]
            logger.info(f"Нечеткое совпадение: '{query}' -> '{matched_name}'")
            return self.apps_cache[matched_name]
            
        return None

    def launch_by_name(self, app_name: str) -> Tuple[bool, str]:
        path = self.find_app_path(app_name)
        if not path:
            return False, f"Приложение '{app_name}' не найдено."
            
        try:
            os.startfile(path)
            clean_name = os.path.basename(path)[:-4]
            return True, f"Запускаю {clean_name}."
        except Exception as e:
            logger.error(f"Ошибка запуска {app_name}: {e}")
            return False, "Ошибка при запуске."