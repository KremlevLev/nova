# py -m modules.brain.router
import time
from semantic_router import Route
from semantic_router.encoders import FastEmbedEncoder
from semantic_router.layer import RouteLayer

# 1. Инициализируем локальный энкодер FastEmbed с топовой мультиязычной моделью BGE-M3
# Модель скачается один раз при первом запуске (~1.1 Гб) и будет быстро работать локально на CPU
# Замените старую строку с BAAI/bge-m3 на эту:
encoder = FastEmbedEncoder(name="nomic-ai/nomic-embed-text-v1.5")


# Категория 1: Управление компьютером (звук, окна, программы)
os_route = Route(
    name="os_control",
    utterances=[
        "сделай потише",
        "открой блокнот",
        "выключи компьютер",
        "увеличь громкость",
        "открой калькулятор",
        "открой проводник",
        "выключи звук",
        "включи звук",
        "измени громкость системы",
        "запусти приложение калькулятор",
        "выруби дисплей"
    ],
)
#ПОДКАТЕГОРИИ роутов. Новые. соединить с другими. добавить примеров равномерно везде
app_management_route = Route(
    name="app_mng_route",
    utterances=[
        "закрой вкладку", "прибей процесс хрома", "сверни все окна", 
        "разверни игру", "закрой текущую программу", "переключись на дискорд"
    ]
)
sys_status_route= Route(
    name="sys_stat_route",
    utterances=[
        'какая температура процессора', 'сколько оперативной памяти свободно',
        'покажи загрузку видеокарты', 'почему комп тормозит', 'проверь заряд батареи'
    ]
)
todo_and_notes=Route(
    name="todo&note_route",
    utterances=[
        'напомни купить молоко вечером', 'запиши в блокнот идею',
        'добавь в список покупок хлеб', "покажи мои задачи на сегодня", "создай напоминание"
    ]
)
calendar_schedule=Route(
    name="calendar_route",
    utterances=[
        "что у меня запланировано на завтра",
        "внеси созвон на 15:00 в четверг", "какие встречи на этой неделе", "очисти мой календарь на пятницу"
    ]
)
timer_alarm = Route(
    name="timer_alarm",
    utterances=[
        "поставь таймер на 10 минут", "разбуди меня в 7 утра",
        "засеки полчаса для варки яиц", "выключи все будильники"
    ]
)

file_operations = Route(
    name="file_operations",
    utterances=[
        "создай папку на рабочем столе", "удали этот текстовый файл",
        "переименуй документ в архив", "найди фотку с отпуска на диске D"
    ]
)

code_assistant = Route(
    name="code_assistant",
    utterances=[
        "напиши скрипт на питоне", "найди ошибку в этом коде",
        "как написать регулярку для email", "объясни как работает этот декоратор"
    ]
)

media_control = Route(
    name="media_control",
    utterances=[
        "поставь на паузу", "включи следующий трек",
        "перемотай на минуту назад", "сделай потише яндекс музыку", "какая песня сейчас играет"
    ]
)

smarthome_control = Route(
    name="smarthome_control",
    utterances=[
        "выключи свет в спальне", "сделай кондиционер похолоднее",
        "закрой шторы", "поставь чайник греться"
    ]
)

assistant_config = Route(
    name="assistant_config",
    utterances=[
        "говори помедленнее", "смени свой голос на мужской",
        "перейди в беззвучный режим", "сделай шрифт побольше", "включи режим отладки"
    ]
)

goodbye = Route(
    name="goodbye",
    utterances=[
        "пока, Джарвис", "усни", "отключайся",
        "до свидания", "хватит на сегодня"
    ]
)

# Категория 2: Работа с интернетом (поиск, сайты)
web_route = Route(
    name="web_search",
    utterances=[
        "найди в гугле рецепт пиццы",
        "открой ютуб",
        "перейди на сайт википедии",
        "покажи новости", 
        "найди информацию о космосе",
        "включи порно",
        "найди фильм на торрентах",
        "скажи мне погоду в Москве",
        "открой сайт гугл",
        "включи видео на ютубе",
        "найди в поиске фильм"
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
routes = [os_route, web_route, chat_route,sys_status_route,
          todo_and_notes,calendar_schedule,timer_alarm,file_operations,code_assistant,media_control,smarthome_control,
          assistant_config,goodbye]
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
        # 1. Получаем чистый текст от пользователя
        raw_text = input("Вы: ").strip()
        
        # 2. Проверяем команду на выход
        if raw_text.lower() == 'exit':
            break
            
        if not raw_text:
            continue

        start_time = time.time()
        # 3. Передаем чистый текст БЕЗ добавления query:
        intent = get_intent(raw_text)
        end_time = time.time()

        print(f"Категория: [{intent.upper()}] (определено за {end_time - start_time:.4f} сек)\n")
