# py -m main
import asyncio
import json
import traceback
import re
import winsound  
import keyboard  
from core.config import BASE_URL, DEFAULT_MODEL, SYSTEM_PROMPT
from modules.audio.tts import stop_speaking, reset_interrupt_flag
try:
    from core.config import LLAMA_BEST
except ImportError:
    LLAMA_BEST = DEFAULT_MODEL
from modules.tools.executor import execute_python_code, mouse_click, create_workspace_project
from modules.brain.llm import NovaLLM, extract_xml_tool_calls
from modules.tools.registry import ALL_TOOLS  # Импортируем плоский список инструментов
from modules.tools.os_utils import (
    get_current_time, open_application, close_application, type_text, 
    change_volume, open_website, execute_cmd_command, 
    get_system_status, search_web_tavily,
    manage_media, manage_windows, create_quick_note, set_timer,
    control_smart_home, configure_assistant, take_screenshot, encode_image_base64,
    press_keyboard_combination, scrape_webpage, get_clipboard_content, set_clipboard_content, run_terminal_command
)

from modules.audio.stt import VoiceListener
from modules.audio.tts import (
    speak, speak_worker, clean_text_for_speech, 
    is_text_code_or_json, is_inside_xml_block
)
import sys
import socket

# Подключение локальной BM25 памяти, задач и индексатора
from modules.brain.memory import LocalMemory
from modules.tools.tasks import TaskScheduler, reminder_checker_worker
from modules.tools.app_indexer import WindowsAppIndexer

# Подключение перехватчиков (Bypasses)
from modules.brain.bypass import check_instant_app_launch, check_instant_app_close, check_fast_commands, determine_model_by_complexity

# Однопоточный сокет-замок от дубликатов процессов
try:
    _instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _instance_lock.bind(('127.0.0.1', 29485))
except OSError:
    print("\n[⚠️ КРИТИЧЕСКАЯ ОШИБКА]: Ассистент Nova уже запущен в другом окне!")
    sys.exit(1)

# --- ИНИЦИАЛИЗАЦИЯ ДВИЖКОВ (СИНГЛТОНЫ) ---
memory_engine = LocalMemory()  # Инициализация чистой BM25 памяти без весов
scheduler_engine = TaskScheduler()
app_launcher = WindowsAppIndexer()

# --- КАРТА СИСТЕМНЫХ ИНСТРУМЕНТОВ ---
AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
    "open_application": open_application,
    "close_application": close_application,

    "type_text": type_text,
    "change_volume": change_volume,
    "open_website": open_website,
    "execute_cmd_command": execute_cmd_command,

    "get_system_status": get_system_status,
    "search_web_tavily": search_web_tavily,
    "manage_media": manage_media,
    "manage_windows": manage_windows,

    "create_quick_note": create_quick_note,
    "set_timer": set_timer,
    "control_smart_home": control_smart_home,
    "configure_assistant": configure_assistant,
    
    "save_to_memory": lambda text: memory_engine.add_document(text) or "Запомнила.",
    "search_in_memory": lambda query: "\n".join([f"- {r['text']}" for r in memory_engine.search(query)]) or "Ничего не найдено.",
    "set_reminder": lambda time_str, message: scheduler_engine.add_reminder(time_str, message),
    "get_active_reminders": lambda: scheduler_engine.list_reminders(),
    
    "execute_python_code": execute_python_code,
    "mouse_click": mouse_click,
    "press_keyboard_combination": press_keyboard_combination,
    "create_workspace_project": create_workspace_project,

    "scrape_webpage": scrape_webpage,
    "get_clipboard_content": get_clipboard_content,
    "set_clipboard_content": set_clipboard_content,
    "run_terminal_command": run_terminal_command
}

keyboard.add_hotkey("esc", stop_speaking)
keyboard.add_hotkey("ctrl+shift+q", stop_speaking)

