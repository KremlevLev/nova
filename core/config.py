import os
from dotenv import load_dotenv

# Загружаем переменные из .env в окружение
load_dotenv()

# Считываем ключ OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Валидация: если забыли добавить ключ в .env, код сразу сообщит об этом
if not OPENROUTER_API_KEY:
    raise ValueError(
        "Критическая ошибка: Переменная OPENROUTER_API_KEY не найдена в .env файле!\n"
        "Пожалуйста, создайте файл .env и добавьте туда ваш ключ."
    )

# Сюда же можно добавлять любые другие настройки проекта
BASE_URL = "https://openrouter.ai"
DEFAULT_MODEL = "google/gemini-2.5-flash"
