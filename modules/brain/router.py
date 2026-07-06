# py -m modules.brain.router
import time
from semantic_router import Route
from semantic_router.encoders import FastEmbedEncoder
from semantic_router.layer import RouteLayer

encoder = FastEmbedEncoder(name="intfloat/multilingual-e5-large")

# --- ДОБАВЛЯЕМ СЛЕНГ В РОУТЫ ---

os_route = Route(
    name="os_control",
    utterances=[
        "сделай потише", "открой блокнот", "выключи компьютер",
        "увеличь громкость", "открой калькулятор", "выруби дисплей",
        "сделай так чтоб я ничего не слышал", "запусти считалку", "погаси экран" # Добавили из теста
    ],
)
sys_status_route= Route(
    name="sys_stat_route",
    utterances=[
        'какая температура процессора', 'сколько оперативной памяти свободно',
        'покажи загрузку видеокарты', 'почему комп тормозит', 
        'че по ресурсам компик не закипает', 'сколько оперативы свободно' # Добавили сленг
    ]
)
calendar_schedule=Route(
    name="calendar_route",
    utterances=[
        "что у меня запланировано на завтра", "внеси созвон на 15:00", 
        "ебани мне встречу", "забей в график созвон с Саней" # Добавили из теста
    ]
)
web_route = Route(
    name="web_search",
    utterances=[
        "найди в гугле рецепт пиццы", "открой ютуб", "покажи новости", 
        "включи порно", "гей порно", "че там по погоде на завтра", "где сейчас идет война" # Добавили из теста
    ],
)
chat_route = Route(
    name="chat",
    utterances=[
        "привет, как дела?", "расскажи анекдот", "какой твой любимый цвет?",
        "слышь ты еблан", "жир", "че делаешь братуха", "ебани мне какую-нибудь историю" # Добавили сленг и мат
    ],
)

# ... (ОСТАЛЬНЫЕ ВАШИ РОУТЫ ОСТАВЛЯЕМ БЕЗ ИЗМЕНЕНИЙ) ...
app_management_route = Route(name="app_mng_route", utterances=["закрой вкладку", "прибей процесс хрома", "сверни все окна", "разверни игру", "закрой текущую программу", "переключись на дискорд"])
todo_and_notes = Route(name="todo&note_route", utterances=['напомни купить молоко вечером', 'запиши в блокнот идею', 'добавь в список покупок хлеб', "покажи мои задачи на сегодня", "создай напоминание"])
timer_alarm = Route(name="timer_alarm", utterances=["поставь таймер на 10 минут", "разбуди меня в 7 утра", "засеки полчаса для варки яиц", "выключи все будильники"])
file_operations = Route(name="file_operations", utterances=["создай папку на рабочем столе", "удали этот текстовый файл", "переименуй документ в архив", "найди фотку с отпуска на диске D", "удали тот мусорный txt файл из загрузок"])
code_assistant = Route(name="code_assistant", utterances=["напиши скрипт на питоне", "найди ошибку в этом коде", "оптимизируй эту функцию", "почему у меня падает ошибка индиката ин декс аут оф рендж"])
media_control = Route(name="media_control", utterances=["поставь на паузу", "включи следующий трек", "перемотай на минуту назад", "вруби следующий трек"])
smarthome_control = Route(name="smarthome_control", utterances=["выключи свет в спальне", "сделай кондиционер похолоднее", "включи свет в гостиной", "поставь чайник на максимум", "вруби кондей на 22 градуса"])
assistant_config = Route(name="assistant_config", utterances=["говори помедленнее", "смени свой голос на мужской", "смени язык на английский", "сделай свой голос погрубее"])
goodbye = Route(name="goodbye", utterances=["пока, Джарвис", "усни", "отключайся", "ладно давай пока", "сваливаю в туман до завтра"])

# Собираем всё
routes = [os_route, web_route, chat_route, sys_status_route, todo_and_notes, calendar_schedule, timer_alarm, file_operations, code_assistant, media_control, smarthome_control, assistant_config, goodbye]
route_layer = RouteLayer(encoder=encoder, routes=routes)

