# python -m modules.brain.llm
import asyncio
import logging
from typing import AsyncGenerator, Union
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
from core.config import BASE_URL, API_KEY, DEFAULT_MODEL, SYSTEM_PROMPT, SMART_MODEL

logger = logging.getLogger("NovaLLM")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(console_handler)

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    timeout=20.0,
)

class NovaLLM:
    def __init__(self, model=DEFAULT_MODEL):
        self.primary_model = model  
        self.fallback_model = SMART_MODEL
        self.history: list[dict] = []
        self._fallback_array = [self.primary_model, self.fallback_model]

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, InternalServerError)),
        before_sleep=lambda retry_state: logger.warning(f"Сбой сети. Повторная попытка {retry_state.attempt_number}/3...")
    )
    async def _safe_api_call(self, **kwargs):
        """Безопасный вызов API с авто-повторами"""
        return await client.chat.completions.create(**kwargs)

    def _handle_api_error(self, e: Exception) -> str:
        """Централизованный обработчик ошибок"""
        if isinstance(e, AuthenticationError):
            return "❌ Ошибка авторизации! Проверьте ключи API в файле .env."
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
            return "💥 Внутренняя ошибка провайдера API."
        else:
            return f"⚠️ Непредвиденная ошибка API: {str(e)}"

    async def ask(self, user_text: str, stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        messages = self._build_messages(user_text)

        kwargs = {
            "model": self.primary_model,
            "messages": messages,
            "stream": stream
        }
        # Передаем массив fallback моделей только при работе с OpenRouter
        if "openrouter" in BASE_URL:
            kwargs["extra_body"] = {"models": self._fallback_array}

        try:
            completion = await self._safe_api_call(**kwargs)
        except Exception as e:
            error_msg = self._handle_api_error(e)
            logger.error(error_msg)
            
            if stream:
                async def error_generator(): yield error_msg
                return error_generator()
            return error_msg

        if stream:
            async def stream_generator() -> AsyncGenerator[str, None]:
                full_response = ""
                try:
                    async for chunk in completion:
                        if chunk.choices:
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

    def _build_messages(self, user_text: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history
        messages.append({"role": "user", "content": user_text})
        return self._trim_context(messages)

    def _trim_context(self, messages: list[dict], max_tokens_limit: int = 4000) -> list[dict]:
        full_text = "".join([msg.get("content") or "" for msg in messages if isinstance(msg, dict)])
        current_tokens = self.count_tokens(full_text)
        
        if current_tokens <= max_tokens_limit:
            return messages
            
        logger.warning(f"Превышение лимита токенов: {current_tokens}/{max_tokens_limit}. Очистка старой памяти...")
        
        while current_tokens > max_tokens_limit and len(messages) > 2:
            messages.pop(1)  # Удаляем старый вопрос
            if len(messages) > 1 and messages[1].get("role") == "assistant":
                messages.pop(1)  # Удаляем соответствующий старый ответ
                
            full_text = "".join([msg.get("content") or "" for msg in messages if isinstance(msg, dict)])
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