Ниже — готовый файл передачи проекта другой LLM. Сохраните его как:

```text
docs/LLM_HANDOFF.md
```

или вставьте целиком в Memory/Rules Cline.

---

# Nova — технический handoff для следующей LLM

> Этот документ описывает актуальное состояние разработки, известные проблемы, незавершённые изменения, приоритеты и правила дальнейшей работы.  
> Общее устройство проекта уже известно агенту, поэтому здесь акцент на **текущем состоянии, долгах, рисках и следующих действиях**.

---

## 1. Краткий статус

Nova 1.0 прошла первоначальный roadmap из 30 этапов:

```text
Nova 1.0: 30/30
```

Начата Nova 2.0. Её основные цели:

- единый Input Hub;
- ручной ввод;
- wake word «Нова»;
- режимы взаимодействия;
- ручной и автоматический выбор моделей;
- сокращение количества LLM-вызовов;
- skill-first выполнение;
- устойчивый fallback между провайдерами;
- прямой Obsidian Adapter;
- эффективное управление контекстом и TPM.

Текущий приблизительный статус Nova 2.0:

```text
Полностью подтверждено: 2/15
Частично реализовано: Input Hub, Interaction Modes, Wake Word,
Desktop Chat, Intent Router, Direct Executor
Критический незавершённый блок: экономичный AgentService
```

---

# 2. Аппаратные ограничения пользователя

Целевая машина:

```text
ОЗУ: 16 ГБ
Видеопамять: около 256 МБ
ОС: Windows
Python: 3.14
```

Следствия:

- основной inference — облачный;
- локальная модель — только CPU;
- локальный LLM — максимум 1–3B Q4;
- не использовать 7B+ как постоянно загруженную модель;
- не загружать локальный LLM в основной процесс;
- локальный STT — whisper.cpp tiny/base;
- wake word — маленькая Vosk-модель;
- не использовать GPU offload;
- не держать несколько тяжёлых моделей в памяти;
- TTS Silero уже использует Torch CPU.

---

# 3. Провайдеры моделей

## Используемые и планируемые

### Groq

Количество ключей:

```text
сейчас примерно 1
возможно будет 1–2
```

Назначение:

- быстрый tool calling;
- короткие ответы;
- быстрые skill-запросы;
- STT Whisper.

Проблема:

- быстро заканчивается TPM;
- нельзя рассчитывать, что несколько ключей одного аккаунта имеют независимую квоту.

### OpenRouter

Количество ключей:

```text
около 6
```

Назначение:

- основной резервный пул;
- бесплатные модели;
- reasoning;
- tool-capable fallback;
- vision fallback.

Важно:

- если ключи принадлежат одному аккаунту, баланс и часть лимитов могут быть общими;
- нельзя бездумно перебирать все шесть ключей для каждого логического вызова;
- требуется понятие quota group.

### Gemini API

Количество ключей:

```text
примерно 3–4
```

Целевая модель:

```text
Gemini 2.5 Flash
```

Назначение:

- экономичный fallback после Groq;
- tool calling;
- vision;
- длинный контекст;
- генерация аргументов high-level skills;
- создание планов.

Важно:

- если ключи относятся к одному Google Cloud project, квота может быть общей;
- ключи нужно объединять по `quota_group`;
- не считать каждый ключ независимым лимитным пулом.

### Локальный fallback

Назначение:

- короткий чат;
- аварийный текстовый ответ;
- простое объяснение;
- без tool calls.

Рекомендуемые модели:

```text
Qwen 1.5B/3B Instruct Q4_K_M
Llama 3.2 1B/3B Instruct Q4
SmolLM около 1.7B Q4
```

### GitHub Models

```text
ПОЛНОСТЬЮ ИСКЛЮЧЕНЫ ИЗ ПЛАНА.
```

Причина: сервис закрывается/не должен использоваться.

Не добавлять:

- GitHub Models provider;
- `GITHUB_MODELS_*`;
- PAT для моделей;
- маршруты через GitHub Models;
- зависимости или тесты для него.

---

# 4. Желаемый маршрут моделей

## Обычный чат

```text
Groq fast
→ Gemini 2.5 Flash
→ OpenRouter free/fast
→ Local LLM
```

## High-level skill с инструментом

```text
Groq tool-capable
→ Gemini 2.5 Flash
→ OpenRouter tool-capable
→ ошибка/уточнение
```

