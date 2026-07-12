# modules/brain/model_gateway.py
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import copy

from openai import AsyncOpenAI

from core.config import (
    DAILY_LIMIT_COOLDOWN,
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    GROQ_RATE_LIMIT_COOLDOWN,
    LLM_REQUEST_TIMEOUT,
    OPENROUTER_API_KEYS,
    OPENROUTER_BASE_URL,
    PROVIDER_ERROR_COOLDOWN,
)
from modules.brain.model_router import ModelCandidate


logger = logging.getLogger("ModelGateway")


class FailureKind(StrEnum):
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    DAILY_LIMIT = "daily_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER = "server"
    CONTEXT = "context"
    BAD_REQUEST = "bad_request"
    TOOL_PROTOCOL = "tool_protocol"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class GatewayFailure(Exception):
    kind: FailureKind
    message: str
    retryable: bool
    rotate_key: bool
    rotate_model: bool
    cooldown_seconds: float = 0

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class KeySlot:
    provider: str
    index: int
    api_key: str
    cooldown_until: float = 0.0
    disabled: bool = False
    consecutive_failures: int = 0
    successful_requests: int = 0
    last_error: str | None = None
    last_success_at: float | None = None

    @property
    def label(self) -> str:
        # Никогда не логируем значение ключа.
        return f"{self.provider}-key-{self.index + 1}"

    @property
    def available(self) -> bool:
        return (
            not self.disabled
            and time.monotonic() >= self.cooldown_until
        )

    @property
    def cooldown_remaining(self) -> float:
        return max(
            0.0,
            self.cooldown_until - time.monotonic(),
        )

    def mark_success(self) -> None:
        self.consecutive_failures = 0
        self.last_error = None
        self.successful_requests += 1
        self.last_success_at = time.time()

    def mark_failure(
        self,
        failure: GatewayFailure,
    ) -> None:
        self.consecutive_failures += 1
        self.last_error = failure.message

        if failure.kind == FailureKind.AUTHENTICATION:
            self.disabled = True
            return

        if failure.cooldown_seconds > 0:
            self.cooldown_until = max(
                self.cooldown_until,
                time.monotonic() + failure.cooldown_seconds,
            )


@dataclass(slots=True)
class ModelResponse:
    provider: str
    model: str
    key_label: str
    text: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


