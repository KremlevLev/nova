# modules/storage/artifacts.py
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.domain.results import ToolResult


logger = logging.getLogger("ArtifactStore")

ARTIFACTS_DIR = Path("data/artifacts")
MAX_ARTIFACT_SIZE = 50 * 1024 * 1024  # 50 MB
DEFAULT_TTL_HOURS = 24  # 24 часа


class ArtifactStore:
    """
    Хранилище артефактов.

    Артефакты — это большие результаты инструментов:
    - логи терминала;
    - diff файлов;
    - скриншоты;
    - сгенерированные проекты;
    - веб-страницы.

    Модель получает не полный текст, а ссылку на артефакт.
    """

    def __init__(
        self,
        *,
        artifacts_dir: str | Path = ARTIFACTS_DIR,
        ttl_hours: float = DEFAULT_TTL_HOURS,
    ) -> None:
        self.artifacts_dir = Path(
            artifacts_dir
        )
        self.artifacts_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.ttl_seconds = ttl_hours * 3600

    def _artifact_path(
        self,
        artifact_id: str,
    ) -> Path:
        return (
            self.artifacts_dir
            / f"{artifact_id}.artifact"
        )

    def _metadata_path(
        self,
        artifact_id: str,
    ) -> Path:
        return (
            self.artifacts_dir
            / f"{artifact_id}.meta"
        )

    def store(
        self,
        content: str,
        *,
        artifact_type: str = "text",
        source: str = "tool",
        metadata: dict[str, Any] | None = None,
        ttl_seconds: float | None = None,
    ) -> ToolResult:
        if len(content.encode("utf-8")) > MAX_ARTIFACT_SIZE:
            return ToolResult.failure(
                "ARTIFACT_TOO_LARGE",
                (
                    f"Артефакт слишком большой: "
                    f"{len(content)} байт "
                    f"(максимум {MAX_ARTIFACT_SIZE})"
                ),
            )

        artifact_id = (
            f"artifact_{uuid.uuid4().hex}"
        )

        content_hash = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

        resolved_ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else self.ttl_seconds
        )

        expires_at = (
            datetime.now(timezone.utc).timestamp()
            + resolved_ttl
        )

        meta = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "source": source,
            "size": len(content),
            "hash": content_hash,
            "created_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "expires_at": expires_at,
            "ttl_seconds": resolved_ttl,
            "metadata": metadata or {},
        }

        try:
            self._artifact_path(
                artifact_id
            ).write_text(
                content,
                encoding="utf-8",
            )

            self._metadata_path(
                artifact_id
            ).write_text(
                json.dumps(
                    meta,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        except OSError as exc:
            return ToolResult.failure(
                "ARTIFACT_STORE_FAILED",
                (
                    f"Не удалось сохранить артефакт: "
                    f"{exc}"
                ),
            )

        logger.info(
            "Артефакт сохранён: artifact_id=%s "
            "type=%s size=%s",
            artifact_id,
            artifact_type,
            len(content),
        )

        return ToolResult.ok(
            f"Артефакт сохранён: {artifact_id}",
            data={
                "artifact_id": artifact_id,
                "type": artifact_type,
                "size": len(content),
                "hash": content_hash,
                "expires_at": expires_at,
            },
        )

    def read(
        self,
        artifact_id: str,
    ) -> ToolResult:
        artifact_path = self._artifact_path(
            artifact_id
        )
        metadata_path = self._metadata_path(
            artifact_id
        )

        if not artifact_path.exists():
            return ToolResult.failure(
                "ARTIFACT_NOT_FOUND",
                (
                    f"Артефакт '{artifact_id}' "
                    f"не найден."
                ),
            )

        try:
            content = artifact_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            metadata = {}

            if metadata_path.exists():
                metadata = json.loads(
                    metadata_path.read_text(
                        encoding="utf-8"
                    )
                )

            return ToolResult.ok(
                f"Артефакт '{artifact_id}' прочитан.",
                data={
                    "artifact_id": artifact_id,
                    "content": content,
                    "metadata": metadata,
                    "size": len(content),
                },
            )

        except OSError as exc:
            return ToolResult.failure(
                "ARTIFACT_READ_FAILED",
                (
                    f"Не удалось прочитать артефакт: "
                    f"{exc}"
                ),
            )

    def delete(
        self,
        artifact_id: str,
    ) -> ToolResult:
        artifact_path = self._artifact_path(
            artifact_id
        )
        metadata_path = self._metadata_path(
            artifact_id
        )

        deleted = False

        if artifact_path.exists():
            artifact_path.unlink()
            deleted = True

        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        if not deleted:
            return ToolResult.failure(
                "ARTIFACT_NOT_FOUND",
                (
                    f"Артефакт '{artifact_id}' "
                    f"не найден."
                ),
            )

        return ToolResult.ok(
            f"Артефакт '{artifact_id}' удалён."
        )

    def cleanup_expired(self) -> int:
        """
        Удаляет все артефакты, срок жизни которых истёк.
        """
        now = time.time()
        removed = 0

        for meta_path in self.artifacts_dir.glob(
            "*.meta"
        ):
            try:
                metadata = json.loads(
                    meta_path.read_text(
                        encoding="utf-8"
                    )
                )

                expires_at = metadata.get(
                    "expires_at", 0
                )

                if now > expires_at:
                    artifact_id = metadata.get(
                        "artifact_id"
                    )

                    if artifact_id:
                        self.delete(
                            artifact_id
                        )
                        removed += 1

            except Exception:
                continue

        if removed > 0:
            logger.info(
                "Очищено устаревших артефактов: %s",
                removed,
            )

        return removed

    def list_artifacts(
        self,
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []

        for meta_path in self.artifacts_dir.glob(
            "*.meta"
        ):
            try:
                metadata = json.loads(
                    meta_path.read_text(
                        encoding="utf-8"
                    )
                )

                artifacts.append(metadata)

            except Exception:
                continue

        return artifacts
