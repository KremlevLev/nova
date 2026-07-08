# py -m main
import asyncio
import json
import traceback
import re
from core.config import BASE_URL, DEFAULT_MODEL

try:
    from core.config import LLAMA_BEST
except ImportError:
    LLAMA_BEST = DEFAULT_MODEL

from modules.brain.llm import NovaLLM, extract_xml_tool_calls
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
from modules.audio.tts import (
    speak, speak_worker, clean_text_for_speech, 
    is_text_code_or_json, is_inside_xml_block
)

# Подключение локальных движков
from modules.brain.memory import LocalVectorMemory
from modules.tools.tasks import TaskScheduler, reminder_checker_worker
from modules.tools.app_indexer import WindowsAppIndexer
from modules.brain.router import encoder as shared_encoder

# Подключение изолированных перехватчиков (Bypasses)
from modules.brain.bypass import check_instant_app_launch, check_instant_app_close, check_fast_commands

# --- ИНИЦИАЛИЗАЦИЯ ДВИЖКОВ (СИНГЛТОНЫ) ---
memory_engine = LocalVectorMemory(encoder=shared_encoder)
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
    
    # Регистрация памяти и задач в LLM
    "save_to_memory": lambda text: memory_engine.add_document(text) or "Запомнила.",
    "search_in_memory": lambda query: "\n".join([f"- {r['text']}" for r in memory_engine.search(query)]) or "Ничего не найдено.",
    "set_reminder": lambda time_str, message: scheduler_engine.add_reminder(time_str, message),
    "get_active_reminders": lambda: scheduler_engine.list_reminders()
}

# --- ГЛАВНЫЙ ЦИКЛ ОРКЕСТРАЦИИ (MAIN LOOP) ---

async def main_loop():
    speak("Инициализация систем. Пожалуйста, подождите.")
    bot = NovaLLM(model=LLAMA_BEST)
    listener = VoiceListener()
    speak("Нова готова к работе. Я вас слушаю.")
    
    # Список имен функций для фильтрации тегов в TTS
    tool_names = list(AVAILABLE_FUNCTIONS.keys())

    while True:
        try:
            user_request = listener.listen()
            if not user_request:
                continue

            if "отключайся" in user_request.lower() or "усни" in user_request.lower():
                speak("Отключаю питание. До встречи.")
                break

            # 0.А. МГНОВЕННЫЙ ЗАПУСК ПО (ZERO-LLM BYPASS)
            is_launch, launch_speech = check_instant_app_launch(user_request, app_launcher)
            if is_launch:
                print(f"[⚡ Instant App Launch Match]: {launch_speech}")
                speak(launch_speech)
                continue

            # 0.Б. МГНОВЕННОЕ ЗАКРЫТИЕ ПО (ZERO-LLM BYPASS)
            is_close, close_speech = check_instant_app_close(user_request)
            if is_close:
                print(f"[⚡ Instant App Close Match]: {close_speech}")
                speak(close_speech)
                continue

            # 1. Быстрый Bypass по регулярным выражениям (звук, время, окна)
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
                system_instruction = (
                    "Ты Nova, ИИ-ассистент для Windows. "
                    "Тебе разрешено вызывать ТОЛЬКО те инструменты, которые предоставлены в текущем запросе (в параметре 'tools'). "
                    "Вызов любых других названий инструментов строго запрещен. Если ты выполнила действие, отвечаешь очень коротко."
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
                                        "id": tc.id or "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
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
                            
                        print(f"   [⚙️ Инструмент запущен]: {func_name} {func_args}")
                        
                        func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                        result = func_to_call(**func_args) if func_to_call else "Ошибка"
                        
                        bot.history.append({
                            "role": "tool", 
                            "tool_call_id": tool_call["id"], 
                            "name": func_name, 
                            "content": str(result)
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