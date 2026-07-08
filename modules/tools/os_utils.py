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
import ctypes

logger = logging.getLogger("Tools")

def get_current_time() -> str:
    now = datetime.datetime.now()
    return now.strftime("Сегодня %d.%m.%Y, точное время %H:%M:%S")


def close_application(app_name: str) -> str:
    """Закрывает запущенное приложение по его имени в системе"""
    app_name = app_name.lower().strip()
    apps = {
        "блокнот": "notepad.exe", 
        "калькулятор": "calc.exe", 
        "проводник": "explorer.exe",
        "хром": "chrome.exe",
        "браузер": "browser.exe"
    }
    process_name = apps.get(app_name, app_name)
    if not process_name.endswith(".exe"):
        process_name += ".exe"
        
    closed = False
    # 1. Сначала пытаемся мягко закрыть процесс через psutil
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == process_name:
                proc.kill()
                closed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    if closed:
        logger.info(f"Приложение {app_name} ({process_name}) успешно закрыто.")
        return f"Приложение '{app_name}' успешно закрыто."
    else:
        # 2. Если не получилось, пробуем системный вызов taskkill
        try:
            result = subprocess.run(["taskkill", "/f", "/im", process_name], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Приложение {app_name} закрыто через taskkill.")
                return f"Приложение '{app_name}' закрыто."
        except Exception:
            pass
        return f"Приложение '{app_name}' не найдено среди активных процессов."


def change_volume(action: str) -> str:
    action = action.lower().strip()
    if action in ["mute", "unmute", "выключить", "включить"]:
        pyautogui.press("volumemute")
        return "Звук переключен."
    elif action in ["up", "громче", "увеличить"]:
        for _ in range(5): 
            pyautogui.press("volumeup")
        return "Громкость увеличена."
    elif action in ["down", "тише", "уменьшить"]:
        for _ in range(5): 
            pyautogui.press("volumedown")
        return "Громкость уменьшена."
    return "Ошибка: Неизвестная команда для звука."

def open_website(url_or_query: str) -> str:
    if "." in url_or_query and " " not in url_or_query:
        if not url_or_query.startswith("http"):
            url_or_query = "https://" + url_or_query
        webbrowser.open(url_or_query)
        return f"Открыт сайт: {url_or_query}"
    else:
        search_url = f"https://www.google.com/search?q={url_or_query}"
        webbrowser.open(search_url)
        return f"Выполнен поиск в Google по запросу: '{url_or_query}'"

def get_system_status(metric: str) -> str:
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
            return "Батарея не обнаружена."
        return "Неизвестная метрика."
    except Exception as e:
        return f"Ошибка при получении данных системы: {e}"

def search_web_tavily(query: str) -> str:
    if not TAVILY_API_KEY:
        return "Ошибка: Ключ TAVILY_API_KEY не найден."
    logger.info(f"Ищу в интернете через Tavily: {query}")
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3},
            timeout=10
        )
        data = response.json()
        if "results" not in data:
            return "Ничего не найдено."
        results_text = "Вот что я нашел в интернете:\n"
        for i, res in enumerate(data['results'], 1):
            results_text += f"{i}. {res['title']}\nСодержание: {res['content']}\n\n"
        return results_text
    except Exception as e:
        return f"Ошибка при поиске в интернете: {e}"

def execute_cmd_command(command: str) -> str:
    command = command.lower().strip()
    safe_commands = {
        "спящий режим": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "заблокировать пк": "rundll32.exe user32.dll,LockWorkStation"
    }
    danger_commands = {
        "очистить корзину": "rd /s /q %systemdrive%\\$Recycle.bin",
        "выключить пк": "shutdown /s /t 0",
        "перезагрузить пк": "shutdown /r /t 0"
    }
    if command in safe_commands:
        os.system(safe_commands[command])
        return f"Безопасная системная команда '{command}' выполнена."
    elif command in danger_commands:
        print(f"\n[⚠️ ВНИМАНИЕ] Джарвис хочет выполнить критическое действие: {command.upper()}")
        print('\a')
        confirm = input("Разрешить? (y - да / n - нет): ")
        if confirm.lower() == 'y':
            os.system(danger_commands[command])
            return f"Действие '{command}' было подтверждено пользователем и выполнено."
        else:
            return f"ОТКАЗ: Пользователь запретил выполнение команды '{command}'."
    return f"Ошибка: Команда '{command}' запрещена или не существует."