def get_intent(user_text: str) -> list[str]:
    """Умный роутер: возвращает список из 1-2 нужных категорий для LLM"""
    match = route_layer(user_text)
    
    # Если роутер уверенно нашел категорию
    if match and hasattr(match, 'name') and match.name:
        # Если это чат, то инструменты вообще не нужны
        if match.name == "chat":
            return ["chat"]
        # Отдаем найденную категорию + оставляем chat как возможность просто ответить
        return [match.name, "chat"]
    
    # Если роутер ничего не понял (вернул None), даем безопасный фолбек
    return ["chat", "web_search", "os_control"]

# --- ТЕСТОВЫЙ БЛОК ---
if __name__ == "__main__":
    import time  # Гарантируем, что модуль импортирован

    dataset = {
        "слышь ты еблан": "chat", "жир": "chat", "че делаешь братуха": "chat",
        "ебани мне какую-нибудь историю": "chat", "расскажи анекдот про программистов": "chat",
        "ладно давай пока": "goodbye", "сваливаю в туман до завтра": "goodbye",
        "как тебя переименовать в пятницу": "assistant_config", "смени язык на английский": "assistant_config",
        "сделай свой голос погрубее": "assistant_config", "выруби этот ящик": "os_control",
        "сделай так чтоб я ничего не слышал": "os_control", "запусти считалку": "os_control",
        "погаси экран": "os_control", "че по ресурсам компик не закипает": "sys_stat_route",
        "сколько оперативы свободно": "sys_stat_route", "поставь на паузу": "media_control",
        "вруби следующий трек": "media_control", "включи порнуху": "web_search",
        "гей порно": "web_search", "ебани мне встречу": "calendar_route",
        "забей в график созвон с Саней на завтра в 5 вечера": "calendar_route",
        "че у меня там по планам на сегодня": "calendar_route", "напомни купить молоко когда освобожусь": "todo&note_route",
        "запиши идею для проекта": "todo&note_route", "засеки мне 10 минут пока пельмени варятся": "timer_alarm",
        "разбуди меня в 7 утра": "timer_alarm", "выруби все будильники": "timer_alarm",
        "создай папку на рабочем столе": "file_operations", "удали тот мусорный txt файл из загрузок": "file_operations",
        "включи свет в гостиной": "smarthome_control", "поставь чайник на максимум": "smarthome_control",
        "вруби кондей на 22 градуса": "smarthome_control", "напиши скрипт на питоне для парсинга сайтов": "code_assistant",
        "почему у меня падает ошибка индиката ин декс аут оф рендж": "code_assistant",
        "оптимизируй эту функцию": "code_assistant", "найди в гугле рецепт пиццы": "web_search",
        "че там по погоде на завтра в Москве": "web_search", "где сейчас идет война": "web_search",
        "перейди на сайт википедии": "web_search",
    }

    print("=" * 80)
    print(f"СТАРТ АВТОТЕСТА РОУТЕРА С ЗАМЕРАМИ ВРЕМЕНИ (Всего фраз: {len(dataset)})")
    print("=" * 80)

    passed_tests = 0
    total_time = 0.0

    for phrase, expected_intent in dataset.items():
        start_time = time.time()
        actual_intents = get_intent(phrase)
        end_time = time.time()
        
        elapsed = end_time - start_time
        total_time += elapsed

        if expected_intent in actual_intents:
            passed_tests += 1
            print(f"[УСПЕХ] '{phrase}' -> {actual_intents} ({elapsed:.4f} сек)")
        else:
            print(f"[ОШИБКА] '{phrase}'")
            print(f"        Ожидалось : {expected_intent}")
            print(f"        Выдало    : {actual_intents} ({elapsed:.4f} сек)")

    print("=" * 80)
    print("ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"Успешно пройдено: {passed_tests} из {len(dataset)}")
    print(f"Среднее время обработки одного запроса: {total_time / len(dataset):.4f} сек")
    print("=" * 80)
