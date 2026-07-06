# py -m main
import asyncio
import json
import traceback
import re
import time
from core.config import BASE_URL, LLAMA_BEST
from modules.brain.llm import NovaLLM
from modules.brain.router import get_intent
from modules.tools.registry import TOOL_REGISTRY
from modules.tools.os_utils import (
    get_current_time, open_application, close_application, type_text, 
    change_volume, open_website, execute_cmd_command, 
    get_system_status, search_web_tavily,
    manage_media, manage_windows, create_quick_note, set_timer,
    control_smart_home, configure_assistant
)
from modules.audio.stt import VoiceListener
from modules.audio.tts import speak

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
    "configure_assistant": configure_assistant
}

# --- ШАБЛОНЫ ДЛЯ БЫСТРОГО ОБХОДА (REGEX BYPASS) ---
FAST_COMMAND_PATTERNS = [
    (re.compile(r'\b(сделай|убавь|потише|тише|уменьши громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("down"), "Громкость уменьшена.")),
    (re.compile(r'\b(громче|прибавь|сделай громче|увеличь громкость)\b', re.IGNORECASE), 
     lambda m: (change_volume("up"), "Громкость увеличена.")),
    (re.compile(r'\b(выключи звук|включи звук|муте|мьют)\b', re.IGNORECASE), 
     lambda m: (change_volume("mute"), "Состояние звука изменено.")),
     
    (re.compile(r'\bоткрой\s+(блокнот|ноутпад)\b', re.IGNORECASE), 
     lambda m: (open_application("блокнот"), "Открываю блокнот.")),
    (re.compile(r'\bоткрой\s+(калькулятор|калк)\b', re.IGNORECASE), 
     lambda m: (open_application("калькулятор"), "Открываю калькулятор.")),
    (re.compile(r'\bоткрой\s+проводник\b', re.IGNORECASE), 
     lambda m: (open_application("проводник"), "Открываю проводник.")),
     
    (re.compile(r'\bзакрывай?\s+(блокнот|ноутпад)\b', re.IGNORECASE), 
     lambda m: (close_application("блокнот"), "Закрываю блокнот.")),
    (re.compile(r'\bзакрывай?\s+(калькулятор|калк)\b', re.IGNORECASE), 
     lambda m: (close_application("калькулятор"), "Закрываю калькулятор.")),
     
    (re.compile(r'\b(сколько времени|который час|время|точное время)\b', re.IGNORECASE), 
     lambda m: (None, get_current_time())),
     
    (re.compile(r'\bсверни\s+(все\s+)?окна\b', re.IGNORECASE), 
     lambda m: (manage_windows("minimize_all"), "Сворачиваю окна.")),
    (re.compile(r'\bзакрыв(ай|аем|ить)\s+окно\b', re.IGNORECASE), 
     lambda m: (manage_windows("close_current"), "Закрываю активное окно.")),
]

def check_fast_commands(user_text: str) -> tuple[bool, str]:
    for pattern, action in FAST_COMMAND_PATTERNS:
        match = pattern.search(user_text)
        if match:
            _, speech_text = action(match)
            return True, speech_text
    return False, ""

# --- УМНЫЙ XML/TEXT ФИЛЬТР И ДЕКОДЕР ---

def is_inside_xml_block(text: str) -> bool:
    """
    Проверяет, находится ли текущий конец стрима внутри открытого XML-тега инструмента.
    Это защищает от проговаривания недописанных технических команд обоих типов.
    """
    # 1. Формат Llama 3.1: <function=имя_функции>...</function>
    open_func_tags = text.count("<function=")
    close_func_tags = text.count("</function>")
    if open_func_tags > close_func_tags:
        return True
        
    # 2. Формат: <имя_функции>...</имя_функции>
    for func_name in AVAILABLE_FUNCTIONS.keys():
        open_count = text.count(f"<{func_name}>")
        close_count = text.count(f"</{func_name}>")
        if open_count > close_count:
            return True
            
    # 3. Проверка, если сам тег в процессе написания
    last_bracket = text.rfind("<")
    if last_bracket > text.rfind(">"):
        return True
    return False

def clean_text_for_speech(text: str) -> str:
    """Удаляет все XML-теги инструментов обоих форматов из голосового потока"""
    cleaned = text
    
    # 1. Удаляем формат <function=имя_функции>...</function>
    cleaned = re.sub(r'<function=\w+>.*?</function>', '', cleaned, flags=re.DOTALL)
    
    # 2. Удаляем формат <имя_функции>...</имя_функции>
    for func_name in AVAILABLE_FUNCTIONS.keys():
        pattern = re.compile(rf'<{func_name}>.*?</{func_name}>', re.DOTALL)
        cleaned = pattern.sub('', cleaned)
    
    # 3. Удаляем любые другие возможные одиночные XML/HTML теги
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    # Схлопываем лишние пробелы и переносы
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def add_tool_call_from_parsed(func_name: str, args_str: str, tool_calls_list: list):
    """Безопасный хелпер сборки и парсинга структуры вызова из регулярных выражений"""
    try:
        clean_args = args_str.strip()
        if clean_args.startswith("```"):
            clean_args = re.sub(r'^```(?:json)?\n', '', clean_args)
            clean_args = re.sub(r'\n```$', '', clean_args)
        
        arguments = json.loads(clean_args)
        
        call_id = f"xml_{func_name}_{int(time.time())}_{len(tool_calls_list)}"
        tool_calls_list.append({
            "id": call_id,
            "type": "function",
            "function": {
                "name": func_name,
                "arguments": json.dumps(arguments)
            }
        })
    except Exception as e:
        print(f"[Ошибка парсинга JSON в XML-инструменте {func_name}]: {e}")

def extract_xml_tool_calls(text: str) -> list[dict]:
    """Ищет в текстовом буфере теги вызова функций обоих форматов и переводит их в tool_calls"""
    tool_calls = []
    
    # 1. Формат Llama 3.1: <function=имя_функции>{аргументы}</function>
    pattern_llama = re.compile(r'<function=(\w+)>\s*(\{.*?\})\s*</function>', re.DOTALL)
    matches_llama = pattern_llama.findall(text)
    for func_name, args_str in matches_llama:
        if func_name in AVAILABLE_FUNCTIONS:
            add_tool_call_from_parsed(func_name, args_str, tool_calls)
            
    # 2. Стандартный формат: <имя_функции>{аргументы}</имя_функции>
    pattern_standard = re.compile(r'<(\w+)>\s*(\{.*?\})\s*</\1>', re.DOTALL)
    matches_standard = pattern_standard.findall(text)
    for func_name, args_str in matches_standard:
        if func_name != "function" and func_name in AVAILABLE_FUNCTIONS:
            add_tool_call_from_parsed(func_name, args_str, tool_calls)
            
    return tool_calls

# --- АСИНХРОННЫЙ ПЛЕЕР ПРЕДЛОЖЕНИЙ ---
async def speak_worker(queue: asyncio.Queue):
    """Фоновый воркер для последовательной озвучки готовых предложений"""
    while True:
        sentence = await queue.get()
        if sentence is None:
            queue.task_done()
            break
        try:
            await asyncio.to_thread(speak, sentence)
        except Exception as e:
            print(f"[Ошибка TTS воркера]: {e}")
        finally:
            queue.task_done()

async def main_loop():
    speak("Инициализация систем. Пожалуйста, подождите.")
    bot = NovaLLM(model=LLAMA_BEST)
    listener = VoiceListener()
    speak("Нова готова к работе. Я вас слушаю.")

    while True:
        try:
            user_request = listener.listen()
            if not user_request:
                continue

            if "отключайся" in user_request.lower() or "усни" in user_request.lower():
                speak("Отключаю питание. До встречи.")
                break

            # 1. Быстрый Bypass по регулярным выражениям (микросекундный отклик)
            is_fast, fast_response = check_fast_commands(user_request)
            if is_fast:
                print(f"[⚡ Regex Bypass Match]: {fast_response}")
                speak(fast_response)
                continue

            # 2. Основной агентный цикл
            intents = get_intent(user_request)
            primary_intent = intents[0]
            active_tools = TOOL_REGISTRY.get(primary_intent, [])
            
            print(f"\n[🧠 Роутер]: Выбрана категория '{primary_intent.upper()}'. Передано инструментов: {len(active_tools)}")

            bot.history.append({"role": "user", "content": user_request})

            for step in range(3):
                # Накладываем строгое системное ограничение, запрещая вызывать несуществующие инструменты
                system_instruction = (
                    "Ты Nova, ИИ-ассистент для Windows. "
                    "Тебе разрешено вызывать ТОЛЬКО те инструменты, которые предоставлены в текущем запросе (в параметре 'tools'). "
                    "Вызов любых других названий инструментов строго запрещен. Если ты выполнила действие, отвечаешь коротко."
                )
                messages = [{"role": "system", "content": system_instruction}] + bot.history
                
                kwargs = {
                    "model": bot.primary_model,
                    "messages": messages,
                    "stream": True,
                }
                if active_tools:
                    kwargs["tools"] = active_tools
                if "openrouter" in BASE_URL:
                    kwargs["extra_body"] = {"models": bot._fallback_array}

                print(f"[Nova]: Анализирует данные (Шаг {step+1})...")
                
                # Изолируем шаг генерации от критического падения в случае ошибки валидации API
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
                        
                        # Обработка текстового потока (включая сырые XML теги)
                        if delta.content:
                            content_piece = delta.content
                            text_buffer += content_piece
                            sentence_buffer += content_piece
                            
                            # Вывод в консоль в реальном времени
                            print(content_piece, end="", flush=True)
                            
                            # Если мы находимся внутри открытого XML-тега инструмента любого типа, приостанавливаем озвучку
                            if is_inside_xml_block(text_buffer):
                                continue
                            
                            # Нарезаем накопленный чистый текст на предложения
                            while True:
                                match = sentence_end_pattern.match(sentence_buffer)
                                if not match:
                                    if "\n" in sentence_buffer:
                                        parts = sentence_buffer.split("\n", 1)
                                        sentence = parts[0].strip()
                                        sentence_buffer = parts[1]
                                        if sentence:
                                            cleaned_s = clean_text_for_speech(sentence)
                                            if cleaned_s:
                                                await speech_queue.put(cleaned_s)
                                        continue
                                    break
                                
                                sentence = match.group(0).strip()
                                sentence_buffer = sentence_buffer[match.end():]
                                if sentence:
                                    cleaned_s = clean_text_for_speech(sentence)
                                    if cleaned_s:
                                        await speech_queue.put(cleaned_s)
                                    
                        # Обработка нативных tool_calls (если API-провайдер отдал их в структурированном виде)
                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_data:
                                    tool_calls_data[idx] = {
                                        "id": tc.id or "",
                                        "type": "function",
                                        "function": {
                                            "name": "",
                                            "arguments": ""
                                        }
                                    }
                                if tc.id:
                                    tool_calls_data[idx]["id"] = tc.id
                                if tc.function.name:
                                    tool_calls_data[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments

                    # Досылаем остатки предложений после окончания генерации
                    remainder = sentence_buffer.strip()
                    if remainder:
                        cleaned_r = clean_text_for_speech(remainder)
                        if cleaned_r:
                            await speech_queue.put(cleaned_r)
                    
                    # Завершаем воспроизведение
                    await speech_queue.put(None)
                    await speak_worker_task
                    
                    print()  # Перенос строки после завершения вывода генерации
                    
                except Exception as step_error:
                    print(f"\n[⚠️ Сбой генерации на Шаге {step+1}]: {step_error}")
                    if "tool call validation" in str(step_error).lower():
                        speak("Модель попыталась использовать недоступное действие. Пожалуйста, повторите запрос иначе.")
                    else:
                        speak("Произошла ошибка при обработке ответа нейросети.")
                    break # Прерываем шаги и возвращаемся в режим ожидания
                
                # Объединяем нативные вызовы и вызовы, извлеченные из XML-тегов текста
                tool_calls = list(tool_calls_data.values()) if tool_calls_data else []
                xml_tool_calls = extract_xml_tool_calls(text_buffer)
                
                if xml_tool_calls:
                    print(f"   [🔍 XML-Парсер]: Извлечено вызовов инструментов из текста: {len(xml_tool_calls)}")
                    tool_calls.extend(xml_tool_calls)
                
                # Сохраняем ассистента в историю
                assistant_msg = {"role": "assistant", "content": text_buffer}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                bot.history.append(assistant_msg)
                
                # Выполнение собранных инструментов
                if tool_calls:
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        
                        try:
                            func_args = json.loads(tool_call["function"]["arguments"]) if tool_call["function"]["arguments"] else {}
                        except Exception as je:
                            print(f"   [⚠️ Ошибка разбора аргументов JSON для {func_name}]: {je}")
                            func_args = {}
                            
                        print(f"   [⚙️ Инструмент запущен]: {func_name} {func_args}")
                        
                        func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                        result = func_to_call(**func_args) if func_to_call else "Ошибка"
                        
                        bot.history.append({
                            "role": "tool", 
                            "tool_call_id": tool_call["id"], 
                            "name": func_name, 
                            "content": str(result)
                        })
                    continue  # Возврат к генерации ответа на основе результатов работы инструментов
                else:
                    break

        except Exception as e:
            print(f"[Критическая Ошибка в цикле]: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main_loop())