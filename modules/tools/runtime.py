# modules/tools/runtime.py
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from core.config import TOOL_TIMEOUT_SECONDS
from modules.domain.results import ToolResult


logger = logging.getLogger("ToolRuntime")


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    WRITE = "write"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"


@dataclass(slots=True)
class RegisteredTool:
    name: str
    schema: dict[str, Any]
    handler: Callable[..., Any]
    risk: RiskLevel = RiskLevel.LOW
    timeout_seconds: float = TOOL_TIMEOUT_SECONDS


ERROR_MARKERS = (
    "ошибка",
    "не удалось",
    "отказ",
    "отклонено",
    "access denied",
    "permission denied",
    "exception",
    "not found",
    "не найден",
    "заблокирован",
    "сбой",
    "аварийная остановка",
)


RISK_BY_TOOL = {
    "get_current_time": RiskLevel.READ_ONLY,
    "get_system_status": RiskLevel.READ_ONLY,
    "search_in_memory": RiskLevel.READ_ONLY,
    "get_active_reminders": RiskLevel.READ_ONLY,
    "list_active_windows": RiskLevel.READ_ONLY,
    "search_web_tavily": RiskLevel.READ_ONLY,
    "scrape_webpage": RiskLevel.READ_ONLY,
    "get_clipboard_content": RiskLevel.READ_ONLY,

    "open_application": RiskLevel.LOW,
    "change_volume": RiskLevel.LOW,
    "manage_media": RiskLevel.LOW,
    "focus_window": RiskLevel.LOW,

    "type_text": RiskLevel.WRITE,
    "set_clipboard_content": RiskLevel.WRITE,
    "create_quick_note": RiskLevel.WRITE,
    "set_reminder": RiskLevel.WRITE,
    "save_to_memory": RiskLevel.WRITE,
    "create_workspace_project": RiskLevel.WRITE,

    "press_keyboard_combination": RiskLevel.EXECUTE,
    "mouse_click": RiskLevel.EXECUTE,
    "open_website": RiskLevel.EXECUTE,
    "run_terminal_command": RiskLevel.EXECUTE,
    "execute_python_code": RiskLevel.EXECUTE,

    "close_application": RiskLevel.DESTRUCTIVE,
    "manage_windows": RiskLevel.DESTRUCTIVE,
    "execute_cmd_command": RiskLevel.DESTRUCTIVE,
    "write_in_application": RiskLevel.WRITE,
}


def _looks_like_error(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in ERROR_MARKERS)

def strip_unknown_properties(
    value: Any,
    schema: dict[str, Any],
) -> Any:
    expected_type = schema.get("type")

    if expected_type == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})

        return {
            key: strip_unknown_properties(
                child_value,
                properties[key],
            )
            for key, child_value in value.items()
            if key in properties
        }

    if expected_type == "array" and isinstance(value, list):
        item_schema = schema.get("items", {})

        return [
            strip_unknown_properties(item, item_schema)
            for item in value
        ]

    return value


def adapt_legacy_result(value: Any) -> ToolResult:
    if isinstance(value, ToolResult):
        return value

    if isinstance(value, tuple) and len(value) == 2:
        success, message = value
        if isinstance(success, bool):
            if success:
                return ToolResult.ok(str(message))
            return ToolResult.failure(
                "LEGACY_TOOL_FAILED",
                str(message),
            )

    if value is None:
        return ToolResult.ok("Операция завершена без текстового результата.")

    message = str(value)

    if _looks_like_error(message):
        return ToolResult.failure(
            "LEGACY_TOOL_ERROR",
            message,
        )

    return ToolResult.ok(message)


def validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    path: str = "arguments",
) -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path} должен быть объектом."]

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for required_name in required:
            if required_name not in value:
                errors.append(
                    f"Отсутствует обязательный параметр '{required_name}'."
                )

        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(
                        f"Неизвестный параметр '{key}'."
                    )

        for key, child_value in value.items():
            child_schema = properties.get(key)
            if child_schema:
                errors.extend(
                    validate_json_schema(
                        child_value,
                        child_schema,
                        f"{path}.{key}",
                    )
                )

    elif expected_type == "array":
        if not isinstance(value, list):
            return [f"{path} должен быть массивом."]

        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            errors.append(
                f"{path} содержит больше {max_items} элементов."
            )

        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(
                    validate_json_schema(
                        item,
                        item_schema,
                        f"{path}[{index}]",
                    )
                )

    elif expected_type == "string":
        if not isinstance(value, str):
            return [f"{path} должен быть строкой."]

        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")

        if min_length is not None and len(value) < min_length:
            errors.append(
                f"{path} короче допустимого значения."
            )

        if max_length is not None and len(value) > max_length:
            errors.append(
                f"{path} превышает лимит {max_length} символов."
            )

    elif expected_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return [f"{path} должен быть целым числом."]

        minimum = schema.get("minimum")
        maximum = schema.get("maximum")

        if minimum is not None and value < minimum:
            errors.append(f"{path} должен быть не меньше {minimum}.")

        if maximum is not None and value > maximum:
            errors.append(f"{path} должен быть не больше {maximum}.")

    elif expected_type == "boolean":
        if not isinstance(value, bool):
            return [f"{path} должен быть логическим значением."]

    elif expected_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{path} должен быть числом."]

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        errors.append(
            f"{path} должен иметь одно из значений: {enum_values}."
        )

    return errors


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        schema: dict[str, Any],
        handler: Callable[..., Any],
        risk: RiskLevel | None = None,
        timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
    ) -> None:
        function_schema = schema.get("function", {})
        name = function_schema.get("name")

        if not isinstance(name, str) or not name:
            raise ValueError("Схема инструмента не содержит имя.")

        if name in self._tools:
            raise ValueError(
                f"Инструмент '{name}' зарегистрирован повторно."
            )

        parameters = function_schema.setdefault(
            "parameters",
            {
                "type": "object",
                "properties": {},
            },
        )
        parameters.setdefault("additionalProperties", False)

        self._tools[name] = RegisteredTool(
            name=name,
            schema=schema,
            handler=handler,
            risk=risk or RISK_BY_TOOL.get(name, RiskLevel.LOW),
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def from_legacy(
        cls,
        schemas: list[dict[str, Any]],
        handlers: dict[str, Callable[..., Any]],
    ) -> "ToolRegistry":
        registry = cls()

        schema_names = {
            item.get("function", {}).get("name")
            for item in schemas
        }
        handler_names = set(handlers)

        missing_handlers = schema_names - handler_names
        missing_schemas = handler_names - schema_names

        if missing_handlers:
            raise ValueError(
                "Для схем отсутствуют обработчики: "
                + ", ".join(sorted(missing_handlers))
            )

        if missing_schemas:
            raise ValueError(
                "Для обработчиков отсутствуют схемы: "
                + ", ".join(sorted(missing_schemas))
            )

        for schema in schemas:
            name = schema["function"]["name"]
            registry.register(
                schema=schema,
                handler=handlers[name],
            )

        return registry

    @property
    def names(self) -> set[str]:
        return set(self._tools)

    def schemas(
        self,
        names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if names is None:
            return [
                tool.schema
                for tool in self._tools.values()
            ]

        return [
            tool.schema
            for name, tool in self._tools.items()
            if name in names
        ]


    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)


class ToolRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self,
        tool_call: dict[str, Any],
    ) -> ToolResult:
        function = tool_call.get("function")
        if not isinstance(function, dict):
            return ToolResult.failure(
                "INVALID_TOOL_CALL",
                "Вызов инструмента не содержит объекта function.",
            )

        name = function.get("name")
        if not isinstance(name, str):
            return ToolResult.failure(
                "INVALID_TOOL_NAME",
                "Не указано имя инструмента.",
            )

        registered = self.registry.get(name)
        if registered is None:
            return ToolResult.failure(
                "TOOL_NOT_FOUND",
                f"Инструмент '{name}' не зарегистрирован.",
            )

        raw_arguments = function.get("arguments") or "{}"

        try:
            arguments = (
                raw_arguments
                if isinstance(raw_arguments, dict)
                else json.loads(raw_arguments)
            )
        except json.JSONDecodeError as exc:
            return ToolResult.failure(
                "INVALID_ARGUMENTS_JSON",
                f"Поврежден JSON аргументов '{name}': {exc}",
            )

        if not isinstance(arguments, dict):
            return ToolResult.failure(
                "INVALID_ARGUMENTS_TYPE",
                "Аргументы инструмента должны быть объектом.",
            )

        parameters_schema = registered.schema["function"].get(
            "parameters",
            {
                "type": "object",
                "properties": {},
            },
        )
        original_arguments = arguments
        arguments = strip_unknown_properties(
            arguments,
            parameters_schema,
        )

        removed_arguments = sorted(
            set(original_arguments) - set(arguments)
        )

        if removed_arguments:
            logger.warning(
                "Из вызова %s удалены неизвестные параметры: %s",
                name,
                removed_arguments,
            )

        validation_errors = validate_json_schema(
            arguments,
            parameters_schema,
        )
        if validation_errors:
            return ToolResult.failure(
                "ARGUMENT_VALIDATION_FAILED",
                " ".join(validation_errors),
                data={"errors": validation_errors},
            )

        started_at = time.perf_counter()

        try:
            if inspect.iscoroutinefunction(registered.handler):
                execution = registered.handler(**arguments)
            else:
                execution = asyncio.to_thread(
                    registered.handler,
                    **arguments,
                )

            raw_result = await asyncio.wait_for(
                execution,
                timeout=registered.timeout_seconds,
            )

            result = adapt_legacy_result(raw_result)
            result.data.setdefault(
                "duration_ms",
                round((time.perf_counter() - started_at) * 1000),
            )
            result.data.setdefault("risk", registered.risk.value)
            return result

        except asyncio.TimeoutError:
            return ToolResult.failure(
                "TOOL_TIMEOUT",
                (
                    f"Инструмент '{name}' превысил лимит "
                    f"{registered.timeout_seconds:.0f} секунд."
                ),
                retryable=True,
            )
        except Exception as exc:
            logger.exception(
                "Ошибка выполнения инструмента %s.",
                name,
            )
            return ToolResult.failure(
                "TOOL_EXECUTION_FAILED",
                f"Ошибка выполнения '{name}': {exc}",
            )