def clean_arguments_for_function(func, func_args: dict) -> dict:
    """
    Инспектирует сигнатуру функции и удаляет любые аргументы, 
    которые функция не способна принять. Предотвращает TypeError от ИИ.
    """
    import inspect
    try:
        sig = inspect.signature(func)
        # Если функция принимает произвольные именованные аргументы (**kwargs), возвращаем как есть
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_kwargs:
            return func_args
            
        # Фильтруем только те ключи, которые явно объявлены в сигнатуре
        cleaned_args = {}
        for k, v in func_args.items():
            if k in sig.parameters and k != "":
                cleaned_args[k] = v
        return cleaned_args
    except Exception:
        # В случае сбоя инспекции возвращаем исходные аргументы для стабильности
        return func_args

def should_pass_tools(request: str) -> bool:
    """Определяет, нужно ли передавать инструменты для оптимизации контекста коротких фраз"""
    clean = request.lower().strip().rstrip(".!?")
    # Простые фразы общения и вежливости не требуют загрузки описаний функций
    chat_phrases = {"привет", "пока", "как дела", "что делаешь", "спасибо", "круто", "отлично", "ясно", "понятно", "хаха"}
    if clean in chat_phrases or len(clean.split()) <= 1:
        return False
    return True

# --- ГЛАВНЫЙ ЦИКЛ ОРКЕСТРАЦИИ (MAIN LOOP) ---