class ModelGateway:
    def __init__(self) -> None:
        self._key_slots = {
            "groq": [
                KeySlot("groq", index, key)
                for index, key in enumerate(GROQ_API_KEYS)
            ],
            "openrouter": [
                KeySlot("openrouter", index, key)
                for index, key in enumerate(
                    OPENROUTER_API_KEYS
                )
            ],
        }

        self._clients: dict[tuple[str, int], AsyncOpenAI] = {}
        self._preferred_key_index = {
            "groq": 0,
            "openrouter": 0,
        }
        self._request_lock = asyncio.Lock()
        self._route_cooldowns: dict[
            tuple[str, int, str],
            float,
        ] = {}

    def _route_identity(
        self,
        slot: KeySlot,
        candidate: ModelCandidate,
    ) -> tuple[str, int, str]:
        return (
            slot.provider,
            slot.index,
            candidate.model,
        )


    def _route_cooldown_remaining(
        self,
        slot: KeySlot,
        candidate: ModelCandidate,
    ) -> float:
        cooldown_until = self._route_cooldowns.get(
            self._route_identity(slot, candidate),
            0.0,
        )

        return max(
            0.0,
            cooldown_until - time.monotonic(),
        )


    def _set_route_cooldown(
        self,
        slot: KeySlot,
        candidate: ModelCandidate,
        seconds: float,
    ) -> None:
        if seconds <= 0:
            return

        identity = self._route_identity(
            slot,
            candidate,
        )

        self._route_cooldowns[identity] = max(
            self._route_cooldowns.get(identity, 0.0),
            time.monotonic() + seconds,
        )

    async def close(self) -> None:
        clients = list(self._clients.values())
        self._clients.clear()

        await asyncio.gather(
            *(client.close() for client in clients),
            return_exceptions=True,
        )

    @staticmethod
    def _prepare_tools_for_provider(
        tools: list[dict[str, Any]] | None,
        provider: str,
    ) -> list[dict[str, Any]] | None:
        if not tools:
            return None

        prepared = copy.deepcopy(tools)

        if provider != "groq":
            return prepared

        def relax_schema(value: Any) -> None:
            if isinstance(value, dict):
                value.pop("additionalProperties", None)

                for child in value.values():
                    relax_schema(child)

            elif isinstance(value, list):
                for child in value:
                    relax_schema(child)

        for tool in prepared:
            parameters = (
                tool.get("function", {})
                .get("parameters")
            )
            relax_schema(parameters)

        return prepared


    def _base_url(self, provider: str) -> str:
        if provider == "groq":
            return GROQ_BASE_URL

        if provider == "openrouter":
            return OPENROUTER_BASE_URL

        raise ValueError(f"Неизвестный провайдер: {provider}")

    def _get_client(self, slot: KeySlot) -> AsyncOpenAI:
        identity = (slot.provider, slot.index)
        client = self._clients.get(identity)

        if client is None:
            client = AsyncOpenAI(
                base_url=self._base_url(slot.provider),
                api_key=slot.api_key,
                timeout=LLM_REQUEST_TIMEOUT,
                # Важно: не ждем скрытые автоматические повторы SDK.
                max_retries=0,
            )
            self._clients[identity] = client

        return client

    def _ordered_slots(
        self,
        provider: str,
    ) -> list[KeySlot]:
        slots = self._key_slots.get(provider, [])

        if not slots:
            return []

        preferred = self._preferred_key_index.get(provider, 0)
        return slots[preferred:] + slots[:preferred]

    def _set_preferred(self, slot: KeySlot) -> None:
        self._preferred_key_index[slot.provider] = slot.index

    @staticmethod
    def _extract_retry_after(error: Exception) -> float | None:
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)

        if not headers:
            return None

        raw_value = headers.get("retry-after")

        if not raw_value:
            return None

        try:
            return max(1.0, float(raw_value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def classify_failure(
        cls,
        error: Exception,
    ) -> GatewayFailure:
        message = str(error)
        lowered = message.lower()
        status_code = getattr(error, "status_code", None)

        retry_after = cls._extract_retry_after(error)

        if status_code in {401, 403} or any(
            marker in lowered
            for marker in (
                "invalid api key",
                "incorrect api key",
                "authentication",
                "unauthorized",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.AUTHENTICATION,
                message="Ключ провайдера отклонен.",
                retryable=False,
                rotate_key=True,
                rotate_model=False,
            )

        daily_markers = (
            "daily limit",
            "daily quota",
            "per day",
            "tokens per day",
            "requests per day",
            "tpd",
            "rpd",
            "quota exceeded",
            "insufficient_quota",
        )

        if any(marker in lowered for marker in daily_markers):
            return GatewayFailure(
                kind=FailureKind.DAILY_LIMIT,
                message="Достигнут долгосрочный лимит ключа.",
                retryable=True,
                rotate_key=True,
                rotate_model=True,
                cooldown_seconds=DAILY_LIMIT_COOLDOWN,
            )

        if status_code == 429 or any(
            marker in lowered
            for marker in (
                "rate limit",
                "rate_limit",
                "too many requests",
                "tpm",
                "rpm",
                "limit exceeded",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.RATE_LIMIT,
                message="Достигнут краткосрочный лимит ключа.",
                retryable=True,
                rotate_key=True,
                rotate_model=True,
                cooldown_seconds=(
                    retry_after
                    or GROQ_RATE_LIMIT_COOLDOWN
                ),
            )

        if "tool choice is none" in lowered:
            return GatewayFailure(
                kind=FailureKind.TOOL_PROTOCOL,
                message=(
                    "Модель попыталась вызвать инструмент в режиме "
                    "финального ответа."
                ),
                retryable=True,
                rotate_key=False,
                rotate_model=True,
            )

        if any(
            marker in lowered
            for marker in (
                "context_length",
                "context length",
                "maximum context",
                "too many tokens",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.CONTEXT,
                message="Контекст превышает лимит модели.",
                retryable=False,
                rotate_key=False,
                rotate_model=True,
            )

        if status_code in {500, 502, 503, 504}:
            return GatewayFailure(
                kind=FailureKind.SERVER,
                message=f"Ошибка сервера провайдера: {status_code}.",
                retryable=True,
                rotate_key=False,
                rotate_model=True,
                cooldown_seconds=PROVIDER_ERROR_COOLDOWN,
            )

        if any(
            marker in lowered
            for marker in (
                "timeout",
                "timed out",
                "read timeout",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.TIMEOUT,
                message="Превышено время ожидания модели.",
                retryable=True,
                rotate_key=False,
                rotate_model=True,
                cooldown_seconds=10,
            )

        if any(
            marker in lowered
            for marker in (
                "connection",
                "network",
                "dns",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.CONNECTION,
                message="Ошибка соединения с провайдером.",
                retryable=True,
                rotate_key=False,
                rotate_model=True,
                cooldown_seconds=10,
            )
        if any(
            marker in lowered
            for marker in (
                "tool call validation failed",
                "parameters for tool",
                "did not match schema",
                "additionalproperties",
            )
        ):
            return GatewayFailure(
                kind=FailureKind.TOOL_PROTOCOL,
                message=(
                    "Модель сформировала некорректные аргументы "
                    "инструмента."
                ),
                retryable=True,
                rotate_key=False,
                rotate_model=True,
            )
        if status_code == 400:
            return GatewayFailure(
                kind=FailureKind.BAD_REQUEST,
                message=f"Провайдер отклонил запрос: {message}",
                retryable=False,
                rotate_key=False,
                rotate_model=True,
            )

        return GatewayFailure(
            kind=FailureKind.UNKNOWN,
            message=f"Неизвестная ошибка модели: {message}",
            retryable=True,
            rotate_key=False,
            rotate_model=True,
            cooldown_seconds=10,
        )

    @staticmethod
    def _consume_tool_call_delta(
        target: dict[int, dict[str, Any]],
        delta_tool_calls: Any,
    ) -> None:
        for tool_call in delta_tool_calls or []:
            index = tool_call.index

            if index not in target:
                target[index] = {
                    "id": tool_call.id or "",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": "",
                    },
                }

            current = target[index]

            if tool_call.id:
                current["id"] = tool_call.id

            function = getattr(tool_call, "function", None)
            if function is None:
                continue

            if function.name:
                current["function"]["name"] += function.name

            if function.arguments:
                current["function"]["arguments"] += (
                    function.arguments
                )

    async def _request_once(
        self,
        *,
        slot: KeySlot,
        candidate: ModelCandidate,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        allow_tools: bool,
    ) -> ModelResponse:
        client = self._get_client(slot)

        kwargs: dict[str, Any] = {
            "model": candidate.model,
            "messages": messages,
            "stream": True,
        }

        prepared_tools = self._prepare_tools_for_provider(
            tools,
            candidate.provider,
        )

        if (
            allow_tools
            and prepared_tools
            and candidate.supports_tools
        ):
            kwargs["tools"] = prepared_tools
            kwargs["tool_choice"] = "auto"


        if candidate.provider == "openrouter":
            kwargs["extra_headers"] = {
                "HTTP-Referer": "https://localhost/nova",
                "X-Title": "Nova Windows Assistant",
            }

            # Разрешаем OpenRouter выбрать резервного провайдера
            # для конкретной модели.
            kwargs["extra_body"] = {
                "provider": {
                    "allow_fallbacks": True,
                }
            }

        stream = await client.chat.completions.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}

        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage_object = chunk.usage
                usage = (
                    usage_object.model_dump()
                    if hasattr(usage_object, "model_dump")
                    else {}
                )

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            finish_reason = (
                choice.finish_reason or finish_reason
            )
            delta = choice.delta

            if delta.content:
                text_parts.append(delta.content)

            self._consume_tool_call_delta(
                tool_calls,
                delta.tool_calls,
            )

        text = "".join(text_parts).strip()
        normalized_calls = list(tool_calls.values())

        if not text and not normalized_calls:
            raise GatewayFailure(
                kind=FailureKind.EMPTY_RESPONSE,
                message="Модель вернула пустой ответ.",
                retryable=True,
                rotate_key=False,
                rotate_model=True,
            )

        return ModelResponse(
            provider=candidate.provider,
            model=candidate.model,
            key_label=slot.label,
            text=text,
            tool_calls=normalized_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def complete(
        self,
        *,
        candidates: list[ModelCandidate],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        allow_tools: bool = True,
        requires_vision: bool = False,
    ) -> ModelResponse:
        failures: list[str] = []

        for candidate in candidates:
            if requires_vision and not candidate.supports_vision:
                continue

            slots = self._ordered_slots(candidate.provider)

            if not slots:
                failures.append(
                    f"{candidate.identity}: нет API-ключей"
                )
                continue

            attempted_slot = False

            for slot in slots:
                if not slot.available:
                    logger.info(
                        "%s пропущен, cooldown %.0f сек.",
                        slot.label,
                        slot.cooldown_remaining,
                    )
                    continue
                route_cooldown = (
                self._route_cooldown_remaining(
                    slot,
                    candidate,
                )
            )

                if route_cooldown > 0:
                    logger.info(
                        "%s/%s пропущен, cooldown модели %.0f сек.",
                        slot.label,
                        candidate.model,
                        route_cooldown,
                    )
                    continue
            

                attempted_slot = True

                logger.info(
                    "Запрос: provider=%s model=%s key=%s",
                    candidate.provider,
                    candidate.model,
                    slot.label,
                )

                try:
                    response = await self._request_once(
                        slot=slot,
                        candidate=candidate,
                        messages=messages,
                        tools=tools,
                        allow_tools=allow_tools,
                    )
                except GatewayFailure as failure:
                    if failure.kind in {
                        FailureKind.AUTHENTICATION,
                        FailureKind.DAILY_LIMIT,
                    }:
                        slot.mark_failure(failure)

                    elif failure.kind == FailureKind.RATE_LIMIT:
                        slot.consecutive_failures += 1
                        slot.last_error = failure.message

                        self._set_route_cooldown(
                            slot,
                            candidate,
                            failure.cooldown_seconds,
                        )

                    else:
                        slot.consecutive_failures += 1
                        slot.last_error = failure.message

                    failures.append(
                        f"{candidate.identity}/{slot.label}: "
                        f"{failure.message}"
                    )

                    logger.warning(
                        "Сбой %s на %s: %s",
                        candidate.identity,
                        slot.label,
                        failure.message,
                    )

                    if failure.rotate_key:
                        continue

                    # Ошибка относится к модели или запросу,
                    # поэтому остальные ключи этой же модели не тратим.
                    break
                except Exception as error:
                    failure = self.classify_failure(error)
                    if failure.kind in {
                        FailureKind.AUTHENTICATION,
                        FailureKind.DAILY_LIMIT,
                    }:
                        slot.mark_failure(failure)
                    
                    elif failure.kind == FailureKind.RATE_LIMIT:
                        slot.consecutive_failures += 1
                        slot.last_error = failure.message
                    
                        self._set_route_cooldown(
                            slot,
                            candidate,
                            failure.cooldown_seconds,
                        )
                    
                    else:
                        slot.consecutive_failures += 1
                        slot.last_error = failure.message
                    
                    failures.append(
                        f"{candidate.identity}/{slot.label}: "
                        f"{failure.message}"
                    )

                    logger.warning(
                        "Сбой %s на %s: %s",
                        candidate.identity,
                        slot.label,
                        failure.message,
                    )

                    if failure.rotate_key:
                        continue

                    break
                else:
                    slot.mark_success()
                    self._set_preferred(slot)

                    logger.info(
                        "Успешный ответ: provider=%s model=%s "
                        "key=%s finish=%s",
                        response.provider,
                        response.model,
                        response.key_label,
                        response.finish_reason,
                    )
                    return response

            if not attempted_slot:
                failures.append(
                    f"{candidate.identity}: все ключи на cooldown"
                )

        raise RuntimeError(
            "Ни один модельный маршрут не сработал. "
            + " | ".join(failures)
        )

    def health_snapshot(self) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []

        for provider, slots in self._key_slots.items():
            for slot in slots:
                snapshot.append(
                    {
                        "provider": provider,
                        "key": slot.label,
                        "available": slot.available,
                        "disabled": slot.disabled,
                        "cooldown_seconds": round(
                            slot.cooldown_remaining,
                            1,
                        ),
                        "successful_requests": (
                            slot.successful_requests
                        ),
                        "consecutive_failures": (
                            slot.consecutive_failures
                        ),
                        "last_error": slot.last_error,
                    }
                )

        return snapshot