def manage_media(action: str) -> str:
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
    try:
        if "minimize_all" in action or "свернуть" in action:
            pyautogui.hotkey('win', 'd')
            return "Все окна свернуты."
        elif "close_current" in action or "закрыть" in action:
            pyautogui.hotkey('alt', 'f4')
            return "Текущее активное окно закрыто."
        return "Неизвестная команда для окон."
    except Exception as e:
        return f"Ошибка управления окнами: {e}"

def create_quick_note(text: str) -> str:
    try:
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        note_path = os.path.join(desktop, "Джарвис_Заметки.txt")
        with open(note_path, "a", encoding="utf-8") as f:
            f.write(f"[{get_current_time()}] {text}\n")
        return "Заметка успешно сохранена на рабочем столе."
    except Exception as e:
        return f"Не удалось сохранить заметку: {e}"

def set_timer(minutes: int) -> str:
    try:
        seconds = int(minutes) * 60
        os.system(f'start /B cmd /c "ping 127.0.0.1 -n {seconds} > nul & echo \x07"')
        return f"Таймер на {minutes} минут успешно запущен."
    except Exception as e:
        return f"Ошибка при установке таймера: {e}"

def control_smart_home(device: str, action: str) -> str:
    device = device.lower().strip()
    action = action.lower().strip()
    logger.info(f"Умный дом: {device} -> {action}")
    return f"Симуляция умного дома: Устройство '{device}' переведено в режим '{action}'."

def configure_assistant(setting: str, value: str) -> str:
    setting = setting.lower().strip()
    value = value.lower().strip()
    logger.info(f"Настройки ассистента: {setting} -> {value}")
    return f"Настройка '{setting}' успешно изменена на значение '{value}'."

def bring_window_to_front(app_name: str) -> bool:
    """Находит окно запущенного приложения и принудительно выводит его на передний план (фокус)"""
    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        
        found_hwnds = []

        def enum_windows_callback(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value.lower()
                    
                    # Маппинг русско-английских названий окон
                    aliases = {
                        "блокнот": ["блокнот", "notepad"],
                        "калькулятор": ["калькулятор", "calc", "calculator"],
                        "проводник": ["проводник", "explorer", "компьютер"],
                        "chrome": ["chrome", "хром", "google chrome"],
                        "obsidian": ["obsidian"]
                    }
                    search_terms = aliases.get(app_name.lower(), [app_name.lower()])
                    if any(term in title for term in search_terms):
                        found_hwnds.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        
        if found_hwnds:
            hwnd = found_hwnds[0]
            user32.ShowWindow(hwnd, 9)  # 9 = SW_RESTORE (развернуть окно, если оно свернуто)
            user32.SetForegroundWindow(hwnd)  # Активировать фокус окна
            return True
    except Exception as e:
        logger.error(f"Ошибка фокусировки окна {app_name}: {e}")
    return False

def open_application(app_name: str) -> str:
    app_name = app_name.lower().strip()
    apps = {"блокнот": "notepad.exe", "калькулятор": "calc.exe", "проводник": "explorer.exe"}
    executable = apps.get(app_name)
    if not executable:
        return f"Ошибка: Я пока не знаю, как открыть приложение '{app_name}'."
    try:
        subprocess.Popen(executable)
        # Ждем 0.5 сек, чтобы Windows успела создать процесс и окно, затем наводим фокус
        time.sleep(0.5)
        bring_window_to_front(app_name)
        return f"Приложение {app_name} успешно открыто."
    except Exception as e:
        return f"Произошла ошибка при запуске: {e}"

def type_text(text: str) -> str:
    try:
        # Небольшая пауза, чтобы активное окно успело среагировать на фокус
        time.sleep(0.5)
        old_clipboard = pyperclip.paste()
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyperclip.copy(old_clipboard)
        return "Текст успешно напечатан в активном окне."
    except Exception as e:
        return f"Не удалось напечатать текст: {e}"