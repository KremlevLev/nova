# main.py
from __future__ import annotations
from modules.windows.process_manager import (
    ProcessManager
)
from modules.tools.registry import (
    ALL_TOOLS,
    planning_tools,
    background_plan_tools,
)

from modules.agent.background_plans import (
    BackgroundPlanManager,
)
from modules.storage.artifacts import (
    ArtifactStore,
)
from modules.storage.database import Database
from modules.storage.conversations import (
    ConversationStore,
)
from modules.storage.memories import MemoryStore
from modules.tools.registry import (
    ALL_TOOLS,
    planning_tools,
)

from modules.windows.git_tools import (
    git_status,
    git_diff,
    git_log,
    git_commit,
    git_branch,
)
from modules.agent.plan_service import (
    PlanService,
)
from modules.browser.manager import (
    BrowserManager,
)
from modules.windows.project_inspector import (
    inspect_project,
)
from modules.windows.filesystem import (
    read_text_file,
    write_text_file,
    apply_text_patch,
    get_file_diff,
    search_files,
    rollback_file,
)
import asyncio
import logging
import re
import socket
import sys
from typing import Any, Callable
from modules.domain.results import ToolResult
from modules.tools.skills import WindowsSkills
from modules.domain.windows_context import WindowsContext

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
    open_website,
    press_keyboard_combination,
    scrape_webpage,
    search_web_tavily,
    set_clipboard_content,
    set_timer,
    take_screenshot,
    type_text,
    run_terminal_command,
    get_active_window_title,
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

process_manager = ProcessManager()
database = Database()
conversation_store = ConversationStore(
    database
)
memory_store = MemoryStore(database)
artifact_store = ArtifactStore()

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
    process_manager: ProcessManager,
    memory_store: MemoryStore,
    artifact_store: ArtifactStore,
    browser_manager: BrowserManager,
) -> dict[str, Callable[..., Any]]:
    
    windows_skills = WindowsSkills(
        app_launcher=app_launcher,
        list_windows=list_active_windows,
        focus_window=focus_window,
        press_hotkey=press_keyboard_combination,
        type_text=type_text,
        get_active_window_title=get_active_window_title,
    )
    def store_artifact_handler(
        content: str,
        artifact_type: str = "text",
    ) -> ToolResult:
        return artifact_store.store(
            content,
            artifact_type=artifact_type,
        )


    def read_artifact_handler(
        artifact_id: str,
    ) -> ToolResult:
        return artifact_store.read(artifact_id)


    def delete_artifact_handler(
        artifact_id: str,
    ) -> ToolResult:
        return artifact_store.delete(artifact_id)

    def save_memory_handler(
        key: str,
        value: str,
        category: str = "general",
    ) -> str:
        memory_store.save(
            key,
            value,
            category=category,
        )
        return f"Запомнила: {key} = {value}"


    def search_memory_handler(
        query: str,
    ) -> str:
        results = memory_store.search(query)

        if not results:
            return "Ничего не найдено."

        return "\n".join(
            f"- {r['key']}: {r['value']}"
            for r in results
        )


    def delete_memory_handler(
        key: str,
    ) -> str:
        memory_store.delete(key)
        return f"Удалила из памяти: {key}"


    def clear_all_memories_handler() -> str:
        memory_store.clear_all()
        return "Вся память очищена."


    def start_process_handler(
        command: list[str],
        label: str | None = None,
        cwd: str | None = None,
    ) -> ToolResult:
        return process_manager.start_process(
            command,
            label=label,
            cwd=cwd,
        )

    def get_process_status_handler(
        process_id: str,
    ) -> ToolResult:
        return process_manager.get_process_status(
            process_id
        )

    def read_process_output_handler(
        process_id: str,
        max_lines: int = 100,
        stream: str = "stdout",
    ) -> ToolResult:
        return process_manager.read_process_output(
            process_id,
            max_lines=max_lines,
            stream=stream,
        )

    def stop_process_handler(
        process_id: str,
        force: bool = False,
    ) -> ToolResult:
        return process_manager.stop_process(
            process_id,
            force=force,
        )

    def list_processes_handler() -> ToolResult:
        return process_manager.list_processes()

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
        "write_in_application": (
            windows_skills.write_in_application),
        "scrape_webpage": scrape_webpage,
        "get_clipboard_content": get_clipboard_content,
        "set_clipboard_content": set_clipboard_content,
        "run_terminal_command": run_terminal_command,
        "list_active_windows": list_active_windows,
        "focus_window": focus_window,
        "start_process": start_process_handler,
        "get_process_status": (
            get_process_status_handler
        ),
        "read_process_output": (
            read_process_output_handler
        ),
        "stop_process": stop_process_handler,
        "list_processes": (
            list_processes_handler
        ),
        "read_text_file": read_text_file,
        "write_text_file": write_text_file,
        "apply_text_patch": apply_text_patch,
        "get_file_diff": get_file_diff,
        "search_files": search_files,
        "rollback_file": rollback_file,
        "git_status": git_status,
        "git_diff": git_diff,
        "git_log": git_log,
        "git_commit": git_commit,
        "git_branch": git_branch,
        "inspect_project": inspect_project,
        "save_memory": save_memory_handler,
        "search_memory": search_memory_handler,
        "delete_memory": delete_memory_handler,
        "clear_all_memories": (
            clear_all_memories_handler
        ),
                "store_artifact": store_artifact_handler,
        "read_artifact": read_artifact_handler,
        "delete_artifact": delete_artifact_handler,
        "browser_start": (
            browser_manager.start
        ),
        "browser_open_url": (
            browser_manager.open_url
        ),
        "browser_get_page_text": (
            browser_manager.get_page_text
        ),
        "browser_click": (
            browser_manager.click
        ),
        "browser_fill": (
            browser_manager.fill
        ),
        "browser_screenshot": (
            browser_manager.screenshot
        ),
        "browser_status": (
            browser_manager.status
        ),
        "browser_close": (
            browser_manager.close
        ),

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
    windows_context: WindowsContext,
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
            # Извлекаем имя приложения из исходной команды.
            lowered_request = user_request.lower().strip()

            for launch_verb in (
                "открой",
                "включи",
                "запусти",
                "запуск",
            ):
                if lowered_request.startswith(
                    launch_verb + " "
                ):
                    application_name = user_request[
                        len(launch_verb):
                    ].strip(" .,!?:;")

                    windows_context.set_application(
                        application_name
                    )
                    break
                
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
        resolved_request = (
            windows_context.resolve_reference(
                user_request
            )
        )

        response = await agent.run(
            resolved_request,
            user_content=(
                user_content
                if user_content != user_request
                else resolved_request
            ),
            use_tools=should_pass_tools(resolved_request),
            has_image=has_image,
        )


        print(f"\n[Nova]: {response.display_text}\n")

        try:
            await speech.say(
                response.speech_text,
                priority=5,
            )
        except asyncio.CancelledError:
            if runtime.is_shutting_down:
                raise
            
            logger.info(
                "Озвучивание ответа прервано пользователем."
            )