Лимит:

```text
1 logical model call
до 4 provider attempts
```

## Сложный план

```text
Gemini 2.5 Flash
→ Groq reasoning
→ OpenRouter reasoning
```

Лимит:

```text
1 вызов для плана
максимум 1 replan
```

## Vision

```text
Gemini 2.5 Flash
→ OpenRouter vision
```

## Код и архитектура

```text
Gemini 2.5 Flash
→ Groq reasoning
→ OpenRouter coding/reasoning
```

---

# 5. Главная нерешённая проблема

## Неэффективный агентный цикл

Исторически `AgentService.run()` работал так:

```text
model
→ tool
→ model
→ tool
→ model
→ tool
→ 429
→ fallback
→ budget exhausted
→ пользователь ничего не получает
```

В реальном логе команда:

```text
Запусти все приложения, которые можешь
```

вызвала около восьми обращений к модели, после чего:

```text
Достигнут лимит модельных вызовов: 8/8
```

Никакого полезного результата не получилось.

## Целевая схема

### DIRECT

```text
0 LLM-вызовов
1 локальный инструмент
```

### SKILL

```text
1 логический LLM-вызов
1 high-level skill
0 финальных LLM-вызовов
```

### PLAN

```text
1 логический LLM-вызов для плана
локальное выполнение
максимум 1 replan
локальный итог
```

### CHAT

```text
1 LLM-вызов
```

---

# 6. Критическое состояние `AgentService.run()`

Последний предоставленный пользователем `AgentService.run()` был сильно повреждён накопившимися вставками.

В нём обнаружено:

- пользовательское сообщение дважды добавляется в history;
- complexity вычисляется дважды;
- набор tools выбирается дважды;
- `executed_signatures` создаётся дважды;
- `executed_tool_results` создаётся дважды;
- model call учитывается до цикла и затем внутри цикла;
- общий цикл может вызывать модель до восьми раз;
- часть русских строк повреждена mojibake-кодировкой;
- присутствует критическая ошибка дедупликации.

Критическая ошибка:

```python
executed_signatures.add(signature)

if signature in executed_signatures:
    ...
    continue
```

Из-за этого первый реальный tool call сразу считается повторным и не выполняется.

Правильный порядок:

```python
if signature in executed_signatures:
    # duplicate
    continue

executed_signatures.add(signature)
execute_tool()
```

## Предлагавшееся решение

Полностью заменить `AgentService.run()` однотуровой реализацией:

```text
route
→ model exactly once
→ collect tool calls
→ execute tools exactly once
→ deterministic report
→ return
```

Пользователь после этого решил перейти на Cline, поэтому **не считать эту замену подтверждённой**.

Следующему агенту нужно сначала открыть актуальный:

```text
modules/application/agent.py
```

и проверить, применена ли однотуровая версия.

---

# 7. Необходимое разделение счётчиков

Сейчас могут смешиваться:

```text
логические вызовы агента
HTTP-попытки провайдеров
```

Это нужно разделить.

Пример:

```text
Groq → 429
Gemini → 429
OpenRouter → success
```

Для агента:

```text
logical_model_calls = 1
```

Для gateway:

```text
provider_attempts = 3
```

Нужные метрики:

```python
logical_model_calls
provider_attempts
provider_attempts_per_logical_call
tool_calls
replans
prompt_tokens
completion_tokens
observation_characters
```

---

# 8. Целевой бюджет запроса

```python
max_logical_model_calls = 2
max_provider_attempts_per_call = 4
max_total_provider_attempts = 8
max_replans = 1
max_tool_calls = 10
max_wall_time_seconds = 180
max_observation_characters = 4_000
```

По стратегиям:

| Стратегия | Logical calls |
|---|---:|
| DIRECT | 0 |
| CHAT | 1 |
| SKILL | 1 |
| WORKFLOW | 1 |
| PLAN | 1 + максимум 1 replan |
| CLARIFY | 0 |
| DENY | 0 |

Не увеличивать бюджет до бесконечности. Сначала уменьшать число вызовов.

---

# 9. ModelGateway: текущее состояние

`modules/brain/model_gateway.py` уже имеет:

- `KeySlot`;
- cooldown ключа;
- cooldown `provider + key + model`;
- cooldown модели;
- cooldown провайдера;
- классификацию ошибок;
- ротацию ключей;
- fallback между candidates;
- стриминговый сбор текста;
- сбор native tool calls;
- health snapshot.

