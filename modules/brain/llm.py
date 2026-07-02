# python -m modules.brain.llm
import asyncio
import logging
from typing import AsyncGenerator, Union

import openai
from openai import AsyncOpenAI
from openai import (
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    BadRequestError,
    InternalServerError
)
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
# Заменяем print на профессиональный логгер
logger = logging.getLogger("NovaLLM")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(console_handler)

# --- ЗАГЛУШКИ КОНФИГА (Замените на ваши импорты) ---
from core.config import BASE_URL, OPENROUTER_API_KEY, SMART_MODEL, debug, MODELS_LIST, SYSTEM_PROMPT
BASE_URL = BASE_URL
OPENROUTER_API_KEY = OPENROUTER_API_KEY
MODELS_LIST = MODELS_LIST
SMART_MODEL = SMART_MODEL
SYSTEM_PROMPT = SYSTEM_PROMPT

# Инициализация клиента (добавлены таймауты)
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=OPENROUTER_API_KEY,
    timeout=30.0, # Предохранитель, если сервер завис
)

class NovaLLM:
    def __init__(self, model=MODELS_LIST[0]):
        self.primary_model = model  # ИСПРАВЛЕНО: было self.model, а вызывалось self.primary_model
        self.fallback_model = SMART_MODEL
        self.history: list[dict] = []
        self._fallback_array = [self.primary_model, self.fallback_model]

    # --- ДЕКОРАТОР ПОВТОРНЫХ ПОПЫТОК ---
    # Будет пытаться отправить запрос 3 раза, если ошибка связана с сетью или таймаутом
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, InternalServerError)),
        before_sleep=lambda retry_state: logger.warning(f"Сбой сети. Повторная попытка {retry_state.attempt_number}/3...")
    )
    async def _safe_api_call(self, **kwargs):
        """Внутренний метод для безопасного вызова API с авто-повторами"""
        return await client.chat.completions.create(**kwargs)

    def _handle_api_error(self, e: Exception) -> str:
        """Централизованный обработчик ошибок"""
        if isinstance(e, AuthenticationError):
            return "❌ Ошибка авторизации! Проверьте OPENROUTER_API_KEY."
        elif isinstance(e, RateLimitError):
            return "⏳ Лимит запросов исчерпан! Модели перегружены. Попробуйте позже."
        elif isinstance(e, APITimeoutError):
            return "⏰ Превышено время ожидания ответа от сервера."
        elif isinstance(e, APIConnectionError):
            return "🌐 Ошибка соединения! Проверьте интернет."
        elif isinstance(e, BadRequestError):
            if "context_length_exceeded" in str(e):
                return "🧠 Контекст переполнен! Вызовите reset_context()."
            return f"⚙️ Неверный формат запроса. Детали: {e.message}"
        elif isinstance(e, InternalServerError):
            return "💥 Внутренняя ошибка провайдера OpenRouter."
        else:
            return f"⚠️ Непредвиденная ошибка API: {str(e)}"

    async def ask(self, user_text: str, stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        messages = self._build_messages(user_text)

        try:
            completion = await self._safe_api_call(
                model=self.primary_model,
                messages=messages,
                stream=stream,
                extra_body={"models": self._fallback_array}
            )
        except Exception as e:
            error_msg = self._handle_api_error(e)
            logger.error(error_msg)
            
            # ИСПРАВЛЕНИЕ КРИТИЧЕСКОГО БАГА С ПОТОКОМ
            # Если ожидается stream, мы обязаны вернуть генератор, иначе код сломается
            if stream:
                async def error_generator(): yield error_msg
                return error_generator()
            return error_msg

        if stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                full_response = ""
                try:
                    async for chunk in completion:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            full_response += delta
                            yield delta
                    self.history.append({"role": "user", "content": user_text})
                    self.history.append({"role": "assistant", "content": full_response})
                except Exception as stream_err:
                    logger.error(f"Поток оборвался: {stream_err}")
                    yield f"\n[Ошибка потока: {stream_err}]"
            return stream_generator()
        else:
            response_text = completion.choices[0].message.content
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": response_text})
            return response_text

    async def ask_with_tools(self, user_text: str, tools: list[dict]) -> dict:
        # ДОБАВЛЕНА ОБРАБОТКА ОШИБОК ДЛЯ TOOLS
        messages = self._build_messages(user_text)
        try:
            completion = await self._safe_api_call(
                model=self.primary_model,
                messages=messages,
                tools=tools,
                extra_body={"models": self._fallback_array}
            )
            return completion.choices[0].message.model_dump()
            
        except Exception as e:
            error_msg = self._handle_api_error(e)
            logger.error(f"Ошибка при вызове Tools: {error_msg}")
            # Возвращаем структуру, имитирующую обычный текстовый ответ-ошибку
            return {"role": "assistant", "content": error_msg, "tool_calls": None}

    def _build_messages(self, user_text: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history
        messages.append({"role": "user", "content": user_text})
        return self._trim_context(messages)

    def _trim_context(self, messages: list[dict], max_tokens_limit: int = 4000) -> list[dict]:
        full_text = "".join([msg["content"] for msg in messages if msg.get("content")])
        current_tokens = self.count_tokens(full_text)
        
        if current_tokens <= max_tokens_limit:
            return messages
            
        logger.warning(f"Превышение лимита токенов: {current_tokens}/{max_tokens_limit}. Очистка старой памяти...")
        
        while current_tokens > max_tokens_limit and len(messages) > 2:
            # ИСПРАВЛЕНО: Удаляем ПАРУ сообщений (вопрос + ответ), чтобы не ломать логику диалога
            messages.pop(1) # Удаляем старый вопрос пользователя
            if len(messages) > 1 and messages[1].get("role") == "assistant":
                messages.pop(1) # Удаляем старый ответ ИИ
                
            full_text = "".join([msg["content"] for msg in messages if msg.get("content")])
            current_tokens = self.count_tokens(full_text)
            
        return messages

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        tokens = 0
        for word in text.split():
            if any('а' <= char <= 'я' or 'А' <= char <= 'Я' for char in word):
                tokens += max(1, len(word) // 2)
            else:
                tokens += max(1, len(word) // 3)
        return int(tokens * 1.1)

    def reset_context(self):
        self.history.clear()
        logger.info("Память Nova полностью очищена.")

    async def __call__(self, user_input):
        return await self.ask(user_input)

# --- ТЕСТОВЫЙ ЗАПУСК ---
async def main():
    bot = NovaLLM()

    print("\n--- Шаг 1: Тест потока (Streaming) ---")
    print("Nova: ", end="", flush=True)
    # Тестируем stream=True, чтобы убедиться, что всё работает плавно
    stream_response = await bot.ask("Расскажи короткий факт о космосе.", stream=True)
    async for chunk in stream_response:
        print(chunk, end="", flush=True)
    print("\n")
    
    print("--- Шаг 2: Тест памяти ---")
    ans2 = await bot.ask("Запомни, мой любимый цвет - синий.")
    print(f"Nova: {ans2}")
    ans3 = await bot.ask("Какой мой любимый цвет?")
    print(f"Nova: {ans3}")

    print("\n--- Шаг 3: Очистка памяти ---")
    bot.reset_context()
    ans4 = await bot.ask("Какой мой любимый цвет?")
    print(f"Nova: {ans4}")

if __name__ == "__main__":
    asyncio.run(main())