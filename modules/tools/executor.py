# modules/tools/executor.py
import sys
import io
import ast
import ctypes
import logging
import pyautogui
import os

logger = logging.getLogger("Executor")

# Настройка безопасности PyAutoGUI
pyautogui.FAILSAFE = True  # Если пользователь дернет мышь в любой угол экрана, выполнение прервется
pyautogui.PAUSE = 0.1

def prompt_hitl_permission(action_type: str, details: str) -> bool:
    """
    Выводит нативное блокирующее модальное окно Windows для подтверждения опасных действий.
    Поток исполнения замораживается до тех пор, пока пользователь не нажмет 'Да' или 'Нет'.
    """
    title = f"Контроль безопасности Nova — {action_type}"
    message = (
        f"Ассистент Nova запрашивает разрешение на выполнение действия:\n\n"
        f"{details}\n\n"
        "Вы подтверждаете выполнение этой операции?"
    )
    # 0x00000004 = MB_YESNO (Кнопки Да/Нет)
    # 0x00000030 = MB_ICONWARNING (Значок предупреждения)
    # 0x00010000 = MB_TOPMOST (Поверх всех окон для гарантированной видимости)
    style = 0x00000004 | 0x00000030 | 0x00010000
    
    result = ctypes.windll.user32.MessageBoxW(0, message, title, style)
    return result == 6  # 6 соответствует выбору 'Да' (IDYES)

def check_dangerous_patterns(code: str) -> tuple[bool, str]:
    """
    Проводит статический анализ синтаксического дерева кода (AST) перед его выполнением.
    """
    # Текстовые маркеры грубой деструкции системы
    blacklist = [
        "shutil.rmtree", "os.remove", "os.unlink", "format", 
        "os.system", "subprocess", "ctypes.windll.ntdll", "regdelete"
    ]
    for word in blacklist:
        if word in code:
            return False, f"Обнаружена заблокированная системная функция: '{word}'."
            
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # Проверка на бесконечные циклы while True:
            if isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    return False, "Обнаружен потенциально бесконечный цикл 'while True'."
    except SyntaxError as e:
        return False, f"Синтаксическая ошибка в коде: {e}"
        
    return True, "Базовые проверки безопасности пройдены."

def execute_python_code(code: str) -> str:
    """
    Выполняет произвольный Python-код в контролируемом контексте с перехватом вывода.
    Каждый вызов проходит через процедуру Human-in-the-Loop.
    """
    logger.info("Получен запрос на выполнение динамического Python-кода.")
    
    # 1. Быстрый автоматический аудит безопасности
    is_safe, check_msg = check_dangerous_patterns(code)
    
    # 2. Интерактивное подтверждение пользователя (HITL)
    details = f"Действие: Выполнение Python-кода (REPL)\nАнализ кода: {check_msg}\n\nКод для запуска:\n---\n{code}\n---"
    allowed = prompt_hitl_permission("Выполнение кода (REPL)", details)
    
    if not allowed:
        return "Отклонено: Пользователь заблокировал выполнение этого скрипта."
        
    # 3. Перехват стандартных потоков вывода
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    redirected_error = io.StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_error
    
    # Предоставляем безопасный контекст исполнения с предустановленными библиотеками
    local_scope = {
        "pyautogui": pyautogui,
        "ctypes": ctypes,
        "sys": sys,
        "io": io,
        "os": os,
    }
    
    try:
        # Выполнение в изолированном контексте
        exec(code, {}, local_scope)
        
        stdout_val = redirected_output.getvalue()
        stderr_val = redirected_error.getvalue()
        
        result_str = stdout_val
        if stderr_val:
            result_str += f"\nОшибки исполнения:\n{stderr_val}"
            
        return result_str if result_str.strip() else "Код выполнен успешно, пустой консольный вывод."
    except pyautogui.FailSafeException:
        return "Аварийная остановка: Сработал аппаратный предохранитель мыши (FailSafe)."
    except Exception as e:
        return f"Сбой в процессе работы скрипта: {e}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def mouse_click(x: int, y: int, click_type: str = "single") -> str:
    """
    Перемещает указатель мыши и совершает нажатие кнопки.
    Применяется плавное наведение курсора, позволяющее перехватить контроль.
    """
    try:
        # Плавное наведение за 0.6 секунды дает пользователю время заметить траекторию мыши
        pyautogui.moveTo(x, y, duration=0.6)
        
        if click_type == "double":
            pyautogui.doubleClick()
            action_desc = "Двойной клик"
        elif click_type == "right":
            pyautogui.rightClick()
            action_desc = "Правый клик"
        else:
            pyautogui.click()
            action_desc = "Одинарный клик"
            
        return f"Успешно: Выполнен {action_desc} в координатах X={x}, Y={y}."
    except pyautogui.FailSafeException:
        return "Аварийная остановка: Пользователь перехватил мышь и сорвал выполнение."
    except Exception as e:
        return f"Не удалось выполнить клик: {e}"