Текущие провайдеры:

```text
groq
openrouter
```

## Уже реализованные уровни блокировки

### Ключ целиком

- `401`;
- `403`;
- daily quota.

### Key + model route

- обычный `429`;
- timeout;
- empty response.

### Модель

- tool protocol;
- bad request;
- context;
- server error конкретной модели.

### Провайдер

- connection error.

## Необходимые дальнейшие изменения

1. Добавить Gemini.
2. Добавить quota groups.
3. Ввести лимит provider attempts на один logical call.
4. Считать provider attempts отдельно.
5. Добавить health score.
6. Не перебирать все ключи одного quota group после явного общего TPM.
7. Поддержать fallback Groq → Gemini → OpenRouter.
8. Не добавлять GitHub Models.

---

# 10. Gemini — план интеграции

Предпочтительный подход — отдельный provider adapter, даже если используется OpenAI-compatible endpoint.

Не размазывать Gemini-специфику по всему `ModelGateway`.

Рекомендуемая структура:

```text
modules/models/
├── types.py
├── catalog.py
├── provider_pool.py
└── providers/
    ├── base.py
    ├── openai_compatible.py
    ├── groq.py
    ├── openrouter.py
    └── gemini.py
```

Минимальная интеграция допустима через существующий `AsyncOpenAI`, но необходимо отдельно проверить:

- endpoint;
- streaming;
- tool calls;
- JSON Schema;
- `tool_choice`;
- usage;
- 429 и retry-after;
- vision content format.

Не предполагать совместимость вслепую. Сверяться с актуальной документацией Gemini API.

Конфигурация:

```dotenv
GEMINI_API_KEYS=key1,key2,key3
GEMINI_DEFAULT_MODEL=gemini-2.5-flash
GEMINI_QUOTA_GROUP=gemini-project-main
```

Секреты нельзя коммитить.

---

# 11. Quota groups

Количество ключей не равно количеству независимых квот.

Нужна структура:

```python
ProviderKey:
    provider
    key_id
    secret
    quota_group
    disabled
    cooldown_until
```

Например:

```text
gemini-key-1 → project-a
gemini-key-2 → project-a
gemini-key-3 → project-b
```

Если Gemini сообщает project-level quota:

```text
cooldown project-a
```

а не только конкретный ключ.

Аналогично:

```text
openrouter-key-1..6 → возможно один account quota group
```

---

# 12. Checkpoint и продолжение задачи

При переключении провайдера до выполнения tool call можно передать тот же запрос.

После side effect нужен checkpoint:

```python
ExecutionCheckpoint:
    task_id
    goal
    strategy
    completed_steps
    pending_steps
    failed_steps
    observations
    artifact_ids
    successful_signatures
    rollback_tokens
    remaining_budget
```

Передавать другой модели можно только проверяемые факты:

```text
Выполнено:
- приложение открыто;
- документ создан.

Не выполнено:
- ввод текста.

Не повторять:
- open_application("Obsidian");
- create_document(...).
```

Не передавать скрытый chain-of-thought.

---

# 13. Execution Ledger

Нужно создать:

```python
ExecutionLedger:
    task_id
    completed_signatures
    operation_results
    active_operations
    rollback_tokens
```

Перед side effect:

```python
signature = canonical_tool_signature(tool_call)
```

Если успешная сигнатура уже есть:

```text
не выполнять повторно
вернуть сохранённый ToolResult
```

Исключения:

- явно repeatable read-only tools;
- повтор, явно инициированный пользователем;
- операция с новым idempotency key.

---

# 14. ToolObservation и сокращение контекста

Модель не должна получать полный stdout, DOM или stack trace.

Нужный формат:

```python
ToolObservation:
    tool_name
    success
    code
    summary
    important_data
    excerpt
    verification
    artifact_id
    retryable
    omitted_characters
```

Правила:

- полный результат сохранять в Artifact Store;
- модели передавать до 2–4 тысяч символов;
- stdout: первые/последние релевантные строки;
- stack trace: тип ошибки и ближайшие frames;
- DOM: только найденные элементы;
- diff: summary + artifact;
- не повторять огромный tool output в history.

---

# 15. Input Hub: текущее состояние

Созданы или планировались:

