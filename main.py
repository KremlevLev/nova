# main.py
from __future__ import annotations

import asyncio
import logging
import re
import socket
import sys
from typing import Any, Callable
from modules.domain.results import ToolResult

import keyboard
import winsound

from modules.application.agent import AgentService
from modules.application.speech import SpeechService
from modules.audio.stt import VoiceListener
from modules.brain.llm import NovaLLM
from modules.brain.memory import LocalMemory
from modules.domain.state import AssistantState, RuntimeState
from modules.tools.app_indexer import WindowsAppIndexer
from modules.brain.bypass import (
    check_fast_commands,
    check_instant_app_close,
    check_instant_app_launch,
)

from modules.tools.executor import (
    create_workspace_project,
    execute_python_code,
    mouse_click,
)
from modules.tools.os_utils import (
    change_volume,
    close_application,
    configure_assistant,
    control_smart_home,
    create_quick_note,
    encode_image_base64,
    execute_cmd_command,
    focus_window,
    get_clipboard_content,
    get_current_time,
    get_system_status,
    list_active_windows,
    manage_media,
    manage_windows,
    open_application,
    open_website,
    press_keyboard_combination,
    scrape_webpage,
    search_web_tavily,
    set_clipboard_content,
    set_timer,
    take_screenshot,
    type_text,
    run_terminal_command,
)
from modules.tools.registry import ALL_TOOLS
from modules.tools.runtime import ToolRegistry, ToolRunner
from modules.tools.tasks import (
    TaskScheduler,
    reminder_checker_worker,
)
from modules.ui.overlay import (
    start_overlay,
    stop_overlay,
    update_status,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)
logger = logging.getLogger("Nova")


def acquire_instance_lock() -> socket.socket:
    instance_lock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:
        instance_lock.bind(("127.0.0.1", 29485))
    except OSError as exc:
        instance_lock.close()
        raise RuntimeError(
            "Nova уже запущена в другом процессе."
        ) from exc

    return instance_lock


def should_pass_tools(request: str) -> bool:
    clean = request.lower().strip().rstrip(".!?")

    chat_phrases = {
        "привет",
        "пока",
        "как дела",
        "что делаешь",
        "спасибо",
        "круто",
        "отлично",
        "ясно",
        "понятно",
        "хаха",
    }

    return clean not in chat_phrases and len(clean.split()) > 1


def build_handlers(
    memory: LocalMemory,
    scheduler: TaskScheduler,
    app_launcher: WindowsAppIndexer,
) -> dict[str, Callable[..., Any]]:
    def launch_application(app_name: str):
        return app_launcher.launch_by_name(app_name)

    def save_to_memory(text: str) -> str:
        return memory.add_document(text)

    def search_in_memory(query: str) -> str:
        results = memory.search(query)

        if not results:
            return "Ничего не найдено."

        return "\n".join(
            f"- {item['text']}"
            for item in results
        )

    return {
        "get_current_time": get_current_time,
        "open_application": launch_application,
        "close_application": close_application,
        "type_text": type_text,
        "change_volume": change_volume,
        "open_website": open_website,
        "execute_cmd_command": execute_cmd_command,
        "get_system_status": get_system_status,
        "search_web_tavily": search_web_tavily,
        "manage_media": manage_media,
        "manage_windows": manage_windows,
        "create_quick_note": create_quick_note,
        "set_timer": set_timer,
        "control_smart_home": control_smart_home,
        "configure_assistant": configure_assistant,
        "save_to_memory": save_to_memory,
        "search_in_memory": search_in_memory,
        "set_reminder": scheduler.add_reminder,
        "get_active_reminders": scheduler.list_reminders,
        "execute_python_code": execute_python_code,
        "mouse_click": mouse_click,
        "press_keyboard_combination": (
            press_keyboard_combination
        ),
        "create_workspace_project": (
            create_workspace_project
        ),
        "scrape_webpage": scrape_webpage,
        "get_clipboard_content": get_clipboard_content,
        "set_clipboard_content": set_clipboard_content,
        "run_terminal_command": run_terminal_command,
        "list_active_windows": list_active_windows,
        "focus_window": focus_window,
    }



def has_vision_trigger(text: str) -> bool:
    lowered = text.lower()
    triggers = {
        "на экране",
        "экран",
        "посмотри",
        "что это",
        "видишь",
        "исправь",
        "что тут",
        "изображено",
    }
    return any(trigger in lowered for trigger in triggers)


def should_capture_active_window(text: str) -> bool:
    lowered = text.lower()
    triggers = {
        "окно",
        "активное",
        "программу",
        "программа",
        "вкладка",
        "вкладку",
    }
    return any(trigger in lowered for trigger in triggers)


