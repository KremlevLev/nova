# modules/input_hub/coordinator.py
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from modules.input_hub.models import (
    AssistantProfile,
    Attachment,
    InputMode,
    ModelSelectionMode,
    RequestSource,
    UserRequest,
)


logger = logging.getLogger("InputCoordinator")


class InputCoordinator:
    """
    Единая очередь пользовательских запросов.

    В неё могут писать:
    - голосовой цикл;
    - Desktop UI;
    - wake word;
    - push-to-talk;
    - quick input;
    - CLI;
    - background services.
    """

    def __init__(
        self,
        *,
        max_queue_size: int = 100,
    ) -> None:
        self._queue: asyncio.Queue[
            UserRequest | None
        ] = asyncio.Queue(
            maxsize=max_queue_size
        )

        self._closed = False
        self._known_request_ids: set[str] = set()

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def queued_requests(self) -> int:
        return self._queue.qsize()

    async def submit(
        self,
        request: UserRequest,
    ) -> bool:
        if self._closed:
            logger.warning(
                "Запрос отклонён: InputCoordinator закрыт."
            )
            return False

        if request.is_empty:
            logger.debug(
                "Пустой запрос не добавлен в очередь."
            )
            return False

        if (
            request.request_id
            in self._known_request_ids
        ):
            logger.warning(
                "Повторный request_id отклонён: %s",
                request.request_id,
            )
            return False

        self._known_request_ids.add(
            request.request_id
        )

        try:
            await self._queue.put(request)

        except asyncio.CancelledError:
            self._known_request_ids.discard(
                request.request_id
            )
            raise

        logger.info(
            (
                "Запрос поставлен в очередь: "
                "request_id=%s source=%s mode=%s"
            ),
            request.request_id,
            request.source.value,
            request.input_mode.value,
        )

        return True

    async def submit_voice(
        self,
        text: str,
        *,
        wake_word: bool = False,
        confidence: float | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> UserRequest | None:
        request = UserRequest.from_voice(
            text,
            wake_word=wake_word,
            confidence=confidence,
            session_id=session_id,
            metadata=metadata,
        )

        submitted = await self.submit(request)

        return request if submitted else None

    async def submit_text(
        self,
        text: str,
        *,
        source: RequestSource = (
            RequestSource.DESKTOP_CHAT
        ),
        profile: AssistantProfile = (
            AssistantProfile.ASSISTANT
        ),
        model_mode: ModelSelectionMode = (
            ModelSelectionMode.AUTO
        ),
        selected_model: str | None = None,
        attachments: list[Attachment] | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> UserRequest | None:
        request = UserRequest.from_text(
            text,
            source=source,
            profile=profile,
            model_mode=model_mode,
            selected_model=selected_model,
            attachments=attachments,
            session_id=session_id,
            metadata=metadata,
        )

        submitted = await self.submit(request)

        return request if submitted else None

    async def next_request(
        self,
    ) -> UserRequest | None:
        return await self._queue.get()

    def task_done(
        self,
        request: UserRequest | None,
    ) -> None:
        if request is not None:
            self._known_request_ids.discard(
                request.request_id
            )

        self._queue.task_done()

    async def requests(
        self,
    ) -> AsyncIterator[UserRequest]:
        while not self._closed:
            request = await self.next_request()

            if request is None:
                self._queue.task_done()
                break

            try:
                yield request
            finally:
                self.task_done(request)

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        while not self._queue.empty():
            try:
                request = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if request is not None:
                self._known_request_ids.discard(
                    request.request_id
                )

            self._queue.task_done()

        await self._queue.put(None)

        logger.info("InputCoordinator закрыт.")
