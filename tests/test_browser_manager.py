# tests/test_browser_manager.py
from __future__ import annotations

import asyncio

from modules.browser.manager import (
    BrowserManager,
    validate_browser_url,
    validate_selector,
)


def test_public_https_url_is_allowed() -> None:
    valid, normalized, error = (
        validate_browser_url(
            "https://example.com"
        )
    )

    assert valid
    assert normalized == "https://example.com"
    assert error is None


def test_url_without_scheme_gets_https() -> None:
    valid, normalized, error = (
        validate_browser_url(
            "example.com"
        )
    )

    assert valid
    assert normalized == "https://example.com"


def test_localhost_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "http://localhost:8000"
    )

    assert not valid
    assert error is not None


def test_loopback_ip_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "http://127.0.0.1"
    )

    assert not valid
    assert error is not None


def test_private_ip_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "http://192.168.1.10"
    )

    assert not valid
    assert error is not None


def test_file_scheme_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "file:///C:/Windows/system.ini"
    )

    assert not valid
    assert error is not None


def test_javascript_scheme_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "javascript:alert(1)"
    )

    assert not valid
    assert error is not None

def test_data_scheme_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "data:text/html,<h1>test</h1>"
    )

    assert not valid
    assert error is not None


def test_file_scheme_is_blocked_without_slashes() -> None:
    valid, _, error = validate_browser_url(
        "file:C:/Windows/system.ini"
    )

    assert not valid
    assert error is not None


def test_ftp_scheme_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "ftp://example.com/file.txt"
    )

    assert not valid
    assert error is not None


def test_local_subdomain_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "http://service.local"
    )

    assert not valid
    assert error is not None


def test_url_credentials_are_blocked() -> None:
    valid, _, error = validate_browser_url(
        "https://user:password@example.com"
    )

    assert not valid
    assert error is not None


def test_protocol_relative_public_url_is_allowed() -> None:
    valid, normalized, error = (
        validate_browser_url(
            "//example.com/page"
        )
    )

    assert valid
    assert normalized == "https://example.com/page"
    assert error is None


def test_invalid_port_is_blocked() -> None:
    valid, _, error = validate_browser_url(
        "https://example.com:99999"
    )

    assert not valid
    assert error is not None


def test_valid_selector() -> None:
    valid, error = validate_selector(
        "button[type='submit']"
    )

    assert valid
    assert error is None


def test_empty_selector_is_rejected() -> None:
    valid, error = validate_selector("")

    assert not valid
    assert error is not None


def test_browser_status_before_start() -> None:
    async def scenario() -> None:
        manager = BrowserManager(
            headless=True
        )

        result = await manager.status()

        assert result.success
        assert result.data["started"] is False

        await manager.close()

    asyncio.run(scenario())