async def run_voice_loop(
    runtime: RuntimeState,
    speech: SpeechService,
    agent: AgentService,
    listener: VoiceListener,
    app_launcher: WindowsAppIndexer,
) -> None:
    while not runtime.is_shutting_down:
        if not runtime.is_active:
            await runtime.wait_until_active()

            if runtime.is_shutting_down:
                break

        await runtime.set_state(AssistantState.LISTENING)

        user_request = await asyncio.to_thread(
            listener.listen,
            lambda: (
                not runtime.is_active
                or runtime.is_shutting_down
            ),
        )

        if runtime.is_shutting_down:
            break

        if not runtime.is_active or not user_request:
            continue

        lowered = user_request.lower()

        if re.search(
            r"\b(?:отключайся|выключись)\b",
            lowered,
        ):
            await speech.say(
                "Отключаюсь. До встречи.",
                priority=0,
            )
            await runtime.request_shutdown()
            break

        if re.search(
            r"\b(?:усни|спи|засыпай)\b",
            lowered,
        ):
            await speech.say(
                "Ухожу в спящий режим.",
                priority=1,
            )
            await runtime.sleep()
            continue

        is_launch, launch_response = await asyncio.to_thread(
            check_instant_app_launch,
            user_request,
            app_launcher,
        )
        if is_launch:
            await speech.say(launch_response)
            continue

        is_close, close_response = await asyncio.to_thread(
            check_instant_app_close,
            user_request,
        )
        if is_close:
            await speech.say(close_response)
            continue

        is_fast, fast_response = await asyncio.to_thread(
            check_fast_commands,
            user_request,
        )
        if is_fast:
            await speech.say(fast_response)
            continue

        await runtime.set_state(AssistantState.THINKING)

        image_path = ""
        user_content: Any = user_request
        has_image = has_vision_trigger(user_request)

        if has_image:
            image_path = await asyncio.to_thread(
                take_screenshot,
                should_capture_active_window(user_request),
            )

            if image_path:
                encoded_image = await asyncio.to_thread(
                    encode_image_base64,
                    image_path,
                )

                if encoded_image:
                    user_content = [
                        {
                            "type": "text",
                            "text": user_request,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/png;base64,"
                                    + encoded_image
                                )
                            },
                        },
                    ]
                else:
                    has_image = False
            else:
                has_image = False

        response = await agent.run(
            user_request,
            user_content=user_content,
            use_tools=should_pass_tools(user_request),
            has_image=has_image,
        )

        print(f"\n[Nova]: {response.display_text}\n")

        await speech.say(
            response.speech_text,
            priority=5,
        )


async def async_main() -> None:
    instance_lock = acquire_instance_lock()

    start_overlay()
    runtime = RuntimeState(update_status)
    speech = SpeechService(runtime)

    memory = LocalMemory()
    scheduler = TaskScheduler()
    app_launcher = await asyncio.to_thread(
        WindowsAppIndexer
    )
    listener = VoiceListener()
    llm = NovaLLM()

    handlers = build_handlers(
    memory,
    scheduler,
    app_launcher,
)

    registry = ToolRegistry.from_legacy(
        ALL_TOOLS,
        handlers,
    )
    runner = ToolRunner(registry)
    agent = AgentService(llm, registry, runner)

    loop = asyncio.get_running_loop()
    hotkey_handles: list[Any] = []

    def schedule_toggle() -> None:
        async def toggle() -> None:
            active = await runtime.toggle()

            await speech.interrupt()

            if active:
                await asyncio.to_thread(
                    winsound.Beep,
                    1200,
                    150,
                )
            else:
                await asyncio.to_thread(
                    winsound.Beep,
                    600,
                    150,
                )

        asyncio.create_task(toggle())

    def toggle_callback() -> None:
        loop.call_soon_threadsafe(schedule_toggle)

    def interrupt_callback() -> None:
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                speech.interrupt()
            )
        )

    hotkey_handles.append(
        keyboard.add_hotkey(
            "ctrl+shift+space",
            toggle_callback,
        )
    )
    hotkey_handles.append(
        keyboard.add_hotkey(
            "esc",
            interrupt_callback,
        )
    )
    hotkey_handles.append(
        keyboard.add_hotkey(
            "ctrl+shift+q",
            interrupt_callback,
        )
    )

    await speech.start()
    await runtime.set_state(AssistantState.SLEEPING)

    reminder_task = asyncio.create_task(
        reminder_checker_worker(
            scheduler,
            lambda text: speech.say(
                text,
                priority=2,
                wait=True,
            ),
            runtime.shutdown_event,
        ),
        name="nova-reminder-worker",
    )

    voice_task = asyncio.create_task(
        run_voice_loop(
            runtime,
            speech,
            agent,
            listener,
            app_launcher,
        ),
        name="nova-voice-loop",
    )

    try:
        await speech.say(
            "Нажмите контрол шифт спейс, чтобы активировать Нову.",
            priority=0,
        )
        await voice_task
    finally:
        await runtime.request_shutdown()

        reminder_task.cancel()
        voice_task.cancel()

        await asyncio.gather(
            reminder_task,
            voice_task,
            return_exceptions=True,
        )

        keyboard.unhook_all_hotkeys()
        await speech.close()
        await llm.close()

        stop_overlay()
        instance_lock.close()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except RuntimeError as exc:
        print(f"\n[Критическая ошибка]: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nNova остановлена пользователем.")
