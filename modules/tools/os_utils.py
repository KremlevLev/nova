import datetime
import subprocess
import logging
import time
import pyautogui
import pyperclip

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