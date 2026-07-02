# python -m modules.brain.llm
import asyncio
from typing import AsyncGenerator, Union
from openai import AsyncOpenAI
# Импортируем всё необходимое из вашего конфига
from core.config import BASE_URL, OPENROUTER_API_KEY, SMART_MODEL, debug, MODELS_LIST

# Инициализация клиента с настройками OpenRouter
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

class novaLLM:
    # По умолчанию берем первую модель из импортированного MODELS_LIST
    def __init__(self, model=MODELS_LIST[0]):
        self.model = model
        self.fallback_model = SMART_MODEL  # Можно использовать SMART_MODEL как fallback
        self.history: list[dict] = []  # История сообщений
        self._fallback_array = [self.model, self.fallback_model]

    async def ask(self, user_text: str, stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        # Пока методы _build_messages и _trim_context не написаны, 
        # временно собираем промпт напрямую. Позже заменим эту строчку на:
        # messages = self._build_messages(user_text)
        messages = self.history + [{"role": "user", "content": user_text}]

        # Отправляем запрос в OpenRouter с поддержкой фолбека
        completion = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,  # Включаем или выключаем потоковую передачу
            extra_body={
                "models": self._fallback_array  # Авто-фолбек на сервере OpenRouter
            }
        )

        # СЦЕНАРИЙ А: Если включен СТРИМИНГ
        if stream:
            # Внутренняя асинхронная функция-генератор
            async def stream_generator() -> AsyncGenerator[str, None]:
                full_response = ""
                async for chunk in completion:
                    # Извлекаем кусочек текста из чанка
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        full_response += delta
                        yield delta  # Отдаем кусочек текста наружу в реальном времени
                
                # Когда поток завершился, сохраняем диалог в память
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": full_response})

            return stream_generator()  # Возвращаем сам генератор

        # СЦЕНАРИЙ Б: Обычный синхронный ответ (строка)
        else:
            response_text = completion.choices[0].message.content
            
            # Сохраняем успешный шаг в историю
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": response_text})
            
            return response_text

    async def __call__(self, user_input):
        return await self.ask(user_input)
    
    # 3. МЕТОД ASK WITH TOOLS (Function Calling)
    async def ask_with_tools(self, user_text: str, tools: list[dict]) -> dict:
        messages = self.history + [{"role": "user", "content": user_text}]

        completion = await client.chat.completions.create(
            model=self.primary_model,
            messages=messages,
            tools=tools,       # Передаем список доступных функций/инструментов
            extra_body={
                "models": self._fallback_array
            }
        )
        
        # Модель возвращает специальный объект с инструкциями, какую функцию вызвать.
        # Мы переводим его в обычный словарь (dict) для удобства дальнейшей обработки.
        message_object = completion.choices[0].message
        
        # Возвращаем словарь, содержащий либо обычный текст, либо tool_calls
        return message_object.model_dump()

async def main():
    bot = novaLLM()

    # ТЕСТ 1: Обычный текстовый запрос (stream=False)
    print("--- Тест обычного запроса ---")
    simple_answer = await bot.ask("Напиши слово 'Привет' на английском.")
    print(f"Ответ: {simple_answer}\n")

    # ТЕСТ 2: Потоковый запрос (stream=True)
    print("--- Тест стриминга ---")
    print("Ответ Nova: ", end="", flush=True)
    
    stream_response = await bot.ask("Расскажи очень короткий анекдот.", stream=True)
    async for chunk in stream_response:
        print(chunk, end="", flush=True)  # Печатаем буквы по мере их появления
    print("\n\n--- Тесты завершены ---")

if __name__ == "__main__":
    asyncio.run(main())