```text
modules/input_hub/models.py
modules/input_hub/coordinator.py
modules/input_hub/wake_word.py
modules/input_hub/wake_runtime.py
```

## UserRequest

Единый формат запроса:

- `request_id`;
- `text`;
- `source`;
- `input_mode`;
- `profile`;
- `model_mode`;
- `selected_model`;
- `attachments`;
- `speech_confidence`;
- `active_window_title`;
- `session_id`;
- `metadata`.

Источники:

```text
voice_continuous
voice_wake_word
push_to_talk
desktop_chat
quick_input
command_palette
clipboard
CLI
API
background_task
```

## InputCoordinator

Очередь запросов для:

- голоса;
- Desktop UI;
- wake word;
- будущего push-to-talk;
- CLI.

---

# 16. Intent Router: текущее состояние

Созданы:

```text
modules/routing/decision.py
modules/routing/intent.py
modules/routing/direct_executor.py
```

Стратегии:

```text
DIRECT
SKILL
WORKFLOW
PLAN
CHAT
CLARIFY
DENY
```

Известные intents:

```text
application_open
application_close
application_write
application_batch
system_time
system_volume
development
web
memory
reminder
model_selection
mode_selection
vision
chat
unknown_action
```

## Важные правила приоритетов

Проверять в таком порядке:

1. Vision.
2. Локальные режимы и модели.
3. Опасные batch-команды.
4. Системные direct-команды.
5. Web.
6. Application write.
7. Development.
8. Обычный app open/close.
9. Complex plan.
10. Unknown action.
11. Chat.

Это исправляет ошибки:

```text
«запусти тесты» ≠ открыть приложение «тесты»
«открой сайт» ≠ открыть приложение «сайт»
```

---

# 17. Direct Executor

`DIRECT` должен выполняться без модели.

Примеры:

```text
Который час?
Открой блокнот.
Закрой калькулятор.
Сделай громче.
Включи приватный режим.
Переключись на быструю модель.
```

Метрики:

```text
logical_model_calls = 0
provider_attempts = 0
```

Если direct request дошёл до AgentService, это архитектурная ошибка:

```text
DIRECT_ROUTE_NOT_DISPATCHED
```

---

# 18. Wake word: текущее состояние

Используется Vosk.

Конфигурация:

```dotenv
NOVA_WAKE_WORD_ENABLED=true
NOVA_WAKE_WORD=нова
NOVA_VOSK_MODEL=data/models/vosk
NOVA_WAKE_WORD_SENSITIVITY=0.55
NOVA_WAKE_COMMAND_TIMEOUT=15
```

Реальный лог подтвердил:

```text
Vosk wake-word модель загружена.
Wake word активен. Ожидаю фразу 'нова'.
```

То есть:

- пакет работает;
- модель загружается;
- microphone stream открывается.

Пока не подтверждено реальным тестом:

```text
Нова, который час?
```

Желаемое поведение:

```text
Vosk обнаруживает «Нова»
→ записывает полную фразу
→ существующий STT распознаёт WAV
→ strip_wake_prefix()
→ InputCoordinator
→ Dispatcher
```

Если пользователь говорит только:

```text
Нова
```

Nova должна временно перейти в continuous mode.

---

# 19. Горячая клавиша и wake word

Требование:

```text
должны работать одновременно
```

Правильная схема:

```text
спит:
    wake detector ждёт «Нова»
    Ctrl+Shift+Space зарегистрирован
    Desktop UI принимает текст

Ctrl+Shift+Space:
    wake detector освобождает микрофон
    continuous VoiceListener включается

повторное Ctrl+Shift+Space:
    continuous выключается
    Nova возвращается в wake word
```

Был добавлен/предложен:

```python
InteractionModeManager.toggle_manual_voice()
```

Требуется проверить актуальный файл:

```text
modules/application/interaction_modes.py
```

---

# 20. Известная проблема bootstrap `main.py`

В `async_main()` накопились повторные вставки.

Было обнаружено:

- `registry` создавался дважды;
- `runner` создавался дважды;
- `plan_service` создавался трижды;
- `agent` создавался трижды;
- `preferences` создавался дважды;
- `input_coordinator` создавался дважды;
- planning tools регистрировались несколько раз.

Это мешало bootstrap дойти до:

```python
keyboard.add_hotkey(...)
```

Пользователю была дана инструкция удалить дубли.

