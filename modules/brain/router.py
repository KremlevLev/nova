# py -m modules.brain.router
from semantic_router import Route
from semantic_router.encoders import HuggingFaceEncoder
from semantic_router.layer import RouteLayer
import time
from core.config import HF_TOKEN
HF_TOKEN = HF_TOKEN  # Используем токен из .env для доступа к HuggingFace API (если нужно)
# 1. Инициализируем локальный энкодер (он скачается один раз при первом запуске, весит ~100мб)
# Мы используем мультиязычную модель, чтобы она хорошо понимала русский
# Если библиотека semantic-router свежая, она принимает эти аргументы:
encoder = HuggingFaceEncoder(
    name="intfloat/multilingual-e5-small",
    query_instruction="query: ",
    passage_instruction="passage: "
)


# ==========================================
# 2. ВАША ЗАДАЧА: ЗАПОЛНИТЬ ПРИМЕРЫ (utterances)
# ==========================================

# Категория 1: Управление компьютером (звук, окна, программы)
os_route = Route(
    name="os_control",
    utterances=[
        "сделай потише","открой блокнот","выключи компьютер","увеличь громкость",
        "открой калькулятор","открой проводник","выключи звук","включи звук",
        "измени громкость системы", "запусти приложение калькулятор", "выруби дисплей"
    ],
)

# Категория 2: Работа с интернетом (поиск, сайты)
web_route = Route(
    name="web_search",
    utterances=[
        "найди в гугле рецепт пиццы",
        "открой ютуб",
        "перейди на сайт википедии",
        "покажи новости", 
        "найди информацию о космосе", "включи порно", "найди фильм на торрентах", "скажи мне погоду в Москве",
        "открой сайт гугл", "включи видео на ютубе", "найди в поиске фильм"
    ],
)

# Категория 3: Обычный чат (когда не нужно вызывать функции)
chat_route = Route(
    name="chat",
    utterances=[
        "привет, как дела?",
        "расскажи анекдот",
        "какой твой любимый цвет?",
        "напиши стих о природе",
        "мне сегодня как-то грустно",
        "представляешь, начальник на работе опять завалил задачами",
        "хочу просто поболтать о жизни, у меня куча мыслей",
        "я так сильно устал за эту неделю, сил вообще нет"
    ],
)

# ==========================================
# 3. Собираем всё в один слой маршрутизации
# ==========================================
routes = [os_route, web_route, chat_route]
route_layer = RouteLayer(encoder=encoder, routes=routes)

# Функция, которую мы будем вызывать из основного кода
def get_intent(user_text: str) -> str:
    """Возвращает название категории (os_control, web_search, chat) или None"""
    match = route_layer(user_text)
    return match.name if match else "chat" # По умолчанию считаем, что это чат

# --- ТЕСТОВЫЙ БЛОК (для проверки) ---
if __name__ == "__main__":
    print("Роутер запущен. Введите фразу (или 'exit' для выхода):")
    while True:
        # 1. Сначала получаем чистый текст от пользователя
        raw_text = input("Вы: ").strip()
        
        # 2. Сразу проверяем команду на выход, пока нет префиксов
        if raw_text.lower() == 'exit':
            break
            
        if not raw_text:
            continue

        # 3. Добавляем префикс query: для точности модели E5
        query_text = f"query: {raw_text}"

        start_time = time.time()
        # 4. Отправляем в вашу функцию, которая внутри вызывает route_layer
        intent = get_intent(query_text)
        end_time = time.time()

        print(f"Категория: [{intent.upper()}] (определено за {end_time - start_time:.4f} сек)\n")

