# tests/test_preferences.py
from __future__ import annotations

from modules.application.preferences import (
    PreferencesManager,
)
from modules.input_hub.models import (
    AssistantProfile,
    InputMode,
    ModelSelectionMode,
)


def test_default_preferences() -> None:
    manager = PreferencesManager()

    snapshot = manager.snapshot()

    assert (
        snapshot.input_mode
        == InputMode.WAKE_WORD
    )
    assert (
        snapshot.assistant_profile
        == AssistantProfile.ASSISTANT
    )
    assert (
        snapshot.model_mode
        == ModelSelectionMode.AUTO
    )
    assert snapshot.cloud_enabled
    assert snapshot.history_enabled


def test_privacy_mode_disables_cloud_and_history() -> None:
    manager = PreferencesManager()

    snapshot = manager.set_input_mode(
        InputMode.PRIVACY
    )

    assert not snapshot.cloud_enabled
    assert not snapshot.history_enabled


def test_private_profile_uses_local_model() -> None:
    manager = PreferencesManager()

    snapshot = manager.set_assistant_profile(
        AssistantProfile.PRIVATE_LOCAL
    )

    assert (
        snapshot.model_mode
        == ModelSelectionMode.LOCAL_ONLY
    )
    assert not snapshot.cloud_enabled


def test_pinned_model_requires_name() -> None:
    manager = PreferencesManager()

    try:
        manager.set_model_mode(
            ModelSelectionMode.PINNED
        )
    except ValueError as exc:
        assert "указать модель" in str(exc)
    else:
        raise AssertionError(
            "PINNED без модели не был отклонён."
        )


def test_pinned_model() -> None:
    manager = PreferencesManager()

    snapshot = manager.set_model_mode(
        ModelSelectionMode.PINNED,
        selected_model="test/model",
    )

    assert (
        snapshot.model_mode
        == ModelSelectionMode.PINNED
    )
    assert (
        snapshot.selected_model
        == "test/model"
    )
