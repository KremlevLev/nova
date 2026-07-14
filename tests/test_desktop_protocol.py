# tests/test_desktop_protocol.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from modules.ui.desktop_protocol import (
    make_command,
    make_event,
    make_serializable,
    validate_command,
)


class ExampleState(StrEnum):
    READY = "ready"


@dataclass
class ExampleData:
    name: str
    path: Path


def test_make_event() -> None:
    event = make_event(
        "runtime",
        {
            "state": "СПИТ",
        },
    )

    assert event["event_type"] == "runtime"
    assert event["payload"]["state"] == "СПИТ"
    assert event["created_at"] > 0


def test_make_command() -> None:
    command = make_command(
        "refresh",
        {},
    )

    assert command["action"] == "refresh"
    assert command["command_id"].startswith(
        "ui_command_"
    )


def test_serializes_dataclass_path_and_enum() -> None:
    value = {
        "state": ExampleState.READY,
        "data": ExampleData(
            name="test",
            path=Path("C:/test"),
        ),
    }

    serialized = make_serializable(value)

    assert serialized["state"] == "ready"
    assert serialized["data"]["name"] == "test"
    assert isinstance(
        serialized["data"]["path"],
        str,
    )


def test_validate_valid_command() -> None:
    command = make_command(
        "refresh"
    )

    valid, error = validate_command(
        command
    )

    assert valid
    assert error is None


def test_validate_invalid_command() -> None:
    valid, error = validate_command(
        {
            "action": "refresh",
        }
    )

    assert not valid
    assert error is not None
