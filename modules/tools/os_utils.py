import datetime
import subprocess
import logging
import time
import pyautogui
import pyperclip
import webbrowser
import os
import psutil
import requests
from core.config import TAVILY_API_KEY

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
    
def get_system_status(metric: str) -> str:
    """Возвращает данные о загрузке системы (RAM, CPU, Батарея)."""
    metric = metric.lower()
    try:
        if "ram" in metric or "память" in metric:
            mem = psutil.virtual_memory()
            return f"Свободно оперативной памяти: {mem.available / (1024**3):.1f} ГБ из {mem.total / (1024**3):.1f} ГБ. Загрузка: {mem.percent}%"
        
        elif "cpu" in metric or "процессор" in metric:
            cpu = psutil.cpu_percent(interval=1)
            return f"Текущая загрузка процессора: {cpu}%."
            
        elif "battery" in metric or "батарея" in metric:
            battery = psutil.sensors_battery()
            if battery:
                plugged = "Да" if battery.power_plugged else "Нет"
                return f"Заряд батареи: {battery.percent}%. Подключено к сети: {plugged}."
            return "Батарея не обнаружена (вероятно, это стационарный ПК)."
            
        return "Неизвестная метрика. Запроси ram, cpu или battery."
    except Exception as e:
        return f"Ошибка при получении данных системы: {e}"

def search_web_tavily(query: str) -> str:
    """Умный поиск в интернете через Tavily API. Возвращает готовый текст ответа."""
    if not TAVILY_API_KEY:
        return "Ошибка: Ключ TAVILY_API_KEY не найден в настройках."
        
    logger.info(f"Ищу в интернете: {query}")
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3 # Берем 3 лучших источника
            },
            timeout=10
        )
        data = response.json()
        
        if "results" not in data:
            return "Ничего не найдено или произошла ошибка API."
            
        # Формируем красивый текстовый ответ для LLM
        results_text = "Вот что я нашел в интернете:\n"
        for i, res in enumerate(data['results'], 1):
            results_text += f"{i}. {res['title']}\nСодержание: {res['content']}\n\n"
            
        return results_text
    except Exception as e:
        return f"Ошибка при поиске в интернете: {e}"

def execute_cmd_command(command: str) -> str:
    """Выполняет системную команду с проверкой безопасности (Human-in-the-loop)."""
    command = command.lower().strip()
    
    # БЕЗОПАСНЫЕ КОМАНДЫ (выполняем сразу)
    safe_commands = {
        "спящий режим": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "заблокировать пк": "rundll32.exe user32.dll,LockWorkStation"
    }
    
    # ОПАСНЫЕ КОМАНДЫ (Требуют подтверждения человека)
    danger_commands = {
        "очистить корзину": "rd /s /q %systemdrive%\\$Recycle.bin",
        "выключить пк": "shutdown /s /t 0",
        "перезагрузить пк": "shutdown /r /t 0"
    }
    
    if command in safe_commands:
        os.system(safe_commands[command])
        return f"Безопасная системная команда '{command}' выполнена."
        
    elif command in danger_commands:
        # === HUMAN IN THE LOOP ===
        print(f"\n[⚠️ ВНИМАНИЕ] Джарвис хочет выполнить критическое действие: {command.upper()}")
        print('\a') # Системный звук (Beep) для привлечения внимания
        
        confirm = input("Разрешить? (y - да / n - нет): ")
        
        if confirm.lower() == 'y':
            os.system(danger_commands[command])
            return f"Действие '{command}' было подтверждено пользователем и выполнено."
        else:
            logger.warning("Действие заблокировано пользователем.")
            # Возвращаем LLM информацию об отказе, чтобы она извинилась
            return f"ОТКАЗ: Пользователь запретил выполнение команды '{command}'. Скажи 'Понял, отменяю действие'."
            
    return f"Ошибка: Команда '{command}' запрещена или не существует. Я не буду её выполнять."
# --- ДОПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ ДЛЯ НОВЫХ КАТЕГОРИЙ ---

def manage_media(action: str) -> str:
    """Управление музыкой и видео (пауза, следующий трек)."""
    action = action.lower()
    try:
        if action in ["play_pause", "пауза", "продолжить"]:
            pyautogui.press("playpause")
            return "Воспроизведение приостановлено/запущено."
        elif action in ["next", "следующий"]:
            pyautogui.press("nexttrack")
            return "Включен следующий трек."
        elif action in ["prev", "предыдущий"]:
            pyautogui.press("prevtrack")
            return "Включен предыдущий трек."
        return "Неизвестная медиа-команда."
    except Exception as e:
        return f"Ошибка управления медиа: {e}"

def manage_windows(action: str) -> str:
    """Управление окнами (свернуть все, закрыть текущее)."""
    try:
        if "minimize_all" in action or "свернуть" in action:
            pyautogui.hotkey('win', 'd')
            return "Все окна свернуты (показан рабочий стол)."
        elif "close_current" in action or "закрыть" in action:
            pyautogui.hotkey('alt', 'f4')
            return "Текущее активное окно закрыто."
        return "Неизвестная команда для окон."
    except Exception as e:
        return f"Ошибка управления окнами: {e}"

def create_quick_note(text: str) -> str:
    """Создает быструю заметку в файл на рабочем столе."""
    try:
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        note_path = os.path.join(desktop, "Джарвис_Заметки.txt")
        
        with open(note_path, "a", encoding="utf-8") as f:
            f.write(f"[{get_current_time()}] {text}\n")
            
        logger.info(f"Заметка сохранена: {text}")
        return "Заметка успешно сохранена на рабочем столе в файл 'Джарвис_Заметки.txt'."
    except Exception as e:
        return f"Не удалось сохранить заметку: {e}"

def set_timer(minutes: int) -> str:
    """Заглушка для таймера. Запускает системный писк через X минут."""
    # В идеале здесь нужен асинхронный таск, но пока сделаем простую команду Windows
    try:
        seconds = int(minutes) * 60
        # Запускаем фоновый процесс пинга, который висит X секунд, а потом издает звук
        os.system(f'start /B cmd /c "ping 127.0.0.1 -n {seconds} > nul & echo \x07 & echo \x07"')
        return f"Таймер на {minutes} минут успешно запущен."
    except Exception as e:
        return f"Ошибка при установке таймера: {e}"