# Описание наших функций в формате OpenAI Tools API
NOVA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Возвращает текущую дату и точное время на компьютере пользователя. Вызывай, если человек спрашивает время, день недели или дату.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Открывает стандартное системное приложение Windows (блокнот, калькулятор, проводник).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Название приложения на русском языке, например: блокнот"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Печатает или вставляет переданный текст в текущее активное окно (например, в открытый Блокнот, браузер или чат). Вызывай эту функцию СРАЗУ ПОСЛЕ вызова open_application, если пользователь просит что-то написать.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Текст, который нужно напечатать."
                    }
                },
                "required": ["text"]
            }
        }
    }
]