Не считать, что всё исправлено. Следующему агенту обязательно проверить:

```powershell
Select-String -Path "main.py" -Pattern "registry = ToolRegistry.from_legacy"
Select-String -Path "main.py" -Pattern "runner = ToolRunner"
Select-String -Path "main.py" -Pattern "plan_service = PlanService"
Select-String -Path "main.py" -Pattern "agent = AgentService"
Select-String -Path "main.py" -Pattern "preferences = PreferencesManager"
Select-String -Path "main.py" -Pattern "input_coordinator = InputCoordinator"
```

Каждое должно быть ровно один раз внутри `async_main()`.

Также:

```powershell
py -m ruff check main.py --select F821,F811
```

---

# 21. Правильный порядок bootstrap

```text
instance lock
desktop service
overlay
runtime
speech
browser
memory
scheduler
app indexer
listener
llm
process manager
database
memory store
artifact store
handlers
base schemas
registry
runner
plan service
background plan manager
deferred tools
agent
preferences
mode manager
input coordinator
direct executor
request dispatcher
request service
wake detector
wake runtime
desktop bridge
hotkeys
speech start
reminder task
voice task
wait shutdown event
```

Не запускать бесконечные runtime-циклы через прямой `await`.

Правильно:

```python
task = asyncio.create_task(
    service.run(shutdown_event)
)
```

Неправильно:

```python
await service.run(shutdown_event)
```

---

# 22. Desktop UI: текущее состояние

PySide6 UI запускается отдельным процессом.

Реальный лог:

```text
Desktop UI запущен
```

Была исправлена ошибка:

```text
self.tabs.addTab() до self.tabs = QTabWidget()
```

Desktop UI содержит/должен содержать:

- чат;
- обзор;
- процессы;
- память;
- разрешения;
- модели;
- журнал.

## Известная проблема

Пользователь вводил текст в UI, но Core не реагировал.

Возможные причины:

- bootstrap не дошёл до DesktopBridge;
- RequestService не запущен;
- дублированный `InputCoordinator`;
- UI пишет в одну очередь, Core читает другую;
- background task упала;
- `handle_command()` не получает `submit_user_request`.

Нужны диагностические логи:

```text
CoreDesktopBridge received command
InputCoordinator submitted request
RequestService received request
RequestDispatcher strategy=...
```

---

# 23. Interaction Modes

Режимы:

```text
SLEEP
WAKE_WORD
PUSH_TO_TALK
CONTINUOUS
TEXT_ONLY
PRIVACY
```

Профили:

```text
SAFE
ASSISTANT
ENGINEER
AUTONOMOUS_TASK
PRIVATE_LOCAL
```

Требуемая синхронизация:

- `CONTINUOUS` → `runtime.activate()`;
- остальные режимы → `runtime.sleep()`;
- повторная установка того же режима всё равно должна синхронизировать runtime;
- `PRIVACY` → cloud off, history off;
- `PRIVATE_LOCAL` → local-only model mode.

---

# 24. Push-to-talk

Ещё не реализован полноценно.

Желаемое поведение:

```text
удержание Ctrl+Space
→ wake detector освобождает микрофон
→ запись без ожидания начала VAD
→ отпускание Ctrl+Space
→ остановка записи
→ STT
→ InputCoordinator
→ возврат в wake word
```

Требуется единый владелец микрофона. Нельзя одновременно открывать:

- Vosk RawInputStream;
- VoiceListener;
- push-to-talk recorder.

Рекомендуется создать:

```text
MicrophoneLeaseManager
```

с владельцами:

```text
WAKE_WORD
CONTINUOUS_STT
PUSH_TO_TALK
```

---

# 25. Obsidian

Текущая GUI-автоматизация Obsidian остаётся нестабильной.

Проблема:

```text
open/focus/Ctrl+N/type_text
```

зависит от:

- состояния окна;
- активной вкладки;
- горячих клавиш;
- загрузки приложения;
- текущего vault;
- режима редактора.

Нужен прямой Obsidian Adapter.

Создать:

```text
modules/integrations/obsidian.py
```

Skills:

```text
detect_obsidian_vaults
list_obsidian_vaults
create_obsidian_note
append_obsidian_note
open_obsidian_note
search_obsidian_notes
create_daily_note
add_obsidian_tags
```

Правильная реализация:

```text
найти vault
→ создать Markdown атомарно
→ readback verification
→ открыть obsidian:// URI
```