async def main_loop():
    bot = NovaLLM(model=LLAMA_BEST)
    listener = VoiceListener()
    
    # === ЗАПУСК ВИЗУАЛЬНОГО ОВЕРЛЕЯ ===
    from modules.ui.overlay import start_overlay, update_status
    start_overlay()
    update_status("СПИТ")  
    
    loop = asyncio.get_running_loop()
    activation_event = asyncio.Event()
    is_active = False  
    HOTKEY = "ctrl+shift+space"
    
    def toggle_nova():
        nonlocal is_active
        is_active = not is_active
        if is_active:
            winsound.Beep(1200, 150)  
            print("\n[🎙️] Нова АКТИВИРОВАНА. Непрерывный слух включен...")
            update_status("СЛУШАЕТ") 
            loop.call_soon_threadsafe(activation_event.set)
        else:
            winsound.Beep(600, 150)   
            print(f"\n[💤] Нова уснула. Нажмите {HOTKEY.upper()} для пробуждения...")
            update_status("СПИТ")
            from modules.audio.tts import stop_speaking
            stop_speaking()
            
            for msg in bot.history:
                content = msg.get("content")
                if isinstance(content, list):
                    text_only = ""
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_only += item.get("text") or ""
                    msg["content"] = text_only
            
    keyboard.add_hotkey(HOTKEY, toggle_nova)
    speak(f"Нажмите {HOTKEY.upper()} чтобы активировать непрерывный слух.")
    
    tool_names = list(AVAILABLE_FUNCTIONS.keys())

    while True:
        try:
            if not is_active:
                await activation_event.wait()
                activation_event.clear()
                if not is_active:
                    continue  
            
            reset_interrupt_flag()  
            update_status("СЛУШАЕТ")
            
            user_request = listener.listen(should_abort=lambda: not is_active)
            
            if not is_active:
                continue
            if not user_request:
                continue

            if "отключайся" in user_request.lower() or "выключись" in user_request.lower():
                speak("Отключаю питание. До встречи.")
                keyboard.unhook_all()
                break

            if "усни" in user_request.lower() or "спи" in user_request.lower():
                speak("Ухожу в спящий режим. Зовите, когда понадоблюсь.")
                winsound.Beep(600, 150)
                is_active = False
                print(f"\n[💤] Нова ушла в спящий режим. Нажмите {HOTKEY.upper()} для пробуждения...")
                continue

            # 0.А. МГНОВЕННЫЙ ЗАПУСК ПО (ZERO-LLM BYPASS)
            is_launch, launch_speech = check_instant_app_launch(user_request, app_launcher)
            if is_launch:
                print(f"[⚡ Instant App Launch Match]: {launch_speech}")
                speak(launch_speech)
                update_status("СЛУШАЕТ")
                continue

            # 0.Б. МГНОВЕННОЕ ЗАКРЫТИЕ ПО (ZERO-LLM BYPASS)
            is_close, close_speech = check_instant_app_close(user_request)
            if is_close:
                print(f"[⚡ Instant App Close Match]: {close_speech}")
                speak(close_speech)
                update_status("СЛУШАЕТ")
                continue

            # 1. Быстрый Bypass по регулярным выражениям (звук, время, окна)
            is_fast, fast_response = check_fast_commands(user_request)
            if is_fast:
                print(f"[⚡ Regex Bypass Match]: {fast_response}")
                speak(fast_response)
                update_status("СЛУШАЕТ")
                continue

            # 2. Основной агентный цикл
            update_status("ДУМАЕТ")
            
            # Решаем, нужно ли грузить инструменты
            use_tools = should_pass_tools(user_request)
            print(f"\n[🧠 Мозг]: Режим обработки: {'Агент с инструментами' if use_tools else 'Простой чат'}")

            # --- CV ДЕТЕКТОР ЭКРАНА ---
            image_path = None
            vision_triggers = ["на экране", "экран", "посмотри", "что это", "видишь", "исправь", "что тут", "изображено"]

            if any(trigger in user_request.lower() for trigger in vision_triggers):
                active_window_triggers = ["окно", "активное", "программу", "программа", "вкладка", "вкладку"]
                capture_active = any(trigger in user_request.lower() for trigger in active_window_triggers)
                print(f"[📸] Обнаружен CV-запрос (Режим окна: {capture_active}). Делаю снимок...")
                image_path = take_screenshot(active_only=capture_active)
                
            if image_path:
                base64_image = encode_image_base64(image_path)
                user_msg_content = [
                    {"type": "text", "text": user_request},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
                print("[📸] Изображение успешно прикреплено к запросу.")
            else:
                user_msg_content = user_request

            bot.history.append({"role": "user", "content": user_msg_content})

            for step in range(3):
                system_instruction = SYSTEM_PROMPT
                messages = [{"role": "system", "content": system_instruction}] + bot.history
                
                # ДИНАМИЧЕСКИЙ ВЫБОР МОДЕЛИ НА ОСНОВЕ СЛОЖНОСТИ ЗАПРОСА
                has_image = image_path is not None
                selected_model = determine_model_by_complexity(
                    user_request, 
                    has_image=has_image, 
                    needs_tools=use_tools
                )
                
                # Вывод отладочной информации в консоль
                if step == 0:
                    print(f"[🧠 Роутер Сложности]: Выбрана модель {selected_model}")
                
                kwargs = {
                    "model": selected_model,  # <--- Модель подменяется динамически
                    "messages": messages,
                    "stream": True,
                }
                if use_tools:
                    kwargs["tools"] = ALL_TOOLS
                if "openrouter" in BASE_URL:
                    kwargs["extra_body"] = {"models": bot._fallback_array}

                print(f"[Nova]: Анализирует данные (Шаг {step+1})...")
                
                try:
                    response = await bot._safe_api_call(**kwargs)
                    
                    text_buffer = ""
                    tool_calls_data = {}
                    
                    speech_queue = asyncio.Queue()
                    speak_worker_task = asyncio.create_task(speak_worker(speech_queue))
                    
                    sentence_buffer = ""
                    sentence_end_pattern = re.compile(r'([^.!?\n]+[.!?\n]+)')
                    
                    async for chunk in response:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        
                        if delta.content:
                            content_piece = delta.content
                            text_buffer += content_piece
                            sentence_buffer += content_piece
                            
                            print(content_piece, end="", flush=True)
                            
                            if is_inside_xml_block(text_buffer, tool_names):
                                continue
                            
                            while True:
                                match = sentence_end_pattern.match(sentence_buffer)
                                if not match:
                                    if "\n" in sentence_buffer:
                                        parts = sentence_buffer.split("\n", 1)
                                        sentence = parts[0].strip()
                                        sentence_buffer = parts[1]
                                        if sentence:
                                            cleaned_s = clean_text_for_speech(sentence, tool_names)
                                            if cleaned_s and not is_text_code_or_json(cleaned_s):
                                                await speech_queue.put(cleaned_s)
                                        continue
                                    break
                                
                                sentence = match.group(0).strip()
                                sentence_buffer = sentence_buffer[match.end():]
                                if sentence:
                                    cleaned_s = clean_text_for_speech(sentence, tool_names)
                                    if cleaned_s and not is_text_code_or_json(cleaned_s):
                                        await speech_queue.put(cleaned_s)
                                    
                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_data:
                                    tool_calls_data[idx] = {
                                        "id": tc.id or "", "type": "function", "function": {"name": "", "arguments": ""}
                                    }
                                if tc.id:
                                    tool_calls_data[idx]["id"] = tc.id
                                if tc.function.name:
                                    tool_calls_data[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments

                    remainder = sentence_buffer.strip()
                    if remainder:
                        cleaned_r = clean_text_for_speech(remainder, tool_names)
                        if cleaned_r and not is_text_code_or_json(cleaned_r):
                            await speech_queue.put(cleaned_r)
                    
                    await speech_queue.put(None)
                    await speak_worker_task
                    print()
                    
                except Exception as step_error:
                    print(f"\n[⚠️ Сбой генерации на Шаге {step+1}]: {step_error}")
                    if "tool call validation" in str(step_error).lower():
                        speak("Модель попыталась использовать недоступное действие. Пожалуйста, повторите запрос иначе.")
                    else:
                        speak("Произошла ошибка при обработке ответа нейросети.")
                    break
                
                tool_calls = list(tool_calls_data.values()) if tool_calls_data else []
                xml_tool_calls = extract_xml_tool_calls(text_buffer, tool_names)
                
                if xml_tool_calls:
                    print(f"   [🔍 XML-Парсер]: Извлечено вызовов инструментов из текста: {len(xml_tool_calls)}")
                    tool_calls.extend(xml_tool_calls)
                
                assistant_msg = {"role": "assistant", "content": text_buffer}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                bot.history.append(assistant_msg)
                
                if tool_calls:
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        try:
                            func_args = json.loads(tool_call["function"]["arguments"]) if tool_call["function"]["arguments"] else {}
                        except Exception as je:
                            print(f"   [⚠️ Ошибка разбора аргументов JSON для {func_name}]: {je}")
                            func_args = {}
                            
                        func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                        
                        if func_to_call:
                            # БЕЗОПАСНАЯ ОЧИСТКА АРГУМЕНТОВ:
                            cleaned_args = clean_arguments_for_function(func_to_call, func_args)
                            print(f"   [⚙️ Инструмент запущен]: {func_name} {cleaned_args}")
                            
                            try:
                                result = func_to_call(**cleaned_args)
                            except Exception as run_err:
                                result = f"Ошибка при выполнении функции: {run_err}"
                        else:
                            print(f"   [⚙️ Инструмент не найден]: {func_name}")
                            result = "Ошибка: Данный инструмент недоступен."
                        
                        bot.history.append({
                            "role": "tool", "tool_call_id": tool_call["id"], "name": func_name, "content": str(result)
                        })
                    continue
                else:
                    break

        except Exception as e:
            print(f"[Критическая Ошибка в цикле]: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(asyncio.gather(
            main_loop(),
            reminder_checker_worker(scheduler_engine, speak)
        ))
    except KeyboardInterrupt:
        print("\nЗавершение работы ассистента.")