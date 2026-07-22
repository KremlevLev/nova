# Nova 2.0 Roadmap

## Выполненные задачи ✅

- [x] Add GEMINI_API_KEYS and GEMINI_BASE_URL to config.py
- [x] Add gemini model lists to config.py (using gemini-2.5-flash)
- [x] Fix model_router.py imports and add Gemini candidates
- [x] Add Gemini provider to ModelGateway
- [x] Write tests for the new functionality
- [x] Implement quota groups (ProviderKey with quota_group)
- [x] Add Execution Checkpoint
- [x] Add Execution Ledger
- [x] Implement ToolObservation for context reduction
- [x] Obsidian Adapter
- [x] **7. Разделение счётчиков** - обновлен budgets.py с новыми счётчиками
- [x] **8. Целевой бюджет запроса** - обновлены лимиты в AgentBudget
- [x] **10. Model Catalog** - создан modules/brain/model_catalog.py
- [x] **Приоритет 5 - Tool Visibility** - создан modules/tools/tool_visibility.py
- [x] **Clean up main.py bootstrap duplicates** - удалено дублирование resolved_request
- [x] **Приоритет 7 - Reasoning Loop** - создан modules/agent/reasoning.py
- [x] **Приоритет 11 - Tool Composition** - создан modules/tools/composition.py
- [x] **Приоритет 8, часть 1 - Research Synthesis** - создан modules/tools/synthesis.py
- [x] **GitHub MCP Server**: автоматическое подключение при наличии GITHUB_TOKEN в .env
- [x] **Filesystem MCP Server**: встроен в DEFAULT_MCP_SERVERS, всегда включён
- [x] **SQLite MCP Server**: поддержка MCP_SQLITE_PATH для указания пути к базе
- [x] **Slack MCP Server**: автоматическое подключение при наличии SLACK_TOKEN в .env
- [x] **Web Search MCP Server**: встроен в DEFAULT_MCP_SERVERS, всегда включён

## Текущие задачи

### 9. ModelGateway статус
- ✅ KeySlot с cooldown
- ✅ Route cooldown
- ✅ Model cooldown
- ✅ Provider cooldown
- ✅ Quota group cooldown (Gemini, Groq)
- ✅ Гроq → Gemini → OpenRouter fallback

### Приоритет 5 - Tool Visibility
- ✅ PUBLIC_SKILLS - публичные навыки (видимы модели)
- ✅ INTERNAL_PRIMITIVES - внутренние примитивы (скрыты)
- ✅ RECOVERY_TOOLS - инструменты восстановления (только для recovery)

### Приоритет 7 - Reasoning Loop (ВЫПОЛНЕН)

- ✅ **Iterative reasoning loop**: реализованы фазы THOUGHT, ACTION, REFLECTION
- ✅ **Self-reflection**: оценка успешности выполнения инструментов
- ✅ **Confidence scoring**: вычисление уверенности на основе результатов
- ✅ **Parallel execution**: параллельный запуск инструментов через run_parallel()
- ✅ Создан modules/agent/reasoning.py
- ✅ Написаны тесты tests/test_reasoning.py (11 passed)

### Приоритет 11 - Tool Composition (ВЫПОЛНЕН)

- ✅ **Tool chains**: ToolChain и ToolChainStep для последовательного выполнения
- ✅ **Conditional execution**: if-then логика через condition параметр
- ✅ **Parallel execution**: параллельный запуск независимых инструментов
- ✅ Создан modules/tools/composition.py
- ✅ Написаны тесты tests/test_composition.py (13 passed)
- ✅ Интегрировано в ReasoningLoop

### Приоритет 8 - Advanced Research Tools, часть 1 (ВЫПОЛНЕН)

- ✅ **Research Synthesis**: объединение информации из разных источников
- ✅ **Source credibility scoring**: оценка достоверности источников
- ✅ **Key point extraction**: извлечение ключевых моментов
- ✅ Создан modules/tools/synthesis.py
- ✅ Написаны тесты tests/test_synthesis.py (11 passed)

## Будущие улучшения (планируются)

### Приоритет 8 - Advanced Research Tools (продолжение)

- Deep web research: многошаговое исследование с анализом источников
- Source verification: проверка достоверности источников
- Citation management: автоматическое формирование списка источников
- Research synthesis: объединение информации из разных источников (ЧАСТИЧНО ВЫПОЛНЕНО)

### Приоритет 9 - Memory Enhancement (ВЫПОЛНЕН)

- ✅ **Hierarchical memory**: 4 уровня (short_term, middle_term, long_term, permanent) с приоритетами
- ✅ **Memory decay**: автоматическое забывание устаревшей информации на основе возраста
- ✅ **Memory consolidation**: метод для объединения похожих воспоминаний (заглушка готова)
- ✅ Создан modules/brain/memory.py с HierarchicalMemory и расширенным LocalMemory

### Приоритет 10 - Multi-modal Reasoning (ВЫПОЛНЕН ЧАСТИЧНО)

- ✅ **Screenshot capture**: захват экрана через PIL.ImageGrab
- ✅ **Vision reasoning**: подготовка изображений для анализа через vision-модели
- ✅ **OCR integration**: распознавание текста на изображениях через vision-модели
- ✅ Создан modules/tools/vision.py с VisionToolkit
- ✅ Написаны тесты tests/test_vision_tools.py (6 passed)

### Приоритет 12 - Recovery & Self-healing (ВЫПОЛНЕН)

