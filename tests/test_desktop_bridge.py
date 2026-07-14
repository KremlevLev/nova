# tests/test_desktop_bridge.py
from __future__ import annotations

import asyncio

from modules.domain.results import ToolResult
from modules.tools.permissions import (
    PermissionManager,
)
from modules.ui.core_bridge import (
    CoreDesktopBridge,
)
from modules.ui.desktop_protocol import (
    make_command,
)
from modules.input_hub.models import (
    UserRequest,
)


class FakeDesktop:
    def __init__(self) -> None:
        self.events = []

    def publish(
        self,
        event_type,
        payload=None,
    ):
        self.events.append(
            {
                "event_type": event_type,
                "payload": payload or {},
            }
        )
        return True

    def get_commands(self):
        return []



class FakeProcessManager:
    def __init__(self) -> None:
        self.stopped = []

    def list_processes(self):
        return ToolResult.ok(
            "Список.",
            data={
                "processes": [],
            },
        )

    def stop_process(
        self,
        process_id,
        force=False,
    ):
        self.stopped.append(
            (process_id, force)
        )

        return ToolResult.ok(
            "Остановлен."
        )


class FakeMemoryStore:
    def __init__(self) -> None:
        self.deleted = []
        self.cleared = False

    def search(
        self,
        query,
        limit=200,
    ):
        return [
            {
                "key": "name",
                "value": "Nova",
                "category": "test",
                "confidence": 1.0,
            }
        ]

    def delete(self, key):
        self.deleted.append(key)
        return True

    def clear_all(self):
        self.cleared = True
        return True


class FakeLLM:
    def provider_health(self):
        return {
            "keys": [],
            "local": {
                "llm_configured": False,
            },
        }


class FakeState:
    value = "СПИТ"


class FakeRuntime:
    state = FakeState()
    is_active = False
    is_shutting_down = False


def create_bridge():
    desktop = FakeDesktop()
    process_manager = FakeProcessManager()
    memory_store = FakeMemoryStore()

    bridge = CoreDesktopBridge(
        desktop=desktop,
        process_manager=process_manager,
        memory_store=memory_store,
        permission_manager=(
            PermissionManager()
        ),
        llm=FakeLLM(),
        runtime=FakeRuntime(),
    )

    return (
        bridge,
        desktop,
        process_manager,
        memory_store,
    )


def test_publish_snapshots() -> None:
    async def scenario() -> None:
        (
            bridge,
            desktop,
            _,
            _,
        ) = create_bridge()

        await bridge.publish_snapshots()

        event_types = {
            event["event_type"]
            for event in desktop.events
        }

        assert "runtime" in event_types
        assert "processes" in event_types
        assert "memories" in event_types
        assert "permissions" in event_types
        assert "models" in event_types

    asyncio.run(scenario())


def test_stop_process_command() -> None:
    async def scenario() -> None:
        (
            bridge,
            desktop,
            process_manager,
            _,
        ) = create_bridge()

        command = make_command(
            "stop_process",
            {
                "process_id": "proc-1",
                "force": True,
            },
        )

        await bridge.handle_command(
            command
        )

        assert process_manager.stopped == [
            ("proc-1", True)
        ]

        assert desktop.events[-1][
            "event_type"
        ] == "command_result"

    asyncio.run(scenario())


def test_delete_memory_command() -> None:
    async def scenario() -> None:
        (
            bridge,
            _,
            _,
            memory_store,
        ) = create_bridge()

        command = make_command(
            "delete_memory",
            {
                "key": "name",
            },
        )

        await bridge.handle_command(
            command
        )

        assert memory_store.deleted == [
            "name"
        ]

    asyncio.run(scenario())


def test_unknown_command_returns_error() -> None:
    async def scenario() -> None:
        (
            bridge,
            desktop,
            _,
            _,
        ) = create_bridge()

        command = make_command(
            "unknown_action"
        )

        await bridge.handle_command(
            command
        )

        result_event = desktop.events[-1]

        assert (
            result_event["event_type"]
            == "command_result"
        )
        assert not result_event[
            "payload"
        ]["success"]

    asyncio.run(scenario())
class FakeInputCoordinator:
    def __init__(self) -> None:
        self.requests = []

    async def submit_text(
        self,
        text,
        **kwargs,
    ):
        request = UserRequest.from_text(
            text,
            **{
                key: value
                for key, value in kwargs.items()
                if key in {
                    "source",
                    "profile",
                    "model_mode",
                    "selected_model",
                }
            },
        )

        self.requests.append(request)
        return request
def test_submit_user_request_command() -> None:
    async def scenario() -> None:
        (
            bridge,
            desktop,
            _,
            _,
        ) = create_bridge()

        coordinator = (
            FakeInputCoordinator()
        )

        bridge.input_coordinator = (
            coordinator
        )

        command = make_command(
            "submit_user_request",
            {
                "text": "Который час?",
                "profile": "assistant",
                "model_mode": "auto",
            },
        )

        await bridge.handle_command(
            command
        )

        assert len(
            coordinator.requests
        ) == 1

        assert (
            coordinator.requests[0].text
            == "Который час?"
        )

        assert (
            desktop.events[-1][
                "event_type"
            ]
            == "command_result"
        )

    asyncio.run(scenario())
