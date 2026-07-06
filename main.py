# py -m main
import asyncio
import json
from core.config import SMART_MODEL
from modules.brain.llm import NovaLLM
from modules.brain.router import get_intent
from modules.tools.registry import TOOL_REGISTRY
from modules.tools.os_utils import (
    get_current_time, open_application, type_text, 
    change_volume, open_website, execute_cmd_command, 
    get_system_status, search_web_tavily
)
from modules.audio.stt import VoiceListener
from modules.audio.tts import speak

# Связь JSON-имен с реальным Python кодом
AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
    "open_application": open_application,
    "type_text": type_text,
    "change_volume": change_volume,
    "open_website": open_website,
    "execute_cmd_command": execute_cmd_command,
    "get_system_status": get_system_status,
    "search_web_tavily": search_web_tavily
}

async def main_loop():
    # Инициализация всех систем
    speak("Инициализация, подождите")
    bot = NovaLLM(model=SMART_MODEL)
    listener = VoiceListener()
    speak("Нова готова к работе. Я вас слушаю.")

    while True:
        # 1. СЛУШАЕМ (Офлайн)
        user_request = listener.listen()
        
        # Пасхалка: экстренное отключение
        if "отключайся" in user_request or "усни" in user_request:
            speak("Отключаю питание. До встречи.")
            break

        # 2. РОУТИНГ (Мгновенно)
        intents = get_intent(user_request)
        primary_intent = intents[0]
        active_tools = TOOL_REGISTRY.get(primary_intent, [])
        
        # 3. ДОБАВЛЯЕМ В ПАМЯТЬ
        bot.history.append({"role": "user", "content": user_request})

        # 4. ОБРАБОТКА ИНТЕЛЛЕКТОМ
        for step in range(3):
            kwargs = {
                "model": bot.primary_model,
                "messages": [{"role": "system", "content": "Ты Nova, голосовой ИИ-помощник. Отвечай кратко, емко и по делу. Не пиши списки, если это не нужно, так как текст будет озвучен голосом."}] + bot.history,
            }
            if active_tools:
                kwargs["tools"] = active_tools

            response = await bot._safe_api_call(**kwargs)
            msg = response.choices[0].message
            
            # Сохраняем ответ
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in msg.tool_calls]
            bot.history.append(assistant_msg)
            
            # Выполнение инструментов
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    
                    func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                    result = func_to_call(**func_args) if func_to_call else "Ошибка"
                    
                    bot.history.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": str(result)})
                continue # Возвращаемся к LLM с результатами
            else:
                # 5. ГОВОРИМ ОТВЕТ
                if msg.content:
                    speak(msg.content)
                break # Выходим из цикла агента, ждем новую команду голосом

if __name__ == "__main__":
    asyncio.run(main_loop())