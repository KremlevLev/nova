# modules/brain/router.py
from semantic_router import Route
from semantic_router.encoders import FastEmbedEncoder
from semantic_router.layer import RouteLayer

encoder = FastEmbedEncoder(name="intfloat/multilingual-e5-large")

# Объединяем os_control и app_mng_route в один мощный роут
system_control_route = Route(
    name="os_control",  # Оставляем имя os_control для совместимости с TOOL_REGISTRY
    utterances=[
        "сделай потише", "открой блокнот", "выключи компьютер",
        "увеличь громкость", "открой калькулятор", "выруби дисплей",
        "сделай так чтоб я ничего не слышал", "запусти считалку", "погаси экран",
        "закрой вкладку", "прибей процесс хрома", "сверни все окна", 
        "разверни игру", "закрой текущую программу", "переключись на дискорд",
        "открой проводник", "запусти проводник", "включи проводник", "открой мои документы"
    ],
)

sys_status_route = Route(
    name="sys_stat_route",
    utterances=[
        'какая температура процессора', 'сколько оперативной памяти свободно',
        'покажи загрузку видеокарты', 'почему комп тормозит', 
        'че по ресурсам компик не закипает', 'сколько оперативы свободно'
    ]
)

calendar_schedule = Route(
    name="calendar_route",
    utterances=[
        "что у меня запланировано на завтра", "внеси созвон на 15:00", 
        "ебани мне встречу", "забей в график созвон с Саней"
    ]
)

web_route = Route(
    name="web_search",
    utterances=[
        "найди в гугле рецепт пиццы", "открой ютуб в браузере", "покажи новости", 
        "включи порно", "гей порно", "че там по погоде на завтра", "где сейчас идет война",
        "погугли информацию про", "найди статью в интернете"
    ],
)

chat_route = Route(
    name="chat",
    utterances=[
        "привет, как дела?", "расскажи анекдот", "какой твой любимый цвет?",
        "слышь ты еблан", "жир", "че делаешь братуха", "ебани мне какую-нибудь историю"
    ],
)

todo_and_notes = Route(
    name="todo&note_route", 
    utterances=[
        'напомни купить молоко вечером', 'запиши в блокнот идею', 
        'добавь в список покупок хлеб', "покажи мои задачи на сегодня", "создай напоминание"
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
        "переименуй документ в архив", "найди фотку с отпуска на диске D", 
        "удали тот мусорный txt файл из загрузок"
    ]
)

code_assistant = Route(
    name="code_assistant", 
    utterances=[
        "напиши скрипт на питоне", "найди ошибку в этом коде", 
        "оптимизируй эту функцию", "почему у меня падает ошибка индиката ин декс аут оф рендж"
    ]
)

media_control = Route(
    name="media_control", 
    utterances=[
        "поставь на паузу", "включи следующий трек", 
        "перемотай на минуту назад", "вруби следующий трек"
    ]
)

smarthome_control = Route(
    name="smarthome_control", 
    utterances=[
        "выключи свет в спальне", "сделай кондиционер похолоднее", 
        "включи свет в гостиной", "поставь чайник на максимум", "вруби кондей на 22 градуса"
    ]
)

assistant_config = Route(
    name="assistant_config", 
    utterances=[
        "говори помедленнее", "смени свой голос на мужской", 
        "смени язык на английский", "сделай свой голос погрубее"
    ]
)

goodbye = Route(
    name="goodbye", 
    utterances=[
        "пока, Джарвис", "усни", "отключайся", 
        "ладно давай пока", "сваливаю в туман до завтра"
    ]
)

# Собираем очищенный список роутов (убрали дублирующий app_management_route)
routes = [
    system_control_route, web_route, chat_route, sys_status_route, 
    todo_and_notes, calendar_schedule, timer_alarm, file_operations, 
    code_assistant, media_control, smarthome_control, assistant_config, goodbye
]
route_layer = RouteLayer(encoder=encoder, routes=routes)

def get_intent(user_text: str) -> list[str]:
    """Умный роутер: возвращает список из 1-2 нужных категорий для LLM"""
    match = route_layer(user_text)
    
    if match and hasattr(match, 'name') and match.name:
        if match.name == "chat":
            return ["chat"]
        return [match.name, "chat"]
    
    return ["chat", "web_search", "os_control"]