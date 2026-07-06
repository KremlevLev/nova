# py -m main
import asyncio
import json
import traceback
from modules.brain.llm import NovaLLM
from modules.brain.router import get_intent
from modules.tools.registry import TOOL_REGISTRY
from modules.tools.os_utils import (
    get_current_time, open_application, type_text, 
    change_volume, open_website, execute_cmd_command, 
    get_system_status, search_web_tavily,
    manage_media, manage_windows, create_quick_note, set_timer
)
from modules.audio.stt import VoiceListener
from modules.audio.tts import speak
from core.config import DEFAULT_MODEL_3
AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
    "open_application": open_application,
    "type_text": type_text,
    "change_volume": change_volume,
    "open_website": open_website,
    "execute_cmd_command": execute_cmd_command,
    "get_system_status": get_system_status,
    "search_web_tavily": search_web_tavily,
    "manage_media": manage_media,              
    "manage_windows": manage_windows,         
    "create_quick_note": create_quick_note,    
    "set_timer": set_timer 
}

async def main_loop():
    speak("Инициализация систем. Пожалуйста, подождите.")
    
    bot = NovaLLM(model=DEFAULT_MODEL_3)
    listener = VoiceListener()
    
    speak("Нова готова к работе. Я вас слушаю.")

    while True:
        try:
            # 1. СЛУШАЕМ
            user_request = listener.listen()
            if not user_request:
                continue # Если была просто тишина, слушаем заново

            if "отключайся" in user_request.lower() or "усни" in user_request.lower():
                speak("Отключаю питание. До встречи.")
                break

            # 2. РОУТИНГ
            intents = get_intent(user_request)
            primary_intent = intents[0]
            active_tools = TOOL_REGISTRY.get(primary_intent, [])
            
            # Логируем для себя, чтобы видеть, что происходит под капотом
            print(f"\n[🧠 Роутер]: Выбрана категория '{primary_intent.upper()}'. Передано инструментов: {len(active_tools)}")

            bot.history.append({"role": "user", "content": user_request})

            # 3. ЦИКЛ АГЕНТА
            for step in range(3):
                kwargs = {
                    "model": bot.primary_model,
                    "messages": [{"role": "system", "content": "Ты Nova, ИИ-ассистент для Windows. Если ты выполнила действие, отвечай коротко (Например: 'Блокнот открыт')."}] + bot.history,
                }
                if active_tools:
                    kwargs["tools"] = active_tools

                print(f"[Nova]: Анализирует данные (Шаг {step+1})...")
                response = await bot._safe_api_call(**kwargs)
                
                # Защита от пустых ответов
                if not response or not hasattr(response, 'choices'):
                    print("[Ошибка]: Модель не вернула ответ.")
                    speak("Произошла ошибка при получении ответа от нейросети.")
                    break

                msg = response.choices[0].message
                
                # Сохраняем ответ ИИ
                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    assistant_msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in msg.tool_calls]
                bot.history.append(assistant_msg)
                
                # Выполнение Инструментов
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        func_name = tool_call.function.name
                        func_args = json.loads(tool_call.function.arguments)
                        print(f"   [⚙️ Инструмент запущен]: {func_name} {func_args}")
                        
                        func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                        result = func_to_call(**func_args) if func_to_call else "Ошибка"
                        
                        bot.history.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": str(result)})
                    continue # Возвращаемся в LLM с результатами
                else:
                    # Если инструментов больше нет - ГОВОРИМ
                    if msg.content:
                        speak(msg.content)
                    break 

        except Exception as e:
            print(f"[Критическая Ошибка в цикле]: {e}")
            traceback.print_exc() # Покажет точную строку ошибки

if __name__ == "__main__":
    asyncio.run(main_loop())