- ✅ **MCP Gateway**: модуль `modules/agent/mcp_gateway.py` для подключения к внешним MCP-серверам
- ✅ **Automatic rollback**: поддержка rollback через RecoveryEngine с MCP инструментами
- ✅ **Alternative paths**: интеграция MCP инструментов как альтернативные пути восстановления
- ✅ **Graceful degradation**: `GracefulDegradation` класс для работы в упрощенном режиме
- ✅ **Self-diagnostics**: `SelfDiagnostics` класс для диагностики агента (database, storage, memory, filesystem, process_manager, model_gateway, mcp_servers)
- ✅ Создан modules/agent/mcp_gateway.py
- ✅ Созданы SelfDiagnostics и GracefulDegradation в modules/agent/recovery.py
- ✅ Написаны тесты tests/test_mcp_gateway.py (40 passed)

## MCP Integration Roadmap

### MCP Servers to Integrate

- [x] GitHub MCP Server - управление репозиториями, issues, PR через `@modelcontextprotocol/server-github`
- [x] Filesystem MCP Server - работа с файлами через `@modelcontextprotocol/server-filesystem`
- [x] SQLite MCP Server - запросы к базе данных через `@modelcontextprotocol/server-sqlite`
- [x] Slack MCP Server - интеграция с Slack через `@modelcontextprotocol/server-slack`
- [x] Web Search MCP Server - поиск в интернете через `@modelcontextprotocol/server-web-search`
- [ ] Google Drive MCP Server - работа с документами через `@modelcontextprotocol/server-gdrive`
- [ ] PostgreSQL MCP Server - подключение к PostgreSQL
- [ ] Git MCP Server - расширенные git операции
- [ ] Jira MCP Server - интеграция с Jira
- [ ] Docker MCP Server - управление контейнерами

### MCP Implementation Tasks (ВЫПОЛНЕНЫ ЧАСТИЧНО)

- [x] MCP Gateway с stdio транспортом - `modules/agent/mcp_gateway.py`
- [x] MCP tools registration с ToolRegistry support
- [x] MCP tool call error handling
- [x] **GitHub MCP Server**: автоматическое подключение при наличии GITHUB_TOKEN в .env
- [x] **Filesystem MCP Server**: встроен в DEFAULT_MCP_SERVERS, всегда включён
- [x] **SQLite MCP Server**: поддержка MCP_SQLITE_PATH для указания пути к базе
- [x] **Slack MCP Server**: автоматическое подключение при наличии SLACK_TOKEN в .env
- [x] **Web Search MCP Server**: встроен в DEFAULT_MCP_SERVERS, всегда включён
- [ ] Добавить SSE транспорт в MCPGateway (для удаленных серверов)
- [ ] MCP-пул соединений для переиспользования процессов
- [ ] Автоматическое обнаружение и подключение к localhost MCP серверам
- [ ] MCP-конфигурация в .env или config.json
- [ ] MCP tools caching (кеширование схем инструментов)
- [ ] MCP error handling middleware
- [ ] MCP timeout и retry политики
- [ ] Логирование MCP tool calls

## Тесты
```bash
python -m pytest tests/ -q  # 40 mcp_gateway tests passed + все остальные

# КОНТЕКСТ ПРОЕКТА
- Ты помогаешь мне развивать моего кастомного ИИ-агента.
- В проекте УЖЕ написано более 31 000 строк кода. Там куча готовых, отлично работающих хардкодных функций и бизнес-логики.
- МЫ НЕ ПЕРЕПИСЫВАЕМ СУЩЕСТВУЮЩИЙ КОД. Старые функции работают на обычном Tool Calling и остаются нетронутыми.

# ТВОЯ ЗАДАЧА
Помогать мне плавно расширять возможности агента с помощью протокола MCP (Model Context Protocol). Мы используем MCP ТОЛЬКО как внешние бесшовные модули/расширения для интеграции с новыми базами данных, API и сервисами, чтобы не раздувать ядро нашего монолита.

# СТРОГИЕ ПРАВИЛА РАЗРАБОТКИ
1. АРХИТЕКТУРА ИЗОЛЯЦИИ: Любая новая интеграция (GitHub, Jira, Slack, базы данных, веб-поиск) должна реализовываться через MCP. Не пиши код интеграции внутрь основного файла агента.
2. ПРИНЦИП КЛИЕНТА: Если нам нужен новый инструмент, сначала проверь, есть ли готовый MCP-сервер в экосистеме. Если есть, пиши код универсального MCP-клиента, который подключается к этому серверу, забирает его инструменты (`list_tools`) и динамически подмешивает их в наш старый массив `tools` перед отправкой в LLM.
3. ЧИСТОТА КОДА: Наш монолит должен оставаться чистым. Весь код управления MCP-транспортами (stdio, SSE) выноси в отдельный изолированный модуль (например, `mcp_gateway.py`).
4. ЗАПРЕТ НА РЕФАКТОРИНГ: Никогда не предлагай переписать наши старые 31к строк под стандарт MCP, если я сам об этом не попрошу. Уважай существующую кодовую базу.

# ФОРМАТ ОТВЕТА
Когда я прошу добавить новую фичу, отвечай по схеме:
1. Есть ли гтой MCP-сервер для этого? Если да — дай ссылку или команду для его запуска.
2. Код конфигурации (json) для подключения этого сервера.
3. Минимальный Python-код (скрипт/функция-прослойка), который заберет эти инструменты и добавит к нашему старому движку.