async def async_main() -> None:
    instance_lock = acquire_instance_lock()
    windows_context = WindowsContext()
    start_overlay()
    runtime = RuntimeState(update_status)
    speech = SpeechService(runtime)
    browser_manager = BrowserManager(
    headless=False
)

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
        process_manager,
        memory_store,
        artifact_store,
        browser_manager,
    )

    planning_tool_names = {
        tool["function"]["name"]
        for tool in planning_tools
    }

    deferred_tool_names = {
    tool["function"]["name"]
    for tool in (
        planning_tools
        + background_plan_tools
    )
}

    base_tool_schemas = [
    tool
    for tool in ALL_TOOLS
    if tool["function"]["name"]
    not in deferred_tool_names
]
    for schema in background_plan_tools:
        tool_name = schema["function"]["name"]

        registry.register(
        schema=schema,
        handler=background_plan_handlers[
            tool_name
        ],
    )


    registry = ToolRegistry.from_legacy(
        base_tool_schemas,
        handlers,
    )

    runner = ToolRunner(registry)

    plan_service = PlanService(
        registry=registry,
        runner=runner,
    )
    background_plan_manager = (
    BackgroundPlanManager(
        plan_service
    )
)

    plan_handlers = {
        "execute_plan": (
            plan_service.execute_plan
        ),
        "get_plan_status": (
            plan_service.get_plan_status
        ),
        "cancel_plan": (
            plan_service.cancel_plan
        ),
    }
    background_plan_handlers = {
    "start_background_plan": (
        background_plan_manager.start_plan
    ),
    "get_background_plan_status": (
        background_plan_manager.get_status
    ),
    "list_background_plans": (
        background_plan_manager.list_plans
    ),
    "cancel_background_plan": (
        background_plan_manager.cancel_plan
    ),
}

    for schema in planning_tools:
        tool_name = schema["function"]["name"]

        registry.register(
            schema=schema,
            handler=plan_handlers[tool_name],
        )

    agent = AgentService(
        llm,
        registry,
        runner,
    )


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
            windows_context,
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
