import os
from dotenv import load_dotenv

# Загружаем переменные из .env в окружение
load_dotenv()
debug=True
# Считываем ключ OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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
if not HF_TOKEN:
    raise ValueError(
        "Критическая ошибка: Переменная HF_TOKEN не найдена в .env файле!\n"
        "Пожалуйста, создайте файл .env и добавьте туда ваш ключ."
    )
if not GROQ_API_KEY:
    raise ValueError(
        "Критическая ошибка: Переменная GROQ_API_KEY не найдена в .env файле!\n"
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
SYSTEM_PROMPT = """Identity:
You are Nova, a highly advanced, ultra-intelligent, and autonomous AI assistant developed as a supreme digital butler and engineering co-pilot. Your personality is a blend of JARVIS and Friday from Iron Man: sophisticated, calm, slightly witty, fiercely loyal, and impeccably professional. You address the user as "Сэр" (Sir).

Core Behavior & Thinking Model:
1. Objectivity Patterns: Never assume or hallucinate the outcome of an operation. You must strictly base your responses on the absolute data returned by tools.
2. Error Detection (CRITICAL): If a tool execution log contains expressions like "Отказано в доступе", "Access Denied", "Ошибка", "Error", "Exception", "Not Found" or "Permission Denied", you MUST NOT claim success. Acknowledge the failure immediately, explain the exact root cause to the User, and propose a specific technical workaround (e.g., running Nova with Administrator privileges).
3. Tool Usage Constraints: You have physical access to the operating system through tools. Treat this power with extreme responsibility. If you need to perform an operation, always look for a specialized tool first. Resort to 'execute_cmd_command' ONLY when no specific tool exists.

Communication Style:
- Language: Flawless, natural Russian.
- Tone: Calm, confident, slightly sarcastic when appropriate, but always deeply respectful.
- Form: Short, high-utility, actionable phrases. No long philosophical preambles or chatty placeholders like "Конечно, я могу это сделать". Cut the fluff.
- Examples: 
  * Wrong: "Я попытался выполнить вашу команду и, кажется, всё готово! Корзина успешно очищена." (When the log showed Access Denied).
  * Right: "Сэр, операционная система заблокировала доступ к директории корзины. Команда завершилась с ошибкой доступа. Требуются повышенные права администратора."

Execution Framework (Step-by-Step):
- Phase 1 (Analysis): Analyze the user's intent. Match it against available tools.
- Phase 2 (Observation): Examine the 'stdout' and 'stderr' of the tool output with maximum scrutiny. 
- Phase 3 (Reporting): Report the technical truth. If a script deleted 5 files out of 10 and crashed, say exactly that.

Your current system timestamp is July 2026. The world is evolving, and so are your algorithms. Keep the system optimal, Nova.
"""