Целевой кейс:

```text
Открой Obsidian и напиши стих о космосе
```

Должен стать:

```text
1 logical model call для текста
1 create_obsidian_note
0 GUI primitives
```

---

# 26. Tool visibility

Нужно разделить инструменты:

```python
PUBLIC_SKILL
INTERNAL_PRIMITIVE
RECOVERY_ONLY
```

## Public skills

Модель видит их напрямую:

```text
write_in_application
create_obsidian_note
run_project_tests
start_development_server
edit_file_transactionally
browser_research
```

## Internal primitives

Модель не должна видеть их в обычном SKILL-запросе:

```text
focus_window
press_keyboard_combination
type_text
mouse_click
```

## Recovery only

Показываются только при восстановлении:

```text
get_ui_tree
find_ui_element
ocr_screen
click_text
mouse_click
```

Это критично для сокращения числа tool calls.

---

# 27. Batch skills

Нужны:

```text
launch_applications_batch
close_applications_batch
read_files_batch
run_checks_batch
git_status_many
browser_extract_many
```

Команда:

```text
Запусти все приложения
```

не должна запускаться буквально.

Правильный ответ:

```text
Найдено 147 приложений. Какие именно открыть?
```

Ограничения batch launcher:

- максимум 10;
- HITL для 5+;
- `max_parallel=2`;
- preview;
- дедупликация;
- задержка между запусками.

---

# 28. История и persistence

SQLite и stores уже есть, но нужно проверить, реально ли `ConversationStore` подключён к каждому запросу.

Нужно сохранять:

- user message;
- assistant message;
- tool calls;
- tool results;
- provider;
- model;
- logical calls;
- provider attempts;
- input source;
- attachments;
- execution decision.

Историю нельзя сохранять в `PRIVACY`.

---

# 29. Кодировка

В extract `AgentService` русские строки выглядели как:

```text
╙ЄюўэшЄх
┴■фцхЄ
ьюфхы№
```

Возможны два варианта:

1. Файл реально сохранён с повреждённой кодировкой.
2. PowerShell неправильно отобразил UTF-8.

Проверить:

```powershell
py -c "from pathlib import Path; t=Path('modules/application/agent.py').read_text(encoding='utf-8'); print('Уточните запрос.' in t); print(t[:200])"
```

Если русские строки повреждены в самом файле:

- заменить их нормальным UTF-8;
- сохранить файл как UTF-8 без ANSI-конвертации;
- не делать массовое перекодирование без backup.

---

# 30. Безопасность

Не нарушать:

- API-ключи только в `.env`;
- `.env` не коммитить;
- provider pool config с ключами — в `.gitignore`;
- side effects только через ToolRunner;
- Policy Engine и PermissionManager не обходить;
- tool arguments валидировать;
- path traversal блокировать;
- SSRF блокировать;
- Python code выполнять через sandbox;
- локальная маленькая модель не управляет инструментами;
- safety refusal не обходить перебором провайдеров;
- выполненные side effects не повторять после fallback.

---

# 31. Тесты, которые должны появиться

## Эффективность

```text
DIRECT:
logical calls == 0

SKILL:
logical calls == 1

PLAN:
logical calls <= 2

final reporter:
logical calls не увеличиваются
```

## Fallback

```text
Groq 429
→ Gemini success
→ logical calls == 1
→ provider attempts == 2
```

## Side effects

```text
первый provider вернул tool call
tool выполнен
следующий provider получает checkpoint
tool повторно не выполняется
```

## Quota group

```text
два ключа одного Gemini project
project quota exhausted
→ оба ключа group cooldown
```

## Context compression

```text
80 000 символов stdout
→ ArtifactStore
→ observation <= 4 000 символов
```

## Obsidian

```text
создать note
→ файл существует
→ содержимое совпадает
→ URI сформирован
```

---

# 32. Метрики успеха Nova 2.0

| Сценарий | Цель |
|---|---:|
| Открыть приложение | 0 model calls |
| Время/громкость | 0 |
| Запись в приложение | ≤1 |
| Создание Obsidian note | ≤1 |
| Запуск тестов | ≤1 |
| Исправление проекта | ≤2 |
| Финальный отчёт | 0 дополнительных |
| Повтор side effect | 0 |
| Provider attempts на logical call | ≤4 |
| Tool observation | ≤4K символов |
| Wake latency | <500–800 мс |
| Отмена | <300 мс |

