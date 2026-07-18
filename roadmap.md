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
- [x] Run all tests after each major change (296 passed)
- [x] **7. Разделение счётчиков** - обновлен budgets.py с новыми счётчиками
- [x] **8. Целевой бюджет запроса** - обновлены лимиты в AgentBudget
- [x] **10. Model Catalog** - создан modules/brain/model_catalog.py
- [x] **Приоритет 5 - Tool Visibility** - создан modules/tools/tool_visibility.py

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
- [ ] Fix критический блок в agent.py (дублирование user message - частично исправлено, требуется окончательная правка)

## Приоритет 5 - Tool Visibility

Public skills (видимы модели):
- write_in_application
- create_obsidian_note
- run_project_tests
- start_development_server
- edit_file_transactionally
- browser_research

Internal primitives (скрыты от модели):
- focus_window
- press_keyboard_combination
- type_text
- mouse_click

Recovery tools (только для восстановления):
- get_ui_tree
- find_ui_element
- ocr_screen
- click_text

## Приоритет 6 - Push-to-talk
(После стабилизации Core)

## Критический блок - AgentService.one-shot

Проблема в agent.py:
- User message добавляется дважды в history (строки ~560 и ~710)
- Signature проверяется после добавления (ошибка дедупликации)

Правильный порядок:
```python
if signature in executed_signatures:
    continue
    
execute_tool()
executed_signatures.add(signature)