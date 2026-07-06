# py -m tests.test_tools
import asyncio
import json
from modules.brain.llm import NovaLLM
from modules.brain.router import get_intent
from modules.tools.registry import TOOL_REGISTRY
from core.config import SMART_MODEL
from modules.tools.os_utils import (
    get_current_time, open_application, type_text, 
    change_volume, open_website, execute_cmd_command, 
    get_system_status, search_web_tavily
)

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

async def run_smart_agent():
    bot = NovaLLM(model=SMART_MODEL)
    bot.reset_context()
    
    # 1. Запрос пользователя
    user_request = "Скажи, сколько у меня сейчас свободной оперативной памяти?"
    print(f"\n[Пользователь]: {user_request}")
    
    # 2. МГНОВЕННЫЙ РОУТИНГ (0.08 сек)
    intents = get_intent(user_request)
    primary_intent = intents[0] # Берем самый уверенный вариант
    print(f"[Роутер]: Определил категорию -> {primary_intent.upper()}")
    
    # 3. ПОДБОР ИНСТРУМЕНТОВ
    # Достаем инструменты только для этой категории. Если их нет - пустой список.
    active_tools = TOOL_REGISTRY.get(primary_intent, [])
    
    if not active_tools:
        print("[Система]: Для этой категории инструменты не нужны. Обычный чат.")
    else:
        print(f"[Система]: Выдаю LLM узкий набор инструментов ({len(active_tools)} шт.)")

    # Добавляем запрос в историю
    bot.history.append({"role": "user", "content": user_request})
    
    # 4. ЦИКЛ АГЕНТА (с отфильтрованными инструментами)
    for step in range(3):
        print(f"[Nova]: Думает (Шаг {step+1})...")
        
        # Если active_tools пустой, kwargs не будет содержать 'tools'
        kwargs = {
            "model": bot.primary_model,
            "messages": [{"role": "system", "content": "Ты Nova."}] + bot.history,
        }
        if active_tools:
            kwargs["tools"] = active_tools

        try:
            response = await bot._safe_api_call(**kwargs)
        except Exception as e:
            print(f"[Ошибка]: {e}")
            break
            
        msg = response.choices[0].message
        
        # Сохраняем ответ
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} 
                for t in msg.tool_calls
            ]
        bot.history.append(assistant_msg)
        
        # Выполнение инструментов
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                print(f"   [⚙️ Вызов]: {func_name} {func_args}")
                
                func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                result = func_to_call(**func_args) if func_to_call else f"Ошибка: нет функции {func_name}"
                
                bot.history.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": str(result)})
            continue
        else:
            print(f"\n[Nova]: {msg.content}")
            break

if __name__ == "__main__":
    asyncio.run(run_smart_agent())