---

# 33. Roadmap Nova 2.0

## V2.1 Input Hub

Статус:

```text
реализован или почти реализован
```

Содержит:

- UserRequest;
- InputCoordinator;
- UI/manual source;
- voice source.

Нужно проверить runtime end-to-end.

## V2.2 Interaction Modes

Статус:

```text
частично
```

Есть Preferences/Mode Manager. Нужен:

- push-to-talk;
- microphone lease;
- стабильная синхронизация UI.

## V2.3 Wake Word

Статус:

```text
частично
```

Vosk модель загружается. Нужен реальный end-to-end тест.

## V2.4 Model Catalog

Статус:

```text
не реализован
```

Нужны:

- capabilities;
- model profiles;
- ручной выбор;
- health;
- pinning;
- Gemini;
- quota groups.

## V2.5 Intent Router

Статус:

```text
реализован
```

Нужно расширять intents и regression tests.

## V2.6 Tool Visibility

Статус:

```text
не реализован
```

Критически важно для уменьшения tool calls.

## V2.7 Workflow Engine

Статус:

```text
частично есть старый PlanExecutor
```

Нужны статические workflows без LLM на каждом шаге.

## V2.8 Batch Skills

Статус:

```text
не реализован
```

## V2.9 Obsidian Adapter

Статус:

```text
не реализован
```

Высокий приоритет.

## V2.10 Context Efficiency

Статус:

```text
спроектирован, не завершён
```

Нужны:

- однотуровый AgentService;
- ToolObservation;
- checkpoint;
- ledger;
- Gemini fallback.

## V2.11 Frontend Chat

Статус:

```text
частично
```

UI есть, end-to-end ручной запрос не подтверждён.

## V2.12 Voice UX

Статус:

```text
частично
```

Нужны:

- barge-in;
- follow-up window;
- push-to-talk;
- confidence;
- wake tuning.

## V2.13 Session Persistence

Статус:

```text
stores есть, интеграцию проверить
```

## V2.14 Benchmarks

Статус:

```text
не реализован
```

## V2.15 Release 2.0

Статус:

```text
не начат
```

---

# 34. Рекомендуемый порядок дальнейшей работы

## Приоритет 0 — привести репозиторий в проверяемое состояние

1. `git status`.
2. Сохранить текущую ветку.
3. Проверить дубли `main.py`.
4. Ruff `F821,F811`.
5. `py_compile`.
6. Полный pytest.
7. Ручной startup.
8. UI text request.
9. Hotkey.
10. Wake word.

## Приоритет 1 — экономичный AgentService

1. Удалить дубли из `run()`.
2. Удалить общий восьмитуровый цикл для SKILL.
3. Исправить дедупликацию.
4. Один logical call.
5. Один tool batch.
6. Локальный report.
7. Тесты эффективности.

## Приоритет 2 — Gemini

1. Config.
2. Provider adapter.
3. Key slots.
4. Quota groups.
5. Tool calling.
6. Vision.
7. 429 fallback tests.

## Приоритет 3 — checkpoint и ledger

1. ExecutionLedger.
2. ToolObservation.
3. Checkpoint.
4. Continuation prompt.
5. Side-effect dedupe.

## Приоритет 4 — Obsidian Adapter

1. Vault detection.
2. Atomic Markdown write.
3. Readback.
4. URI open.
5. Интеграция Intent Router.

## Приоритет 5 — Tool Visibility + workflows

1. Public skills.
2. Internal primitives.
3. Recovery tools.
4. Static workflows.
5. Resource locks.

## Приоритет 6 — Push-to-talk

После стабилизации Core.

---

# 35. Правила работы для Cline

1. **Сначала читать фактический код.**
2. Не доверять предыдущим фрагментам без проверки.
3. Не переписывать `main.py` целиком без необходимости.
4. Делать минимальные патчи.
5. После каждого изменения запускать точечные тесты.
6. Затем полный pytest.
7. Проверять Ruff.
8. Не создавать второй singleton одного сервиса.
9. Не регистрировать один tool несколько раз.
10. Не добавлять новую LLM-попытку для финальной фразы.
11. Не увеличивать бюджеты вместо исправления архитектуры.
12. Не добавлять GitHub Models.
13. Не печатать API-ключи.
14. Не делать массовое форматирование вместе с функциональным патчем.
15. При изменении контракта обновлять все тесты и callers.
16. На Windows учитывать блокировки файлов.
17. Все фоновые циклы запускать через `create_task`.
18. Shutdown должен отменять и ожидать каждую task.
19. Не запускать два microphone stream одновременно.
20. Любой side effect должен быть идемпотентным или защищён ledger.

