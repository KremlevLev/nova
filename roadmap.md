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

### Приоритет 9 - Memory Enhancement

- Hierarchical memory: дерево памяти с приоритетами
- Memory decay: "забывание" устаревшей информации
- Memory consolidation: периодическое обобщение памяти
- Semantic search: векторный поиск по памяти

### Приоритет 10 - Multi-modal Reasoning

- Vision reasoning: анализ экрана + выполнение действий
- OCR integration: распознавание текста + последующее действие
- Screenshot analysis: понимание UI через изображения
- Visual planning: планирование на основе визуального контекста

### Приоритет 12 - Recovery & Self-healing

- Automatic rollback: откат при неудачах
- Alternative paths: поиск альтернативных решений
- Graceful degradation: работа в упрощенном режиме
- Self-diagnostics: диагностика самого агента

## Тесты
```bash
python -m pytest tests/ -q  # 326 passed