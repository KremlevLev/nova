# modules/tools/registry.py

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

save_memory_tool = {
    "type": "function",
    "function": {
        "name": "save_to_memory",
        "description": "Запоминает важную информацию о пользователе (имена, предпочтения, факты), чтобы использовать в будущем.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Факт или информация для сохранения (например: 'Пользователь любит синий цвет')."}
            },
            "required": ["text"]
        }
    }
}

search_memory_tool = {
    "type": "function",
    "function": {
        "name": "search_in_memory",
        "description": "Ищет в долговременной памяти Nova информацию о пользователе по запросу.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос для извлечения фактов."}
            },
            "required": ["query"]
        }
    }
}

add_reminder_tool = {
    "type": "function",
    "function": {
        "name": "set_reminder",
        "description": "Устанавливает напоминание или будильник на определенное время или интервал.",
        "parameters": {
            "type": "object",
            "properties": {
                "time_str": {"type": "string", "description": "Время в формате '+минуты' (например '+15' для 15 минут) или в формате 'ЧЧ:ММ' (например '18:00')."},
                "message": {"type": "string", "description": "Текст напоминания (например: 'купить хлеб')."}
            },
            "required": ["time_str", "message"]
        }
    }
}

list_reminders_tool = {
    "type": "function",
    "function": {
        "name": "get_active_reminders",
        "description": "Возвращает список всех активных на данный момент напоминаний.",
        "parameters": {"type": "object", "properties": {}}
    }
}

execute_python_tool = {
    "type": "function",
    "function": {
        "name": "execute_python_code",
        "description": "Запускает произвольный Python-код (REPL). Позволяет совершать сложные математические расчеты, работу с файлами, автоматизацию интерфейса через pyautogui и глубокое взаимодействие с ОС. Требует подтверждения пользователя.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Полный исполняемый код Python для запуска."}
            },
            "required": ["code"]
        }
    }
}

mouse_click_tool = {
    "type": "function",
    "function": {
        "name": "mouse_click",
        "description": "Перемещает курсор мыши на координаты X, Y и совершает клик. Используется для точного нажатия кнопок на экране.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Координата X на экране (в пикселях)."},
                "y": {"type": "integer", "description": "Координата Y на экране (в пикселях)."},
                "click_type": {"type": "string", "enum": ["single", "double", "right"], "description": "Тип нажатия (single - обычный, double - двойной, right - правый)."}
            },
            "required": ["x", "y"]
        }
    }
}

press_hotkey_tool = {
    "type": "function",
    "function": {
        "name": "press_keyboard_combination",
        "description": "Нажимает заданную комбинацию клавиш (например, 'ctrl+n' для создания нового файла, 'ctrl+s' для сохранения, 'enter' для подтверждения, 'tab'). Используйте перед вводом текста в редакторы, чтобы создать документ.",
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Комбинация клавиш в нижнем регистре через знак плюс, например: 'ctrl+n' или 'enter'"}
            },
            "required": ["keys"]
        }
    }
}

create_project_tool = {
    "type": "function",
    "function": {
        "name": "create_workspace_project",
        "description": "Создает полноценную модульную структуру проекта (папки и файлы) на Рабочем столе за один шаг. Используйте этот инструмент, когда пользователь просит написать сложную программу, модульный код, развернуть инфраструктуру или бэкенд.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Имя корневой папки проекта на Рабочем столе (например, 'fastapi_kubernetes_app')."
                },
                "files": {
                    "type": "array",
                    "description": "Список всех файлов проекта с их относительными путями и кодом.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Относительный путь к файлу (например, 'app/main.py', 'Dockerfile', 'k8s/deployment.yaml')."},
                            "content": {"type": "string", "description": "Полный исходный код или текстовое содержимое файла."}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            "required": ["project_name", "files"]
        }
    }
}

scrape_webpage_tool = {
    "type": "function",
    "function": {
        "name": "scrape_webpage",
        "description": "Загружает веб-страницу по URL и извлекает из неё чистый текст. Используйте для подробного чтения статей, руководств и документации из интернета.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Полный адрес страницы, например: 'https://docs.pytest.org/'"}
            },
            "required": ["url"]
        }
    }
}

get_clipboard_tool = {
    "type": "function",
    "function": {
        "name": "get_clipboard_content",
        "description": "Возвращает текущий скопированный пользователем текст из буфера обмена Windows. Используйте, чтобы проанализировать логи ошибок или куски кода, скопированные пользователем.",
        "parameters": {"type": "object", "properties": {}}
    }
}

set_clipboard_tool = {
    "type": "function",
    "function": {
        "name": "set_clipboard_content",
        "description": "Копирует указанный текст в буфер обмена Windows пользователя.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Текст, который нужно положить в буфер обмена."}
            },
            "required": ["text"]
        }
    }
}

run_terminal_tool = {
    "type": "function",
    "function": {
        "name": "run_terminal_command",
        "description": "Выполняет консольную команду (CMD) в системе Windows в скрытом фоновом режиме и возвращает текстовый ответ. Позволяет проверять статус Git, запускать тесты, устанавливать библиотеки через pip. Требует подтверждения пользователя.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Полный текст консольной команды."}
            },
            "required": ["command"]
        }
    }
}

# Единый плоский список всех инструментов для Nova
ALL_TOOLS = [
    open_app_tool, 
    close_app_tool, 
    type_text_tool, 
    scrape_webpage_tool,
    get_clipboard_tool,
    set_clipboard_tool,
    run_terminal_tool,
    create_project_tool,
    get_time_tool, 
    change_volume_tool, 
    open_website_tool, 
    get_system_status_tool, 
    search_web_tavily_tool, 
    execute_cmd_tool, 
    manage_media_tool, 
    manage_windows_tool, 
    create_note_tool, 
    set_timer_tool, 
    control_smart_home_tool, 
    configure_assistant_tool, 
    save_memory_tool, 
    search_memory_tool, 
    add_reminder_tool, 
    list_reminders_tool, 
    execute_python_tool, 
    mouse_click_tool, 
    press_hotkey_tool
]