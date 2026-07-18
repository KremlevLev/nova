# Nova 2.0 - Компактный план

## Выполненные задачи (✅)

- Gemini Provider integration (api keys, модели, priority 20)
- Quota groups в ModelGateway
- Execution Checkpoint и Execution Ledger
- ToolObservation для контекста
- Obsidian Adapter
- **7. Разделение счётчиков** - обновлен budgets.py
- **8. Целевой бюджет запроса** - обновлены лимиты в AgentBudget
- **10. Model Catalog** - создан modules/brain/model_catalog.py
- **Приоритет 5 - Tool Visibility** - создан modules/tools/tool_visibility.py

## Текущие задачи

### 9. ModelGateway статус
- ✅ KeySlot с cooldown
- ✅ Route cooldown
- ✅ Model cooldown
- ✅ Provider cooldown
- ✅ Quota group cooldown (Gemini, Groq)
- ✅ Гроq → Gemini → OpenRouter fallback

## Оставшиеся задачи

- [ ] Complete Input Hub (wake word, push-to-talk, CLI)
- [ ] Verify Intent Router priorities
- [ ] Verify Direct Executor metrics
- [ ] Test wake word + hotkey coordination
- [ ] Clean up main.py bootstrap duplicates
- [ ] Fix критический блок в agent.py (дублирование user message)

## Приоритет 5 - Tool Visibility

Создан файл `modules/tools/tool_visibility.py`:
- PUBLIC_SKILLS - публичные навыки (видимы модели)
- INTERNAL_PRIMITIVES - внутренние примитивы (скрыты)
- RECOVERY_TOOLS - инструменты восстановления (только для recovery)

## Приоритет 6 - Push-to-talk

(После стабилизации Core)

## Тесты
```bash
python -m pytest tests/ -q  # 296 passed