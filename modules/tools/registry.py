open_app_tool = {"type": "function", "function": {"name": "open_application", "description": "Открывает программу (блокнот, калькулятор, проводник).", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}}
close_app_tool = {"type": "function", "function": {"name": "close_application", "description": "Закрывает запущенную программу (блокнот, калькулятор, проводник, хром) по названию.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string", "description": "Название закрываемого приложения (блокнот, калькулятор, проводник, хром)."}}, "required": ["app_name"]}}}
type_text_tool = {"type": "function", "function": {"name": "type_text", "description": "Печатает текст в активное окно.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}
get_time_tool = {"type": "function", "function": {"name": "get_current_time", "description": "Возвращает текущую дату и время.", "parameters": {"type": "object", "properties": {}}}}
change_volume_tool = {"type": "function", "function": {"name": "change_volume", "description": "Изменяет громкость системы.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "'up', 'down' или 'mute'"}}, "required": ["action"]}}}
open_website_tool = {"type": "function", "function": {"name": "open_website", "description": "Просто открывает веб-сайт в браузере.", "parameters": {"type": "object", "properties": {"url_or_query": {"type": "string"}}, "required": ["url_or_query"]}}}
get_system_status_tool = {"type": "function", "function": {"name": "get_system_status", "description": "Возвращает инфу о ПК: 'ram', 'cpu' или 'battery'.", "parameters": {"type": "object", "properties": {"metric": {"type": "string"}}, "required": ["metric"]}}}
search_web_tavily_tool = {"type": "function", "function": {"name": "search_web_tavily", "description": "Ищет информацию в интернете.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
execute_cmd_tool = {"type": "function", "function": {"name": "execute_cmd_command", "description": "Выполняет системные команды: 'очистить корзину', 'спящий режим', 'выключить пк'.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}

manage_media_tool = {"type": "function", "function": {"name": "manage_media", "description": "Управление музыкой и видео.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "'play_pause', 'next', 'prev'"}}, "required": ["action"]}}}
manage_windows_tool = {"type": "function", "function": {"name": "manage_windows", "description": "Управление окнами Windows.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "'minimize_all' или 'close_current'"}}, "required": ["action"]}}}
create_note_tool = {"type": "function", "function": {"name": "create_quick_note", "description": "Сохраняет текст/идею/напоминание в текстовый файл на рабочем столе.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}
set_timer_tool = {"type": "function", "function": {"name": "set_timer", "description": "Устанавливает таймер на заданное количество минут.", "parameters": {"type": "object", "properties": {"minutes": {"type": "integer"}}, "required": ["minutes"]}}}

control_smart_home_tool = {
    "type": "function",
    "function": {
        "name": "control_smart_home",
        "description": "Управление устройствами умного дома (свет, кондиционер, чайник и др.).",
        "parameters": {
            "type": "object",
            "properties": {
                "device": {"type": "string", "description": "Название устройства (например, свет, кондей, чайник)."},
                "action": {"type": "string", "description": "Действие (например, включить, выключить, 22 градуса, максимум)."}
            },
            "required": ["device", "action"]
        }
    }
}

configure_assistant_tool = {
    "type": "function",
    "function": {
        "name": "configure_assistant",
        "description": "Изменение конфигурации или голоса ассистента (язык, скорость, тон).",
        "parameters": {
            "type": "object",
            "properties": {
                "setting": {"type": "string", "description": "Название настройки (например, голос, язык, скорость)."},
                "value": {"type": "string", "description": "Новое значение (например, мужской, английский, помедленнее)."}
            },
            "required": ["setting", "value"]
        }
    }
}

TOOL_REGISTRY = {
    "os_control": [open_app_tool, close_app_tool, type_text_tool, change_volume_tool, execute_cmd_tool],
    "sys_stat_route": [get_time_tool, get_system_status_tool], 
    "web_search": [open_website_tool, search_web_tavily_tool], 
    "file_operations": [execute_cmd_tool, open_app_tool],
    "media_control": [manage_media_tool, change_volume_tool],
    "app_mng_route": [manage_windows_tool, close_app_tool, execute_cmd_tool],
    "todo&note_route": [create_note_tool, get_time_tool],
    "timer_alarm": [set_timer_tool, get_time_tool],
    "code_assistant": [search_web_tavily_tool],
    "calendar_route": [create_note_tool, get_time_tool], 
    "smarthome_control": [control_smart_home_tool], 
    "assistant_config": [configure_assistant_tool], 
    "goodbye": [], 
    "chat": [], 
}