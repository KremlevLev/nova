# tests/test_artifacts.py
from __future__ import annotations

import time
from pathlib import Path

from modules.storage.artifacts import (
    ArtifactStore,
)


def test_store_and_read_artifact() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=24,
    )

    result = store.store(
        "Hello, Nova!",
        artifact_type="text",
        source="test",
    )

    assert result.success
    artifact_id = result.data["artifact_id"]

    read_result = store.read(artifact_id)

    assert read_result.success
    assert (
        read_result.data["content"]
        == "Hello, Nova!"
    )

    store.delete(artifact_id)


def test_store_large_artifact() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=24,
    )

    large_content = "A" * 100_000

    result = store.store(
        large_content,
        artifact_type="text",
    )

    assert result.success
    assert result.data["size"] == 100_000

    store.delete(result.data["artifact_id"])


def test_read_nonexistent_artifact() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=24,
    )

    result = store.read("nonexistent_id")

    assert not result.success
    assert result.code == "ARTIFACT_NOT_FOUND"


def test_delete_nonexistent_artifact() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=24,
    )

    result = store.delete("nonexistent_id")

    assert not result.success
    assert result.code == "ARTIFACT_NOT_FOUND"


def test_cleanup_expired_artifacts() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=0,  # Истекает сразу.
    )

    result = store.store(
        "Temporary content",
        artifact_type="text",
    )

    assert result.success

    time.sleep(0.1)

    removed = store.cleanup_expired()

    assert removed >= 1


def test_list_artifacts() -> None:
    store = ArtifactStore(
        artifacts_dir="data/test_artifacts",
        ttl_hours=24,
    )

    store.store(
        "First",
        artifact_type="text",
    )
    store.store(
        "Second",
        artifact_type="text",
    )

    artifacts = store.list_artifacts()

    assert len(artifacts) >= 2

    for artifact in artifacts:
        store.delete(
            artifact["artifact_id"]
        )
