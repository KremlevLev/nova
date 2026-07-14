# tests/test_input_models.py
from __future__ import annotations

from modules.input_hub.models import (
    AssistantProfile,
    Attachment,
    AttachmentType,
    InputMode,
    ModelSelectionMode,
    RequestSource,
    UserRequest,
)


def test_create_voice_request() -> None:
    request = UserRequest.from_voice(
        "Открой блокнот",
        confidence=1.5,
    )

    assert request.is_voice
    assert (
        request.source
        == RequestSource.VOICE_CONTINUOUS
    )
    assert (
        request.input_mode
        == InputMode.CONTINUOUS
    )
    assert request.speech_confidence == 1.0


def test_create_wake_word_request() -> None:
    request = UserRequest.from_voice(
        "Открой блокнот",
        wake_word=True,
    )

    assert (
        request.source
        == RequestSource.VOICE_WAKE_WORD
    )
    assert (
        request.input_mode
        == InputMode.WAKE_WORD
    )


def test_create_text_request() -> None:
    request = UserRequest.from_text(
        "Привет",
        profile=AssistantProfile.ENGINEER,
        model_mode=(
            ModelSelectionMode.SMART
        ),
    )

    assert not request.is_voice
    assert (
        request.source
        == RequestSource.DESKTOP_CHAT
    )
    assert (
        request.profile
        == AssistantProfile.ENGINEER
    )
    assert (
        request.model_mode
        == ModelSelectionMode.SMART
    )


def test_image_attachment_is_detected() -> None:
    request = UserRequest.from_text(
        "Что на изображении?",
        attachments=[
            Attachment(
                attachment_type=(
                    AttachmentType.IMAGE
                ),
                path="screen.png",
            )
        ],
    )

    assert request.has_attachments
    assert request.has_image


def test_empty_request() -> None:
    request = UserRequest.from_text("  ")

    assert request.is_empty


def test_request_serialization() -> None:
    request = UserRequest.from_text(
        "Тест",
        selected_model="test-model",
    )

    data = request.to_dict()

    assert data["text"] == "Тест"
    assert data["selected_model"] == (
        "test-model"
    )
    assert data["request_id"].startswith(
        "request_"
    )
