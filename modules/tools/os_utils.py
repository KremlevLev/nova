import datetime
import subprocess
import logging
import time
import pyautogui
import pyperclip
import webbrowser
import os

logger = logging.getLogger("Tools")

def get_current_time() -> str:
    """Возвращает текущее время и дату."""
    now = datetime.datetime.now()
    return now.strftime("Сегодня %d.%m.%Y, точное время %H:%M:%S")

def open_application(app_name: str) -> str:
    """Открывает базовые программы Windows."""
    app_name = app_name.lower().strip()
    
    # Простой словарь соответствий (потом можно расширить)
    apps = {
        "блокнот": "notepad.exe",
        "калькулятор": "calc.exe",
        "проводник": "explorer.exe"
    }
    
    executable = apps.get(app_name)
    if not executable:
        return f"Ошибка: Я пока не знаю, как открыть приложение '{app_name}'."
    
    try:
        subprocess.Popen(executable)
        logger.info(f"Успешно запущено: {executable}")
        return f"Приложение {app_name} успешно открыто."
    except Exception as e:
        logger.error(f"Ошибка запуска {executable}: {e}")
        return f"Произошла ошибка при запуске: {e}"
def type_text(text: str) -> str:
    """Вставляет текст в активное окно (через буфер обмена для поддержки русского языка)."""
    try:
        # Даем системе полсекунды, чтобы окно (например, Блокнот) успело сфокусироваться
        time.sleep(1.0)
        
        # Сохраняем то, что было в буфере обмена у пользователя (чтобы не затереть его личные данные)
        old_clipboard = pyperclip.paste()
        
        # Копируем текст от нейросети и вставляем через Ctrl+V
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        
        # Возвращаем старый буфер обмена на место
        time.sleep(0.1)
        pyperclip.copy(old_clipboard)
        
        logger.info("Текст успешно вставлен.")
        return "Текст успешно напечатан в активном окне."
    except Exception as e:
        logger.error(f"Ошибка при вводе текста: {e}")
        return f"Не удалось напечатать текст: {e}"
def change_volume(action: str) -> str:
    """Управляет громкостью системы (mute, up, down)."""
    action = action.lower().strip()
    
    if action in ["mute", "unmute", "выключить", "включить"]:
        pyautogui.press("volumemute")
        return "Звук переключен (включен/выключен)."
    elif action in ["up", "громче", "увеличить"]:
        # Нажимаем несколько раз для заметного эффекта
        for _ in range(5): 
            pyautogui.press("volumeup")
        return "Громкость увеличена."
    elif action in ["down", "тише", "уменьшить"]:
        for _ in range(5): 
            pyautogui.press("volumedown")
        return "Громкость уменьшена."
    else:
        return "Ошибка: Неизвестная команда для звука."

def open_website(url_or_query: str) -> str:
    """Открывает сайт по URL или ищет запрос в Google."""
    # Если это похоже на домен (есть точка и нет пробелов)
    if "." in url_or_query and " " not in url_or_query:
        if not url_or_query.startswith("http"):
            url_or_query = "https://" + url_or_query
        webbrowser.open(url_or_query)
        return f"Открыт сайт: {url_or_query}"
    else:
        # Иначе делаем поиск в Google
        search_url = f"https://www.google.com/search?q={url_or_query}"
        webbrowser.open(search_url)
        return f"Выполнен поиск в Google по запросу: '{url_or_query}'"

def execute_cmd_command(command: str) -> str:
    """Выполняет системную команду (например, выключение ПК, сон)."""
    # ЗДЕСЬ МЫ ДЕЛАЕМ БРОНЮ (Ограничиваем список разрешенных команд ради безопасности)
    allowed_commands = {
        "спящий режим": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "очистить корзину": "rd /s /q %systemdrive%\\$Recycle.bin"
    }
    
    cmd_to_run = allowed_commands.get(command.lower().strip())
    if cmd_to_run:
        os.system(cmd_to_run)
        return f"Системная команда '{command}' выполнена."
    else:
        return f"Ошибка: Команда '{command}' запрещена или не существует. Я не буду её выполнять."