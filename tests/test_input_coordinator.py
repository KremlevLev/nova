# tests/test_input_coordinator.py
from __future__ import annotations

import asyncio

from modules.input_hub.coordinator import (
    InputCoordinator,
)
from modules.input_hub.models import (
    UserRequest,
)


def test_submit_and_receive_request() -> None:
    async def scenario() -> None:
        coordinator = InputCoordinator()

        submitted = await coordinator.submit_text(
            "Привет"
        )

        assert submitted is not None
        assert coordinator.queued_requests == 1

        request = await coordinator.next_request()

        assert request is not None
        assert request.text == "Привет"

        coordinator.task_done(request)
        await coordinator.close()

    asyncio.run(scenario())


def test_empty_request_is_rejected() -> None:
    async def scenario() -> None:
        coordinator = InputCoordinator()

        request = await coordinator.submit_text(
            "   "
        )

        assert request is None
        assert coordinator.queued_requests == 0

        await coordinator.close()

    asyncio.run(scenario())


def test_duplicate_request_id_is_rejected() -> None:
    async def scenario() -> None:
        coordinator = InputCoordinator()

        request = UserRequest.from_text(
            "Тест"
        )

        first = await coordinator.submit(
            request
        )
        second = await coordinator.submit(
            request
        )

        assert first
        assert not second

        queued = await coordinator.next_request()
        coordinator.task_done(queued)

        await coordinator.close()

    asyncio.run(scenario())


def test_voice_request() -> None:
    async def scenario() -> None:
        coordinator = InputCoordinator()

        request = await coordinator.submit_voice(
            "Открой блокнот",
            wake_word=True,
        )

        assert request is not None
        assert request.is_voice

        queued = await coordinator.next_request()

        assert queued is request

        coordinator.task_done(queued)
        await coordinator.close()

    asyncio.run(scenario())
