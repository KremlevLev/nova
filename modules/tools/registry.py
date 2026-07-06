# --- СТАРЫЕ ИНСТРУМЕНТЫ (оставляем) ---
open_app_tool = {
    "type": "function", "function": {"name": "open_application", "description": "Открывает программу (блокнот, калькулятор, проводник).", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}
}
type_text_tool = {
    "type": "function", "function": {"name": "type_text", "description": "Печатает текст в активное окно.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
}
get_time_tool = {
    "type": "function", "function": {"name": "get_current_time", "description": "Возвращает текущую дату и время.", "parameters": {"type": "object", "properties": {}}}
}
change_volume_tool = {
    "type": "function", "function": {"name": "change_volume", "description": "Изменяет громкость системы.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "description": "'up', 'down' или 'mute'"}}, "required": ["action"]}}
}
open_website_tool = {
    "type": "function", "function": {"name": "open_website", "description": "Просто открывает веб-сайт в браузере (не ищет информацию, а именно открывает вкладку).", "parameters": {"type": "object", "properties": {"url_or_query": {"type": "string"}}, "required": ["url_or_query"]}}
}

# --- НОВЫЕ ИНСТРУМЕНТЫ ---
get_system_status_tool = {
    "type": "function",
    "function": {
        "name": "get_system_status",
        "description": "Возвращает информацию о ресурсах ПК: оперативная память, процессор или заряд батареи.",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Какую метрику проверить: 'ram' (память), 'cpu' (процессор) или 'battery' (батарея)."
                }
            },
            "required": ["metric"]
        }
    }
}

search_web_tavily_tool = {
    "type": "function",
    "function": {
        "name": "search_web_tavily",
        "description": "Ищет информацию в интернете и читает статьи. Вызывай это, чтобы ответить на вопросы о погоде, новостях, фактах или если не знаешь ответа.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос (например: 'погода в москве сегодня' или 'кто такой Илон Маск')."
                }
            },
            "required": ["query"]
        }
    }
}

execute_cmd_tool = {
    "type": "function",
    "function": {
        "name": "execute_cmd_command",
        "description": "Выполняет системные команды: 'очистить корзину', 'спящий режим', 'выключить пк', 'заблокировать пк'.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Точное название команды из списка."
                }
            },
            "required": ["command"]
        }
    }
}

# --- КАРТА ИНСТРУМЕНТОВ ДЛЯ РОУТЕРА ---
TOOL_REGISTRY = {
    "os_control": [open_app_tool, type_text_tool, change_volume_tool, execute_cmd_tool],
    "sys_stat_route": [get_time_tool, get_system_status_tool], 
    "web_search": [open_website_tool, search_web_tavily_tool], 
    "file_operations": [execute_cmd_tool], # Добавили сюда корзину
    "chat": [], # Режим болтовни: инструментов нет
}