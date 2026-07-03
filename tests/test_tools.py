# py -m tests.test_tools
import asyncio
import json
from modules.brain.llm import NovaLLM
from modules.tools.registry import NOVA_TOOLS
from modules.tools.os_utils import get_current_time, open_application, type_text
from core.config import SMART_MODEL
AVAILABLE_FUNCTIONS = {
    "get_current_time": get_current_time,
    "open_application": open_application,
    "type_text": type_text
}

async def run_tool_test():
    bot = NovaLLM(model=SMART_MODEL)
    # Очищаем память перед стартом
    bot.reset_context()
    
    user_request = "Открой блокнот. Напиши там стих о космосе. А потом скажи мне точное время."
    print(f"\n[Пользователь]: {user_request}")
    
    # Добавляем наш запрос в память
    bot.history.append({"role": "user", "content": user_request})
    
    # ЦИКЛ АГЕНТА: Даем ИИ максимум 5 шагов на выполнение всей цепочки
    for step in range(5):
        print(f"[Система]: Nova думает (Шаг {step+1}/5)...")
        
        try:
            # Отправляем всю историю ИИ вместе с инструментами
            response = await bot._safe_api_call(
                model=bot.primary_model,
                messages=[{"role": "system", "content": "Ты Nova, ИИ-ассистент."}] + bot.history,
                tools=NOVA_TOOLS
            )
        except Exception as e:
            print(f"[Ошибка сети/API]: {e}")
            break
            
        msg = response.choices[0].message
        
        # Безопасно сохраняем ответ ИИ в историю
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {"name": t.function.name, "arguments": t.function.arguments}
                } for t in msg.tool_calls
            ]
        bot.history.append(assistant_msg)
        
        # Если ИИ решил использовать инструменты
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(f"[⚙️ Инструмент]: Выполняю '{func_name}' -> {func_args}")
                
                func_to_call = AVAILABLE_FUNCTIONS.get(func_name)
                if func_to_call:
                    result = func_to_call(**func_args)
                else:
                    result = f"Ошибка: Функция {func_name} не найдена."
                
                # Отправляем результат выполнения функции обратно в историю!
                bot.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })
            
            # Продолжаем цикл: отправляем ИИ обновленную историю с результатами
            continue
            
        else:
            # Если инструментов в ответе нет, значит ИИ закончил работу и написал ответ текстом
            print(f"\n[Nova]: {msg.content}")
            break

if __name__ == "__main__":
    asyncio.run(run_tool_test())