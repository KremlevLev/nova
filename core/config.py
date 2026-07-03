import os
from dotenv import load_dotenv

# Загружаем переменные из .env в окружение
load_dotenv()
debug=True
# Считываем ключ OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
# Валидация: если забыли добавить ключ в .env, код сразу сообщит об этом
if not OPENROUTER_API_KEY:
    raise ValueError(
        "Критическая ошибка: Переменная OPENROUTER_API_KEY не найдена в .env файле!\n"
        "Пожалуйста, создайте файл .env и добавьте туда ваш ключ."
    )
if not TAVILY_API_KEY:
    raise ValueError(
        "Критическая ошибка: Переменная TAVILY_API_KEY не найдена в .env файле!\n"
        "Пожалуйста, создайте файл .env и добавьте туда ваш ключ."
    )
# Сюда же можно добавлять любые другие настройки проекта
BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-31b-it:free" #default model for general use
DEFAULT_MODEL_2 = "google/gemma-4-26b-a4b-it:free" #default model for general use
DEFAULT_MODEL_3 = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free" #default model for general use
DEFAULT_MODEL_4 = "openai/gpt-oss-20b:free" #default model for general use
CODE_MODEL = "poolside/laguna-m.1:free" #coding, math, reasoning
FALLBACK_MODEL = "openrouter/free" #fallback model for when primary models are unavailable
SMART_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free" #very smart, but slow
#SMART_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
#SMART_MODEL = "openrouter/free"

MODELS_LIST = [
    DEFAULT_MODEL, DEFAULT_MODEL_2, FALLBACK_MODEL
    ] #list of models to try in order
SYSTEM_PROMPT = "Ты — Nova, минималистичный и эффективный ИИ-ассистент для ОС Windows."