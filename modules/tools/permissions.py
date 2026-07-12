# modules/tools/permissions.py
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field

from modules.tools.policy import (
    PolicyContext,
    PolicyDecision,
    evaluate_policy,
    format_confirmation_message,
)


logger = logging.getLogger("Permissions")


@dataclass(slots=True)
class PermissionRequest:
    operation_id: str
    policy_context: PolicyContext
    decision: PolicyDecision
    message: str

    created_at: float = field(
        default_factory=time.time
    )
    expires_at: float = 0.0

    resolved: bool = False
    granted: bool = False

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False

        return time.time() > self.expires_at


class PermissionManager:
    """
    Централизованный менеджер разрешений.

    В текущей реализации:
    - ALLOW и ALLOW_WITH_WARNING проходят без подтверждения;
    - REQUIRE_CONFIRMATION и REQUIRE_STRONG_CONFIRMATION
      требуют вызова confirm() или deny().

    В будущем:
    - голосовое подтверждение;
    - ПИН-код для сильного подтверждения;
    - доверенные временные окна;
    - политики по умолчанию для конкретных приложений.
    """

    def __init__(self) -> None:
        self._pending: dict[
            str,
            PermissionRequest,
        ] = {}
        self._lock = threading.RLock()

    def request(
        self,
        policy_context: PolicyContext,
        *,
        expires_after_seconds: float = 60.0,
    ) -> PermissionRequest:
        decision = evaluate_policy(
            policy_context
        )

        message = format_confirmation_message(
            policy_context
        )

        request = PermissionRequest(
            operation_id=(
                policy_context.operation_id
            ),
            policy_context=policy_context,
            decision=decision,
            message=message,
            expires_at=(
                time.time()
                + expires_after_seconds
                if decision
                in {
                    PolicyDecision.REQUIRE_CONFIRMATION,
                    PolicyDecision.REQUIRE_STRONG_CONFIRMATION,
                }
                else 0.0
            ),
        )

        with self._lock:
            self._pending[
                request.operation_id
            ] = request

        logger.info(
            "Запрос разрешения: operation_id=%s "
            "tool=%s decision=%s",
            request.operation_id,
            policy_context.tool_name,
            decision.value,
        )

        return request

    def confirm(
        self,
        operation_id: str,
    ) -> bool:
        with self._lock:
            request = self._pending.get(
                operation_id
            )

            if request is None:
                logger.warning(
                    "Запрос %s не найден.",
                    operation_id,
                )
                return False

            if request.is_expired():
                logger.warning(
                    "Запрос %s истёк.",
                    operation_id,
                )
                return False

            if request.resolved:
                logger.warning(
                    "Запрос %s уже обработан.",
                    operation_id,
                )
                return False

            request.resolved = True
            request.granted = True

            del self._pending[operation_id]

        logger.info(
            "Разрешено: operation_id=%s tool=%s",
            operation_id,
            request.policy_context.tool_name,
        )

        return True

    def deny(
        self,
        operation_id: str,
    ) -> bool:
        with self._lock:
            request = self._pending.get(
                operation_id
            )

            if request is None:
                return False

            if request.resolved:
                return False

            request.resolved = True
            request.granted = False

            del self._pending[operation_id]

        logger.info(
            "Запрещено: operation_id=%s tool=%s",
            operation_id,
            request.policy_context.tool_name,
        )

        return True

    def check(
        self,
        policy_context: PolicyContext,
    ) -> tuple[bool, str | None]:
        """
        Синхронная проверка без ожидания подтверждения.

        Возвращает:
        - (True, None) — разрешено;
        - (False, "причина") — запрещено;
        - (False, None) — требуется подтверждение.
        """
        decision = evaluate_policy(
            policy_context
        )

        if decision == PolicyDecision.DENY:
            return (
                False,
                (
                    f"Инструмент "
                    f"'{policy_context.tool_name}' "
                    "запрещён политикой безопасности."
                ),
            )

        if decision in {
            PolicyDecision.REQUIRE_CONFIRMATION,
            PolicyDecision.REQUIRE_STRONG_CONFIRMATION,
        }:
            return (False, None)

        return (True, None)

    async def wait_for_confirmation(
        self,
        policy_context: PolicyContext,
        *,
        timeout_seconds: float = 60.0,
    ) -> bool:
        """
        Асинхронно ожидает подтверждения.

        В текущей реализации — заглушка, которая всегда
        возвращает True.

        В будущем:
        - отправляет событие в UI;
        - ожидает ответа пользователя;
        - применяет таймаут.
        """
        request = self.request(
            policy_context,
            expires_after_seconds=(
                timeout_seconds
            ),
        )

        if request.decision in {
            PolicyDecision.ALLOW,
            PolicyDecision.ALLOW_WITH_WARNING,
        }:
            return True

        if request.decision == PolicyDecision.DENY:
            return False

        # Временная заглушка: всегда разрешаем.
        # TODO: интеграция с UI.
        logger.info(
            "Ожидание подтверждения: operation_id=%s "
            "tool=%s (заглушка: разрешено)",
            request.operation_id,
            policy_context.tool_name,
        )

        await asyncio.sleep(0.1)

        self.confirm(request.operation_id)

        return True
