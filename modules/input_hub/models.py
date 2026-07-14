# modules/input_hub/models.py
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class RequestSource(StrEnum):
    VOICE_CONTINUOUS = "voice_continuous"
    VOICE_WAKE_WORD = "voice_wake_word"
    PUSH_TO_TALK = "push_to_talk"

    DESKTOP_CHAT = "desktop_chat"
    QUICK_INPUT = "quick_input"
    COMMAND_PALETTE = "command_palette"

    CLIPBOARD = "clipboard"
    CLI = "cli"
    API = "api"
    BACKGROUND_TASK = "background_task"


class InputMode(StrEnum):
    SLEEP = "sleep"
    WAKE_WORD = "wake_word"
    PUSH_TO_TALK = "push_to_talk"
    CONTINUOUS = "continuous"
    TEXT_ONLY = "text_only"
    PRIVACY = "privacy"


class AssistantProfile(StrEnum):
    SAFE = "safe"
    ASSISTANT = "assistant"
    ENGINEER = "engineer"
    AUTONOMOUS_TASK = "autonomous_task"
    PRIVATE_LOCAL = "private_local"


class ModelSelectionMode(StrEnum):
    AUTO = "auto"
    FAST = "fast"
    SMART = "smart"
    CODING = "coding"
    VISION = "vision"
    FREE_ONLY = "free_only"
    LOCAL_ONLY = "local_only"
    PINNED = "pinned"


class AttachmentType(StrEnum):
    FILE = "file"
    IMAGE = "image"
    SCREENSHOT = "screenshot"
    CLIPBOARD = "clipboard"
    ARTIFACT = "artifact"


@dataclass(slots=True)
class Attachment:
    attachment_type: AttachmentType
    path: str | None = None
    artifact_id: str | None = None
    mime_type: str | None = None
    display_name: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_type": (
                self.attachment_type.value
            ),
            "path": self.path,
            "artifact_id": self.artifact_id,
            "mime_type": self.mime_type,
            "display_name": self.display_name,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class UserRequest:
    request_id: str
    text: str
    source: RequestSource
    input_mode: InputMode

    created_at: float = field(
        default_factory=time.time
    )

    profile: AssistantProfile = (
        AssistantProfile.ASSISTANT
    )

    model_mode: ModelSelectionMode = (
        ModelSelectionMode.AUTO
    )
    selected_model: str | None = None

    attachments: list[Attachment] = field(
        default_factory=list
    )

    speech_confidence: float | None = None
    active_window_title: str | None = None
    session_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        text: str,
        *,
        source: RequestSource,
        input_mode: InputMode,
        profile: AssistantProfile = (
            AssistantProfile.ASSISTANT
        ),
        model_mode: ModelSelectionMode = (
            ModelSelectionMode.AUTO
        ),
        selected_model: str | None = None,
        attachments: list[Attachment] | None = None,
        speech_confidence: float | None = None,
        active_window_title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "UserRequest":
        clean_text = str(text).strip()

        if speech_confidence is not None:
            speech_confidence = max(
                0.0,
                min(1.0, speech_confidence),
            )

        return cls(
            request_id=(
                f"request_{uuid.uuid4().hex}"
            ),
            text=clean_text,
            source=source,
            input_mode=input_mode,
            profile=profile,
            model_mode=model_mode,
            selected_model=selected_model,
            attachments=attachments or [],
            speech_confidence=speech_confidence,
            active_window_title=(
                active_window_title
            ),
            session_id=session_id,
            metadata=metadata or {},
        )

    @classmethod
    def from_voice(
        cls,
        text: str,
        *,
        wake_word: bool = False,
        confidence: float | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "UserRequest":
        return cls.create(
            text,
            source=(
                RequestSource.VOICE_WAKE_WORD
                if wake_word
                else RequestSource.VOICE_CONTINUOUS
            ),
            input_mode=(
                InputMode.WAKE_WORD
                if wake_word
                else InputMode.CONTINUOUS
            ),
            speech_confidence=confidence,
            session_id=session_id,
            metadata=metadata,
        )

    @classmethod
    def from_text(
        cls,
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
        metadata: dict[str, Any] | None = None,
    ) -> "UserRequest":
        return cls.create(
            text,
            source=source,
            input_mode=InputMode.TEXT_ONLY,
            profile=profile,
            model_mode=model_mode,
            selected_model=selected_model,
            attachments=attachments,
            session_id=session_id,
            metadata=metadata,
        )

    @property
    def has_attachments(self) -> bool:
        return bool(self.attachments)

    @property
    def has_image(self) -> bool:
        return any(
            attachment.attachment_type
            in {
                AttachmentType.IMAGE,
                AttachmentType.SCREENSHOT,
            }
            for attachment in self.attachments
        )

    @property
    def is_voice(self) -> bool:
        return self.source in {
            RequestSource.VOICE_CONTINUOUS,
            RequestSource.VOICE_WAKE_WORD,
            RequestSource.PUSH_TO_TALK,
        }

    @property
    def is_empty(self) -> bool:
        return (
            not self.text.strip()
            and not self.attachments
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "text": self.text,
            "source": self.source.value,
            "input_mode": self.input_mode.value,
            "created_at": self.created_at,
            "profile": self.profile.value,
            "model_mode": self.model_mode.value,
            "selected_model": self.selected_model,
            "attachments": [
                attachment.to_dict()
                for attachment in self.attachments
            ],
            "speech_confidence": (
                self.speech_confidence
            ),
            "active_window_title": (
                self.active_window_title
            ),
            "session_id": self.session_id,
            "metadata": self.metadata,
        }
