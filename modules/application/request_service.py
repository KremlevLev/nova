# modules/application/request_service.py
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from modules.application.request_dispatcher import (
    RequestDispatcher,
)
from modules.domain.results import (
    AssistantResponse,
)
from modules.input_hub.coordinator import (
    InputCoordinator,
)
from modules.input_hub.models import (
    UserRequest,
)


logger = logging.getLogger(
    "RequestService"
)


ResponseHandler = Callable[
    [UserRequest, AssistantResponse],
    Awaitable[None],
]


class RequestService:
    """
    Последовательно обрабатывает запросы из InputCoordinator.

    На данном этапе одновременно исполняется один запрос. Это защищает
    GUI и clipboard-инструменты от конфликтующих действий.
    """

    def __init__(
        self,
        *,
        coordinator: InputCoordinator,
        dispatcher: RequestDispatcher,
        response_handler: (
            ResponseHandler | None
        ) = None,
    ) -> None:
        self.coordinator = coordinator
        self.dispatcher = dispatcher
        self.response_handler = (
            response_handler
        )

        self._current_request: (
            UserRequest | None
        ) = None
        self._current_task: (
            asyncio.Task | None
        ) = None

    @property
    def current_request(
        self,
    ) -> UserRequest | None:
        return self._current_request

    async def run(
        self,
        shutdown_event: asyncio.Event,
    ) -> None:
        while not shutdown_event.is_set():
            request_task = asyncio.create_task(
                self.coordinator.next_request()
            )
            shutdown_task = asyncio.create_task(
                shutdown_event.wait()
            )

            done, pending = await asyncio.wait(
                {
                    request_task,
                    shutdown_task,
                },
                return_when=(
                    asyncio.FIRST_COMPLETED
                ),
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(
                *pending,
                return_exceptions=True,
            )

            if shutdown_task in done:
                if not request_task.done():
                    request_task.cancel()
                break

            request = request_task.result()

            if request is None:
                self.coordinator.task_done(
                    None
                )
                break

            self._current_request = request

            try:
                self._current_task = (
                    asyncio.create_task(
                        self.dispatcher.dispatch(
                            request
                        ),
                        name=(
                            "nova-dispatch-"
                            + request.request_id
                        ),
                    )
                )

                response = (
                    await self._current_task
                )

                if (
                    self.response_handler
                    is not None
                ):
                    await self.response_handler(
                        request,
                        response,
                    )

            except asyncio.CancelledError:
                if shutdown_event.is_set():
                    raise

                logger.info(
                    "Запрос %s отменён.",
                    request.request_id,
                )

            except Exception:
                logger.exception(
                    "Ошибка RequestService для %s.",
                    request.request_id,
                )

            finally:
                self._current_task = None
                self._current_request = None
                self.coordinator.task_done(
                    request
                )

    async def cancel_current(self) -> bool:
        task = self._current_task

        if task is None or task.done():
            return False

        task.cancel()

        await asyncio.gather(
            task,
            return_exceptions=True,
        )

        return True