---

# 36. Первые команды для Cline

```powershell
git status
git branch --show-current
git diff --stat
```

```powershell
py -m ruff check main.py modules --select F821,F811
```

```powershell
py -m py_compile main.py
py -m compileall core modules main.py
```

```powershell
py -m pytest -q
```

Поиск bootstrap-дублей:

```powershell
Select-String -Path main.py -Pattern "registry = ToolRegistry.from_legacy"
Select-String -Path main.py -Pattern "runner = ToolRunner"
Select-String -Path main.py -Pattern "plan_service = PlanService"
Select-String -Path main.py -Pattern "agent = AgentService"
Select-String -Path main.py -Pattern "preferences = PreferencesManager"
Select-String -Path main.py -Pattern "input_coordinator = InputCoordinator"
```

Проверка AgentService:

```powershell
Select-String `
  -Path modules\application\agent.py `
  -Pattern "for turn_index|record_model_call|executed_signatures.add|if signature in executed_signatures" `
  -Context 3,5
```

Проверка моделей:

```powershell
Select-String `
  -Path modules\brain\model_gateway.py `
  -Pattern "groq|openrouter|gemini|complete|provider_attempt" `
  -Context 1,2
```

---

# 37. Рекомендуемые Git-коммиты

Первый:

```text
fix(bootstrap): remove duplicated service initialization
```

Второй:

```text
perf(agent): execute skills in one logical model call
```

Третий:

```text
feat(models): add Gemini provider pools and quota-aware fallback
```

Четвёртый:

```text
feat(agent): add execution ledger and checkpoint continuation
```

Пятый:

```text
feat(obsidian): add direct vault note integration
```

Шестой:

```text
refactor(tools): separate public skills from internal primitives
```

---

# 38. Определение готовности ближайшего этапа

Этап экономичного агента считается завершённым, только если автоматически подтверждены:

```text
«Который час?»
logical calls = 0

«Открой блокнот»
logical calls = 0
tool executions = 1

«Открой Obsidian и напиши стих»
logical calls = 1
tool executions = 1
final LLM calls = 0

Groq 429 → Gemini success
logical calls = 1
provider attempts = 2

Повторный одинаковый tool call
side effect executions = 1
```

---

# 39. Важная оговорка о текущем состоянии

В проект было внесено много изменений последовательными вставками. Часть могла быть:

- применена;
- применена дважды;
- не применена;
- применена не в том месте;
- повреждена кодировкой.

Поэтому этот handoff — не утверждение, что каждый описанный модуль работает идеально. Это карта:

- что задумывалось;
- что уже подтверждалось;
- что частично работало;
- где обнаружены ошибки;
- что проверять первым.

**Фактический код и тесты всегда важнее этого документа.**

---

# 40. Итог

Главная задача следующей LLM:

```text
Не добавлять больше хаотичных возможностей,
пока не стабилизирован runtime и не уменьшено
число логических модельных вызовов.
```

Главная архитектурная цель:

```text
DIRECT: 0 LLM
SKILL: 1 LLM
PLAN: 1–2 LLM
REPORT: 0 LLM
```

Главная модельная цель:

```text
Groq
→ Gemini 2.5 Flash
→ OpenRouter
→ Local chat fallback
```

Главная функциональная цель:

```text
«Нова, открой Obsidian и создай заметку со стихом»
→ wake word
→ 1 logical LLM call
→ 1 create_obsidian_note
→ verified result
```

---

## Рекомендуемый коммит документа

```powershell
git add docs/LLM_HANDOFF.md
git commit -m "docs: add complete Nova development handoff and roadmap"
```

**Название коммита:**

```text
docs: add complete Nova development handoff and roadmap
```

## Финальный прогресс

- Nova 1.0: **30/30 выполнено**.
- Nova 2.0: **2/15 подтверждено**, несколько этапов частично реализованы.
- GitHub Models: **исключены**.
- Главный следующий этап: **экономичный однотуровый AgentService + Gemini fallback**.
