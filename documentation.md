# Nova AI Assistant — Comprehensive Technical Documentation

## Project Overview

**Nova** is a local Windows AI assistant written in Python 3.14+ that combines voice control, system automation, engineering capabilities, and a desktop UI. It operates entirely locally with cloud LLM providers (Groq, OpenRouter) for inference, and provides offline fallback via local models.

### Key Characteristics
- **Platform**: Windows-only (uses Win32 APIs, UI Automation, COM)
- **Architecture**: Modular, async-first, event-driven with clear separation of concerns
- **LLM Providers**: Groq (primary), OpenRouter (fallback), Local LLM/STT fallback (Vosk + Llama.cpp)
- **Voice**: Whisper (Groq) for STT, Silero v5 for TTS (Russian, CPU-only)
- **UI**: PySide6 desktop application with overlay indicator
- **Testing**: 220+ tests covering all major components

---

## Directory Structure

```
nova/
├── core/                       # Configuration, system prompt, shared constants
├── modules/
│   ├── agent/                  # Planning, execution, recovery, background plans
│   ├── application/            # Agent service, speech, request dispatch, preferences
│   ├── audio/                  # STT (Whisper), TTS (Silero)
│   ├── brain/                  # LLM gateway, model router, memory, tool calls
│   ├── browser/                # Playwright-based browser agent
│   ├── domain/                 # Core data structures (results, state, context)
│   ├── input_hub/              # Wake word, voice/text input coordination
│   ├── local/                  # Local inference fallback (Vosk, Llama.cpp)
│   ├── routing/                # Intent routing, direct execution, decisions
│   ├── security/               # Python sandbox for code execution
│   ├── storage/                # SQLite, conversations, memories, artifacts
│   ├── tools/                  # Tool registry, runtime, policies, skills
│   ├── ui/                     # Desktop UI (PySide6), overlay
│   └── windows/                # Windows-specific: FS, Git, processes, UI automation
├── data/                       # Local data (memory, logs, backups)
├── scripts/                    # Build installer, dependency installation
├── tests/                      # 220+ unit/integration tests
└── main.py                     # Application entry point
```

---

## Core Modules

### `core/config.py` — Central Configuration

**Purpose**: Loads all environment variables, validates API keys, builds model routing tables, and generates the system prompt.

**Key Components**:
- `_split_csv()` / `_collect_keys()` / `_model_list()` — helpers for parsing env vars
- `GROQ_API_KEYS`, `OPENROUTER_API_KEYS` — tuples of API keys with rotation support
- Model lists by provider and task type: `GROQ_CHAT_MODELS`, `GROQ_TOOL_MODELS`, `GROQ_COMPLEX_MODELS`, `GROQ_VISION_MODELS`, `OPENROUTER_*` equivalents
- Derived constants: `DEFAULT_MODEL`, `MODEL_BASIC_TOOLS`, `MODEL_COMPLEX_TOOLS`, `MODEL_CV_BASE`, `SMART_MODEL`, `FALLBACK_MODEL`
- Runtime limits: `MAX_AGENT_TURNS=8`, `MAX_TOOL_CALLS=12`, `MAX_CONTEXT_ESTIMATED_TOKENS=12000`, `TOOL_TIMEOUT_SECONDS=30`
- `build_system_prompt()` — generates the master system prompt with current timestamp, identity (female, addresses user as "Сэр"), reliability rules, GUI rules, communication style, agent workflow, and high-level Windows skills

**Environment Variables**:
```
NOVA_DEBUG=false
GROQ_API_KEYS=key1,key2,key3          # or GROQ_API_KEY, GROQ_API_KEY_2...
OPENROUTER_API_KEYS=key1,key2          # or OPENROUTER_API_KEY, OPENROUTER_API_KEY_2...
TAVILY_API_KEY=xxx                     # Web search
HF_TOKEN=xxx                           # Hugging Face (local models)
NOVA_GROQ_CHAT_MODELS=llama-3.1-8b-instant
NOVA_GROQ_TOOL_MODELS=openai/gpt-oss-20b
NOVA_GROQ_COMPLEX_MODELS=openai/gpt-oss-120b,openai/gpt-oss-20b
NOVA_GROQ_VISION_MODELS=meta-llama/llama-4-scout-17b-16e-instruct
NOVA_OPENROUTER_CHAT_MODELS=openrouter/free
NOVA_OPENROUTER_TOOL_MODELS=openai/gpt-oss-20b:free,openrouter/free
NOVA_OPENROUTER_COMPLEX_MODELS=openai/gpt-oss-120b:free,nvidia/nemotron-3-ultra-550b-a55b:free,openrouter/free
NOVA_OPENROUTER_ULTRA_MODELS=nvidia/nemotron-3-ultra-550b-a55b:free,openai/gpt-oss-120b:free,openrouter/free
NOVA_OPENROUTER_VISION_MODELS=meta-llama/llama-4-scout:free,openrouter/free
NOVA_LLM_REQUEST_TIMEOUT=90
NOVA_GROQ_RATE_LIMIT_COOLDOWN=90
NOVA_PROVIDER_ERROR_COOLDOWN=30
NOVA_DAILY_LIMIT_COOLDOWN=21600
NOVA_MAX_AGENT_TURNS=8
NOVA_MAX_TOOL_CALLS=12
NOVA_MAX_CONTEXT_TOKENS=12000
NOVA_TOOL_TIMEOUT_SECONDS=30
NOVA_DESKTOP_UI=true
NOVA_WAKE_WORD_ENABLED=false
NOVA_VOSK_MODEL=/path/to/vosk-model
NOVA_WAKE_WORD=нова
NOVA_WAKE_WORD_SENSITIVITY=0.55
NOVA_WAKE_COMMAND_TIMEOUT=15
NOVA_ENABLE_LOCAL_LLM_FALLBACK=true
```

### `core/prompts.py` — System Prompts

Contains additional prompt templates used by various modules (planning, code generation, etc.).

---

## Brain Modules (`modules/brain/`)

### `brain/llm.py` — NovaLLM (High-Level LLM Interface)

**Purpose**: Unified async interface for chat completions with automatic fallback from cloud to local inference.

**Class: `NovaLLM`**
- `__init__(model=None)` — optional primary model override
- `complete(candidates, messages, tools=None, allow_tools=True, requires_vision=False)` — main entry point
  - Tries `ModelGateway.complete()` with candidate models
  - On failure, falls back to `LocalLLMFallback` if enabled and conditions allow (no tools, no vision, no tool calls requested)
- `close()` — closes gateway connections
- `reset_context()` — clears conversation history
- `provider_health()` — returns health snapshot including local LLM availability

**Fallback Logic**: Local LLM is used only for pure text chat (no tools, no vision, no tool calls in request). This preserves reliability for tool-calling tasks.

### `brain/model_gateway.py` — ModelGateway (Multi-Provider LLM Gateway)

**Purpose**: Production-grade multi-provider, multi-key LLM gateway with sophisticated cooldown and failure handling.

**Architecture — Four Lock Levels**:
1. **Key-level** (global): 401/403 auth failures, daily quota exhaustion → key disabled entirely
2. **Route-level** (key + model): 429 rate limits, timeouts, empty responses → specific key/model combo cooled down
3. **Model-level** (provider + model): Tool protocol errors, bad requests, context overflow → model cooled across all keys
4. **Provider-level**: Network/server errors (5xx, DNS, connection) → entire provider cooled

**Key Classes**:
- `FailureKind` (StrEnum): AUTHENTICATION, RATE_LIMIT, DAILY_LIMIT, TIMEOUT, CONNECTION, SERVER, CONTEXT, BAD_REQUEST, TOOL_PROTOCOL, EMPTY_RESPONSE, UNKNOWN
- `GatewayFailure` — structured exception with kind, message, retryable flag, cooldown_seconds, status_code
- `KeySlot` — tracks per-key state: disabled flag, global_cooldown_until, consecutive_failures, successful_requests, last_error, last_success_at
- `ModelResponse` — normalized response: provider, model, key_label, text, tool_calls, finish_reason, usage

**Core Methods**:
- `complete(candidates, messages, tools, allow_tools, requires_vision)` — iterates candidates, tries keys in preferred order, applies cooldowns, registers failures at correct level, returns first success
- `classify_failure(error)` — regex-based error classification with status code extraction and retry-after header parsing
- `_prepare_tools_for_provider(tools, provider)` — strips `additionalProperties` for Groq (prevents schema rejection)
- `_request_once(slot, candidate, messages, tools, allow_tools)` — streams response via AsyncOpenAI, accumulates text and tool calls
- `health_snapshot()` — returns structured state for all keys, routes, models, providers

**Cooldown Configuration** (from config):
- `GROQ_RATE_LIMIT_COOLDOWN=90s`
- `PROVIDER_ERROR_COOLDOWN=30s`
- `DAILY_LIMIT_COOLDOWN=21600s` (6 hours)

### `brain/model_router.py` — ModelRouter (Task → Model Selection)

**Purpose**: Classifies user request complexity and builds an ordered list of model candidates (provider + model) for the gateway.

**Complexity Classification** (`TaskComplexity` enum):
- `CHAT` — simple conversation, no tools needed
- `BASIC_TOOL` — single tool call, simple action
- `COMPLEX_TOOL` — multi-step, multiple actions, or complex markers
- `ULTRA` — architecture design, full project analysis, deep research
- `VISION` — image/screen analysis required

**Classification Logic** (`classify_complexity`):
1. If `has_image` → VISION
2. If `not needs_tools` → CHAT
3. Score "ultra" markers (long text >1200 chars, architectural/security/refactor/migration keywords, code markers like traceback/docker/kubernetes) — score ≥4 → ULTRA
4. Count action verbs (открой, запусти, создай, установи, проверь, найди, скачай, выполни, нажми, переключи, сохрани, удали, перемести, скопируй) — ≥2 → COMPLEX_TOOL
5. Check complex markers (затем, после чего, а потом, и потом, а также, сначала, исправь, установи, создай проект, запусти тесты, проанализируй логи, напиши код, открой и напиши) — any present → COMPLEX_TOOL
6. Text length >300 → COMPLEX_TOOL
7. Default → BASIC_TOOL

**Route Building** (`build_model_route`):
- Returns prioritized `ModelCandidate` list (provider, model, supports_tools, supports_vision, priority)
- Priority: lower number = higher priority
- Vision → Groq vision models (priority 10) then OpenRouter vision (30)
- Ultra → OpenRouter ultra models (10) then Groq complex (40)
- Complex tool → Groq complex (10) then OpenRouter complex (30)
- Basic tool → Groq tool (10) then OpenRouter tool (30)
- Chat → Groq chat (10) then OpenRouter chat (30)
- Deduplicates by identity, sorts by priority

**ModelCandidate Dataclass**:
- `provider`, `model`, `supports_tools`, `supports_vision`, `priority`
- `identity` property: "provider:model"

### `brain/memory.py` — LocalMemory (BM25-based Local Semantic Memory)

**Purpose**: Lightweight, fast local memory using BM25 ranking (no embeddings, no heavy dependencies). Compatible with Python 3.14, zero idle memory.

**Features**:
- JSON file persistence (`data/memory/local_memory.json`)
- Russian stemming (suffix stripping: -ий, -ов, -ами, -ям, -ом, -ему, -ого, -ое, -ая, -их, -ых, -ую, -ть, -ся, -ти, -ок, -ек, -а, -е, -и, -о, -у, -ы, -я, -ь)
- Duplicate protection (case-insensitive exact match)
- BM25 scoring with k1=1.2, b=0.75
- Optional SQLite backend via `MemoryStore` for conversation integration

**Class: `LocalMemory(BaseMemory)`**
- `__init__(storage_path, database=None)` — loads existing memory
- `add_document(text, metadata)` — adds with dedup, saves to disk
- `search(query, limit=3)` — returns scored results with metadata

**BaseMemory**: Abstract interface for future vector/remote backends.

### `brain/bypass.py` — Fast Command Bypass (Regex-based Instant Actions)

**Purpose**: Intercept simple, deterministic commands before they reach the LLM for sub-5ms execution.

**Components**:
- `LAUNCH_VERBS` / `CLOSE_VERBS` — Russian verb forms for app launch/close
- `FAST_COMMAND_PATTERNS` — compiled regex + handler tuples:
  - Volume: "громкость 50", "тише", "громче", "выключи звук/включи звук/муте"
  - Time: "сколько времени", "который час", "точное время"
  - Windows: "сверни все окна", "закрой активное окно"
- `check_instant_app_launch(text, app_launcher)` — matches launch verbs + app name, delegates to `WindowsAppIndexer`
- `check_instant_app_close(text)` — matches close verbs, delegates to `close_application`
- `check_fast_commands(text)` — runs through `FAST_COMMAND_PATTERNS`
- `is_complex_request(text)` — detects compound commands (conjunctions: ", ", " и потом", " а потом", " затем", " после чего", " а также") or multiple action verbs → returns True to force LLM routing
- `determine_model_by_complexity(text, has_image, needs_tools)` — selects model tier:
  - Has image OR no tools needed → `MODEL_CV_BASE` (Llama 4 Scout)
  - Complex request → `MODEL_COMPLEX_TOOLS` (GPT-OSS-120B)
  - Simple tool call → `MODEL_BASIC_TOOLS` (GPT-OSS-20B)

### `brain/tool_calls.py` — Tool Call Parsing & Normalization

**Purpose**: Extract, normalize, and deduplicate tool calls from LLM output (both native OpenAI format and XML fallbacks).

**Functions**:
- `_normalize_arguments(arguments)` — handles dict, JSON string, markdown code fences
- `normalize_tool_call(tool_call)` — validates structure, ensures call_id, returns canonical form
- `extract_xml_tool_calls(text, allowed_names)` — parses `<function=name>args</function>` and `<name>args</name>` patterns, validates against allowed tool names
- `canonical_tool_signature(tool_call)` — creates deterministic "name:args_json" signature for deduplication
- `deduplicate_tool_calls(tool_calls)` — removes duplicate calls by canonical signature

### `brain/bypass.py` — (covered above)

---

## Application Modules (`modules/application/`)

### `application/agent.py` — AgentService (Main Agent Loop)

**Purpose**: Orchestrates the complete agentic loop: tool selection → model calls → tool execution → verification → final report.

**Key Components**:
- `ACTION_PATTERNS` — regexes for action verbs (открой, запусти, напиши, создай, удали, etc.)
- `request_requires_action(text)` — checks if user text contains action verbs
- `content_to_text(content)` — extracts text from multimodal content
- `estimate_message_tokens(messages)` — rough token estimation (chars/3)
- `split_history_into_turns(history)` — groups by user turns to preserve tool call/response pairs
- `trim_history(history, max_tokens)` — drops oldest turns until under limit

**Class: `AgentService`**
- `__init__(llm, registry, runner, session_id=None)` — budget manager, intent router, conversation history
- `_request_model(complexity, messages, tools, allow_tools, has_image)` — builds candidate route via `build_model_route`, filters for vision, calls `llm.complete()`
- `_parse_tool_arguments(tool_call)` — safe JSON parsing
- `_tool_result_record(tool_call, result)` — standardized tool result record
- `_duplicate_result_content(signature)` — standardized duplicate rejection response
- `_deterministic_tool_summary(tool_results)` — builds text summary without LLM
- `_deterministic_speech_summary(tool_results)` — generates short Russian speech summary
- `_build_final_report_messages(user_text, tool_results, budget_exhausted)` — constructs isolated final report context (prevents "tool_choice=none but model called tool" errors)
- `_create_final_report(...)` — delegates to `build_assistant_response_from_tools` (local, no LLM)
- `run(user_text, user_content=None, use_tools=True, has_image=False)` — **main entry point**
  - Creates turn_id, resolves UserRequest
  - Routes via `DeterministicIntentRouter` → `ExecutionDecision`
  - Handles CLARIFY/DENY/CHAT strategies
  - Selects tools (router-specified or heuristic via `select_tool_names`)
  - Agent loop (max `MAX_AGENT_TURNS`):
    - Trims history, builds messages with system prompt
    - Checks budget before each model call
    - Calls model, extracts native + XML tool calls, deduplicates
    - If no tool calls: checks for "action requested but no tools used" (nudges once), returns final report or chat response
    - Executes each tool call via `runner.execute()` with `ToolContext`
    - Tracks signatures, budget, duplicate prevention
    - On tool limit or budget exhaustion → returns final report
  - Returns `AssistantResponse`

**Budget System**: Integrated with `BudgetManager`/`AgentBudget` — tracks model calls, tool calls, wall time, repeated tool calls per turn.

### `application/speech.py` — SpeechService (TTS Queue Manager)

**Purpose**: Single-worker TTS queue with priority, interrupt handling, and generation-based invalidation.

**Features**:
- `prepare_text_for_speech(text)` — strips code blocks, XML/tool calls, HTML, markdown tables, URLs, long paths, hashes; truncates to ~700 chars with sentence-boundary preference
- `split_speech_chunks(text, max_chunk=420)` — splits into Silero-safe chunks at sentence boundaries
- `SpeechService` — async priority queue with generation counter
  - `say(text, priority=10, wait=True)` — enqueues, optionally waits for completion
  - `interrupt()` — increments generation, stops current playback, clears pending queue, resolves waiters
  - `close()` — graceful shutdown with sentinel
  - Worker (`_run`) — processes queue, splits into chunks, calls `speak()` per chunk, checks generation before each chunk

**State Management**: Generation counter ensures stale messages are discarded after interrupt without cancelling parent tasks.

### `application/preferences.py` — PreferencesManager (Runtime Settings)

**Purpose**: Thread-safe runtime preferences with cross-setting validation.

**Settings** (`PreferencesSnapshot`):
- `input_mode`: SLEEP, WAKE_WORD, PUSH_TO_TALK, CONTINUOUS, TEXT_ONLY, PRIVACY
- `assistant_profile`: SAFE, ASSISTANT, ENGINEER, AUTONOMOUS_TASK, PRIVATE_LOCAL
- `model_mode`: AUTO, FAST, SMART, CODING, VISION, FREE_ONLY, LOCAL_ONLY, PINNED
- `selected_model`: str (for PINNED mode)
- `tts_enabled`, `cloud_enabled`, `history_enabled`: bool

**Cross-setting Logic**:
- `PRIVACY` mode → forces `cloud_enabled=false`, `history_enabled=false`
- `PRIVATE_LOCAL` profile → forces `cloud_enabled=false`, `history_enabled=false`, `model_mode=LOCAL_ONLY`
- `LOCAL_ONLY` model mode → forces `cloud_enabled=false`
- PINNED mode requires `selected_model`

**Initialization**: Reads `NOVA_WAKE_WORD_ENABLED` and `NOVA_VOSK_MODEL` to set initial `input_mode`.

### `application/request_dispatcher.py` — RequestDispatcher (Strategy Router)

**Purpose**: Routes `UserRequest` to appropriate executor based on `ExecutionDecision`.

**Strategies**:
- `DIRECT` → `DirectRequestExecutor` (no LLM, instant)
- `CLARIFY` → returns clarification question locally
- `DENY` → returns denial reason locally
- `CHAT/SKILL/WORKFLOW/PLAN` → `AgentService.run()` with appropriate tool settings

**Flow**:
1. Empty request check
2. `intent_router.route(request)` → `ExecutionDecision`
3. Switch on `decision.strategy`
4. Attach metadata (`request_id`, `execution_decision`, `model_calls`) to response

### `application/request_service.py` — RequestService (Sequential Request Processor)

**Purpose**: Serializes request processing to prevent GUI/clipboard conflicts.

**Operation**:
- Runs loop waiting on `coordinator.next_request()` and `shutdown_event`
- For each request: creates dispatch task, awaits result, calls `response_handler(request, response)`
- `cancel_current()` — cancels in-flight dispatch task

**Concurrency**: Single active request at a time.

### `application/interaction_modes.py` — InteractionModeManager

**Purpose**: Centralized input mode switching with runtime synchronization.

**Modes** (`InputMode`):
- `SLEEP` — inactive
- `WAKE_WORD` — listens for "Нова" via Vosk
- `PUSH_TO_TALK` — manual activation
- `CONTINUOUS` — always listening (VoiceListener)
- `TEXT_ONLY` — no voice
- `PRIVACY` — no cloud, no history

**Features**:
- `toggle_manual_voice()` — hotkey (Ctrl+Shift+Space) toggles CONTINUOUS ↔ previous mode
- `set_mode(mode)` — applies mode, interrupts speech, syncs `RuntimeState` (activate/sleep)
- `set_mode_from_string(name)` — CLI/desktop UI entry point
- `attach_wake_runtime(wake_runtime)` — late binding for wake word detector

### `application/reporting.py` — Tool Execution Reporting

**Purpose**: Builds final user-facing responses from tool execution records without additional LLM calls.

**Data Structures**:
- `ToolExecutionSummary` — display_text, speech_text, success, error_code, counts

**Functions**:
- `_result_from_record(record)` — extracts result dict
- `_verification_state(result)` — reads `verification.verified` (bool/None)
- `_human_tool_name(name)` — maps tool names to Russian descriptions
- `_specialized_speech_summary(records, failed_count)` — returns short speech for common patterns (write_in_application, type_text, create_workspace_project, run_terminal_command, set_reminder, open_application, close_application)
- `build_tool_execution_summary(records, budget_exhausted)` — builds detailed display text with verification statuses, counts, budget note
- `build_assistant_response_from_tools(records, budget_exhausted)` → `AssistantResponse` — main entry point

---

## Audio Modules (`modules/audio/`)

### `audio/stt.py` — VoiceListener (Speech-to-Text)

**Purpose**: Continuous voice capture with VAD, Whisper (Groq) transcription, local Vosk fallback.

**Key Components**:
- `WHISPER_HALLUCINATIONS` — set of common Whisper false positives to filter ("спасибо", "продолжение следует", "минут", etc.)
- `KNOWN_APPLICATION_NAMES` — for command correction
- `normalize_voice_command(text)` — fixes Whisper errors at command start (e.g., "ключи" → "включи") only when known app name present
- `TranscriptionAttempt` — dataclass with success, text, error, status_code, retryable
- `VoiceListener` — main class
  - `__init__(input_device=None)` — 16kHz, 1024 block, 1.2s silence timeout, 0.18s min speech, 60s max, 0.8s pre-roll
  - `_calibrate(stream, should_abort)` — measures noise floor, sets adaptive threshold (0.006–0.045)
  - `_record(should_abort)` — VAD loop with pre-roll, start/continue thresholds, silence detection
  - `_transcribe(wav_path)` — tries Groq keys in order with cooldown rotation, falls back to local Vosk
  - `_transcribe_local(wav_path)` — async bridge to `LocalSTTFallback`
  - `transcribe_file(wav_path)` — transcribes existing file, filters hallucinations
  - `listen(should_abort)` — full pipeline: record → save temp WAV → transcribe → cleanup

**Key Rotation**: Preferred key index, per-key cooldowns (401/403 → 24h, 429 → 90s, retryable → 15s)

### `audio/tts.py` — Silero TTS (Text-to-Speech)

**Purpose**: CPU-only Russian TTS via Silero v5 with English→Russian phonetic transliteration.

**Components**:
- `_get_silero_engine()` — lazy loads `v5_ru.pt`, auto-downloads from silero.ai
- `speak(text, speaker="baya")` — blocking synthesis + playback via sounddevice
  - Interrupt flag checked at 3 phases (pre-start, pre-synthesis, pre-playback)
  - `put_accent=True`, `put_yo=True`
- `stop_speaking()` — sets interrupt flag, calls `sd.stop()`
- `reset_interrupt_flag()` / `is_interrupted()`
- `split_speech_chunks(text, max_chunk=420)` — sentence/word splitting for worker
- `speak_worker(queue)` — async queue consumer with interrupt handling

**English→Russian Transliteration** (`convert_english_to_russian_phonetic`):
- `TECH_GLOSSARY` — 60+ tech terms (llm→эл эл эм, python→пайтон, vscode→вэ эс код, etc.)
- `transliterate_word(word)` — handles snake_case, CamelCase, single letters, trailing digits, leading digits, silent 'e' endings, digraphs (tion→шн, sh→ш, ch→ч, ph→ф, th→т, etc.), char-by-char mapping
- Pre-processes file extensions (main.py → main py)

---

## Input Hub (`modules/input_hub/`)

### `input_hub/models.py` — Core Data Types

**Enums**:
- `RequestSource`: VOICE_CONTINUOUS, VOICE_WAKE_WORD, PUSH_TO_TALK, DESKTOP_CHAT, QUICK_INPUT, COMMAND_PALETTE, CLIPBOARD, CLI, API, BACKGROUND_TASK
- `InputMode`: SLEEP, WAKE_WORD, PUSH_TO_TALK, CONTINUOUS, TEXT_ONLY, PRIVACY
- `AssistantProfile`: SAFE, ASSISTANT, ENGINEER, AUTONOMOUS_TASK, PRIVATE_LOCAL
- `ModelSelectionMode`: AUTO, FAST, SMART, CODING, VISION, FREE_ONLY, LOCAL_ONLY, PINNED
- `AttachmentType`: FILE, IMAGE, SCREENSHOT, CLIPBOARD, ARTIFACT

**Dataclasses**:
- `Attachment` — type, path, artifact_id, mime_type, display_name, metadata
- `UserRequest` — request_id, text, source, input_mode, created_at, profile, model_mode, selected_model, attachments, speech_confidence, active_window_title, session_id, metadata
  - Factory methods: `create()`, `from_voice()`, `from_text()`
  - Properties: `has_attachments`, `has_image`, `is_voice`, `is_empty`
  - `to_dict()` for serialization

### `input_hub/coordinator.py` — InputCoordinator (Request Queue)

**Purpose**: Single async queue for all input sources with deduplication and lifecycle management.

**Class: `InputCoordinator`**
- `__init__(max_queue_size=100)`
- `submit(request)` — validates non-empty, deduplicates by request_id, enqueues
- `submit_voice()` / `submit_text()` — convenience factories
- `next_request()` → `UserRequest | None` — dequeues (None = shutdown sentinel)
- `task_done(request)` — marks complete, removes from known IDs
- `requests()` — async iterator
- `close()` — drains queue, sends sentinel

### `input_hub/wake_word.py` — WakeWordDetector (Vosk-based)

**Purpose**: Low-power always-on wake word detection ("Нова") with full command capture.

**Architecture**:
- `WakeWordConfig.from_environment()` — reads `NOVA_WAKE_WORD_ENABLED`, `NOVA_VOSK_MODEL`, `NOVA_WAKE_WORD_SENSITIVITY`, `NOVA_WAKE_COMMAND_TIMEOUT`, `NOVA_INPUT_DEVICE`
- `WakeWordDetector` — runs in thread via `asyncio.to_thread`
  - `wait_for_command(should_abort)` — streams audio to Vosk `KaldiRecognizer`
  - Pre-roll buffer (1.2s) captures audio before wake word
  - Wake detection on partial/final results via `contains_wake_word()`
  - Post-wake capture: continues recording until silence (1.1s) or max duration (15s)
  - Minimum post-wake blocks (0.5s) ensures user can speak command
  - Saves full utterance to temp WAV for high-quality re-transcription
  - Returns `WakeCapture(detected, audio_path, detected_text, error)`
- `normalize_wake_text()`, `contains_wake_word()`, `strip_wake_prefix()` — text utilities
- `_rms_from_bytes()` — audio level calculation

### `input_hub/wake_runtime.py` — WakeWordRuntime (Bridge)

**Purpose**: Connects `WakeWordDetector` → `VoiceListener.transcribe_file()` → `InputCoordinator`.

**Flow**:
1. Loop while `input_mode == WAKE_WORD` and not `runtime.is_active`
2. `detector.wait_for_command()` → get WAV
3. Set state `TRANSCRIBING`
4. `listener.transcribe_file(wav_path)` → full transcription
5. `strip_wake_prefix()` → clean command
6. If command: `coordinator.submit_voice(wake_word=True, metadata={wake_detected_text, full_transcription})` → state `SLEEPING`
7. If only wake word: `runtime.activate()` → enters continuous listening mode

---

## Agent Modules (`modules/agent/`)

### `agent/planning.py` — Planning & Execution Engine

**Purpose**: Structured plan definition, validation, execution with dependency resolution and recovery.

**Core Types**:
- `PlanStepStatus`: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, CANCELLED
- `PlanStep` — step_id, tool_name, arguments, depends_on[], description, critical, status, result
- `ExecutionPlan` — goal, steps[], plan_id, created_at
- `PlanBudget` — max_steps=20, max_wall_time=300s
- `PlanValidationResult` — valid, errors[]
- `PlanExecutionResult` — success, plan, completed/failed/skipped counts, error_code, message, `to_tool_result()`

**Validation** (`PlanValidator.validate`):
- Goal non-empty, steps exist, step count ≤ budget
- Unique step_ids
- All tools registered in registry
- No planning tools (execute_plan, cancel_plan, get_plan_status) inside plans
- All dependencies exist, no self-dependency, no cycles (DFS)

**Execution** (`PlanExecutor.execute`):
- Validates plan first
- Topological execution respecting `depends_on`
- Per-step: builds tool call, creates `ToolContext`, executes via `runner` with `RecoveryEngine`
- `RecoveryEngine.execute_with_recovery()` — up to 3 attempts with exponential backoff (1s, 2s, 4s, max 8s), supports fallback/rollback
- `StepVerifier.verify(step, result)` — checks `result.success` and `result.verification.verified`
- Critical step failure → skips remaining, returns failure
- Deadlock detection (no progress in iteration) → returns PLAN_DEADLOCK
- Wall-time budget enforcement → cancels remaining

**Recovery Integration**: Uses `RecoveryEngine` from `agent/recovery.py` for retry/fallback/rollback decisions.

### `agent/recovery.py` — RecoveryEngine (Error Recovery Strategy)

**Purpose**: Determines recovery action after tool failure based on error code and context.

**RecoveryAction** (StrEnum): RETRY, FALLBACK, ASK_USER, ROLLBACK, ABORT, CONTINUE

**Classification** (`decide(result, context)`):
1. Success → CONTINUE
2. Cancellation → ABORT
3. User denied → ABORT
4. User input codes (EMPTY_TEXT, AMBIGUOUS_TARGET, etc.) → ASK_USER
5. Non-retryable codes (POLICY_DENIED, ARGUMENT_VALIDATION_FAILED, TOOL_NOT_FOUND, APPLICATION_NOT_FOUND, etc.) → ABORT
6. Fallback codes (UI_AUTOMATION_NOT_AVAILABLE, ELEMENT_NOT_FOUND, MODEL_ROUTE_FAILED, etc.) + `has_fallback` → FALLBACK
7. Retryable codes (TOOL_TIMEOUT, CONNECTION_ERROR, TEMPORARY_FAILURE, etc.) or `result.retryable` + attempts < max → RETRY with exponential backoff
8. Has rollback token + `has_rollback` → ROLLBACK
9. Default → ABORT

**Execution Wrapper** (`execute_with_recovery`):
- Loops attempts, calls operation(attempt)
- On RETRY: sleeps `delay_seconds` (cancellable)
- On non-RETRY: returns immediately with decision
- After max attempts: final decision with exhausted context

### `agent/background_plans.py` — BackgroundPlanManager (Async Plan Execution)

**Purpose**: Runs `PlanService.execute_plan()` in background asyncio tasks, allowing user to continue interacting.

**Class: `BackgroundPlanManager`**
- `start_plan(goal, steps, session_id, turn_id)` → creates `BackgroundPlan` record, spawns asyncio task
- `_run_plan(record)` — executes, updates status (RUNNING→COMPLETED/FAILED/CANCELLED), stores result
- `get_status(background_id)`, `list_plans()`, `cancel_plan(background_id)` — management
- `close()` — cancels all running tasks

**BackgroundPlan** dataclass: background_id, goal, steps, session/turn IDs, status, timestamps, result, error, task reference

### `agent/plan_service.py` — PlanService (Tool-Call Facade)

**Purpose**: Exposes plan execution as a tool call for LLM-driven planning.

**Class: `PlanService`**
- `execute_plan(goal, steps, session_id, turn_id)` — parses raw steps, builds `ExecutionPlan`, runs `PlanExecutor`, returns `ToolResult`
- `get_plan_status(plan_id)`, `cancel_plan(plan_id)` — status/control
- `_parse_steps(raw_steps)` — converts `[{step_id, tool_name, arguments, depends_on, description, critical}]` to `PlanStep` list

---

## Routing Modules (`modules/routing/`)

### `routing/decision.py` — ExecutionDecision (Routing Result)

**Purpose**: Immutable decision object from intent router.

**Enums**:
- `ExecutionStrategy`: DIRECT, CHAT, SKILL, WORKFLOW, PLAN, CLARIFY, DENY
- `IntentKind`: CHAT, SYSTEM_TIME, SYSTEM_VOLUME, APPLICATION_OPEN, APPLICATION_CLOSE, APPLICATION_WRITE, WEB, DEVELOPMENT, VISION, UNKNOWN_ACTION, MODEL_SELECTION, MODE_SELECTION, APPLICATION_BATCH

**Dataclass: `ExecutionDecision`**
- strategy, intent
- required_tools: set[str]
- selected_skill: str | None
- workflow_name: str | None
- arguments: dict
- needs_model, needs_tools, needs_clarification
- clarification_question, denial_reason
- expected_model_calls, expected_tool_calls
- confidence, reason
- metadata: dict
- Factory methods: `chat()`, `clarify()`, `deny()`
- `to_dict()` for serialization

### `routing/direct_executor.py` — DirectRequestExecutor (LLM-Free Execution)

**Purpose**: Executes deterministic intents without LLM involvement.

**Supported Intents**:
- `MODEL_SELECTION` — switches model mode (AUTO, FAST, SMART, CODING, VISION, FREE_ONLY, LOCAL_ONLY, PINNED)
- `MODE_SELECTION` — switches input mode (PRIVACY, TEXT_ONLY, VOICE, CONTINUOUS, WAKE_WORD)
- `SYSTEM_TIME` → `get_current_time`
- `SYSTEM_VOLUME` → `change_volume` (parses "up/down/mute/NN%")
- `APPLICATION_OPEN` → `open_application`
- `APPLICATION_CLOSE` → `close_application`

**Argument Parsing** (`_build_tool_arguments`):
- Extracts app_name from decision.arguments
- Parses volume action from raw text (regex for %, up/down/mute)
- Returns clarification response if required args missing

**Execution**: Builds tool call, creates `ToolContext`, runs via `ToolRunner`, wraps result via `build_assistant_response_from_tools`.

### `routing/intent.py` — DeterministicIntentRouter (Rule-Based Router)

**Purpose**: Fast, deterministic intent classification using keyword/regex matching (skill-first routing).

**Priority Order** (critical for correctness):
1. Empty/vision
2. Chat phrases / model selection / mode selection
3. Dangerous batch commands (all apps)
4. Direct system commands (time, volume)
5. Web tasks (before app regex to avoid "open site" → app launch)
6. App + write intent → `write_in_application` skill (with content check)
7. Development markers → SKILL or PLAN (complex markers → PLAN)
8. App open/close → DIRECT
9. Complex markers (multi-step) → PLAN
10. Unknown action verbs → SKILL
11. Default → CHAT

**Key Constants**:
- `KNOWN_APPLICATIONS` — 35+ app names (Russian/English)
- `CHAT_PHRASES` — 11 short phrases
- `MODEL_SELECTION_MARKERS` / `MODE_SELECTION_MARKERS`
- `WRITE_MARKERS` / `TOPIC_MARKERS` (content detection)
- `COMPLEX_MARKERS` (sequential/conditional)
- `DEVELOPMENT_MARKERS` (code, test, git, docker, k8s, refactor, traceback)
- `INVALID_APPLICATION_TARGETS` — filters false positives (сайт, тест, проект, код, команда, терминал, сервер, процесс, все приложения)
- `WEB_MARKERS` (site, page, internet, docs, URL, search)

**Helpers**:
- `normalize_request_text()` — lower, ё→е, collapse whitespace
- `_extract_application_name()` — known app lookup + regex patterns with post-filtering
- `_requests_all_applications()` — detects dangerous "open everything" requests
- `_has_content_or_topic()` — checks for topic markers (" о ", " про ", " с текстом ", etc.)

**Class: `DeterministicIntentRouter`**
- `route(request, has_image)` → `ExecutionDecision`
- Returns decision with strategy, intent, required_tools, selected_skill, arguments, model/tool needs, confidence

---

## Tools Infrastructure (`modules/tools/`)

### `tools/base.py` — Core Tool Definitions

**Enums**:
- `ToolCategory`: SYSTEM_READ/WRITE, APPLICATION, GUI_READ/WRITE, FILE_READ/WRITE, MEMORY, REMINDER, WEB_READ, NETWORK_WRITE, PROCESS_READ/CONTROL, TERMINAL, DEVELOPMENT, CLIPBOARD_READ/WRITE, DESTRUCTIVE, UNKNOWN
- `RiskLevel`: READ_ONLY, LOW, WRITE, EXECUTE, DESTRUCTIVE, CRITICAL

**Dataclasses**:
- `ToolCancellationToken` — asyncio.Event wrapper with `raise_if_cancelled()`
- `ToolContext` — operation_id, session/turn IDs, working_directory, expected_window, source, metadata, cancellation token
  - `create()` factory with defaults
  - `elapsed_ms` property
- `ToolDefinition` — **single source of truth** for tools
  - name, description, parameters (JSON Schema), handler
  - category, risk, timeout_seconds
  - idempotent, supports_rollback, requires_confirmation
  - inject_context (new handlers receive context=)
  - `from_legacy()` — converts old registry schema
  - `to_openai_schema()` — for LLM
  - `schema` property — legacy compatibility

**Alias**: `RegisteredTool = ToolDefinition`

### `tools/registry.py` — Tool Registry (All Tool Schemas)

**Purpose**: Central flat list `ALL_TOOLS` of OpenAI function schemas. Extended by domain-specific tool groups.

**Tool Categories**:
1. **Core System**: open_application, close_application, type_text, get_current_time, change_volume, open_website, get_system_status, search_web_tavily, execute_cmd_command, manage_media, manage_windows, create_quick_note, set_timer, control_smart_home, configure_assistant
2. **Memory**: save_to_memory, search_in_memory
3. **Reminders**: set_reminder, get_active_reminders
4. **Code Execution**: execute_python_code (requires confirmation)
5. **GUI Automation**: mouse_click, press_keyboard_combination
6. **Project Creation**: create_workspace_project
7. **High-Level Skills**: write_in_application
8. **Web**: scrape_webpage
9. **Clipboard**: get_clipboard_content, set_clipboard_content
10. **Terminal**: run_terminal_command (requires confirmation)
11. **Window Management**: list_active_windows, focus_window
12. **Process Manager** (4 tools): start_process, get_process_status, read_process_output, stop_process, list_processes
13. **Filesystem** (6 tools): read_text_file, write_text_file, apply_text_patch, get_file_diff, search_files, rollback_file
14. **Git** (6 tools): git_status, git_diff, git_log, git_commit, git_branch, inspect_project
15. **Memory Store** (4 tools): save_memory, search_memory, delete_memory, clear_all_memories
16. **Artifacts** (3 tools): store_artifact, read_artifact, delete_artifact
17. **Browser Agent** (8 tools): browser_start, browser_open_url, browser_get_page_text, browser_click, browser_fill, browser_screenshot, browser_status, browser_close
18. **Planning** (3 tools): execute_plan, get_plan_status, cancel_plan
19. **Background Plans** (4 tools): start_background_plan, get_background_plan_status, list_background_plans, cancel_background_plan

**Post-processing**: Ensures `additionalProperties: false` on all schemas.

### `tools/runtime.py` — ToolRegistry & ToolRunner (Execution Engine)

**ToolRegistry**:
- `register_definition(definition)` / `register(schema, handler, risk, category, timeout)`
- `from_legacy(schemas, handlers)` — bulk registration with validation
- `schemas(names?)`, `get(name)`, `definitions()`, `names` property

**ToolRunner**:
- `__init__(registry, permission_manager=None)`
- `_parse_arguments(tool_call)` → (name, arguments, parse_error)
- `execute(tool_call, context)` — **main execution path**:
  1. Parse arguments, validate JSON
  2. Look up definition
  3. Create context (with cancellation token)
  4. Policy check via `PermissionManager` → ALLOWED/DENIED/NEEDS_CONFIRMATION
  5. Wait for confirmation if needed (user denial → USER_DENIED)
  6. Strip unknown properties per schema
  7. Validate arguments against JSON Schema (type, required, additionalProperties, min/max length/items, enum, min/max for numbers)
  8. Execute handler (async or sync via `asyncio.to_thread`) with timeout
  9. Adapt legacy results via `adapt_legacy_result()`
  10. Attach metadata (operation_id, session_id, turn_id, risk, category, idempotent)
  11. Warning for stripped unknown arguments

**Error Handling**: Timeout → TOOL_TIMEOUT (retryable), Cancelled → TOOL_CANCELLED, Exception → TOOL_EXECUTION_FAILED

### `tools/selection.py` — Heuristic Tool Selector

**Purpose**: Reduces LLM context by pre-selecting relevant tools based on user text.

**Tool Groups** (constants):
- `COMMON_READ_TOOLS`, `APPLICATION_TOOLS`, `TEXT_INPUT_TOOLS`, `GUI_TOOLS`, `WEB_TOOLS`, `MEMORY_TOOLS`, `REMINDER_TOOLS`, `SYSTEM_TOOLS`, `DEVELOPMENT_TOOLS`, `NOTE_TOOLS`, `MODEL_DIAGNOSTIC_TOOLS`, `HIGH_LEVEL_APPLICATION_SKILLS`, `PROCESS_MANAGER_TOOLS`, `FILESYSTEM_TOOLS`, `GIT_TOOLS`, `PROJECT_TOOLS`, `MEMORY_STORE_TOOLS`, `BROWSER_AGENT_TOOLS`, `PLANNING_TOOLS`, `ARTIFACT_TOOLS`, `BACKGROUND_PLAN_TOOLS`

**Marker Tuples**: application_markers, browser_agent_markers, planning_markers, text_input_markers, web_markers, memory_markers, reminder_markers, system_markers, development_markers, background_plan_markers, note_markers, provider_markers, filesystem_markers, git_markers, project_markers, memory_store_markers, artifact_markers

**Function**: `select_tool_names(user_text, has_image)` → set[str]
- Always includes `COMMON_READ_TOOLS` + `HIGH_LEVEL_APPLICATION_SKILLS`
- Adds groups based on marker matching (case-insensitive, ё→е)
- `has_image` → adds `GUI_TOOLS`

**Note**: Not a security boundary; final enforcement in `ToolRunner` + policy.

### `tools/skills.py` — WindowsSkills (High-Level Composites)

**Purpose**: Multi-step operations with verification, replacing fragile atomic tool chains.

**Class: `WindowsSkills`**
- Dependencies injected: `app_launcher`, `list_windows`, `focus_window`, `press_hotkey`, `type_text`, `get_active_window_title`

**Skills**:
1. `write_in_application(app_name, text, create_new_document=True)` — **flagship skill**
   - Launches app, waits 0.8s, focuses window (with fallback to matched name)
   - Ctrl+N for new doc (0.3s wait)
   - Verifies active window matches app before typing
   - Types text, returns verified result with `VerificationResult(verified=True, confidence=0.9)`
   - Max 100k chars per call

2. `open_and_focus(app_name)` — launches + focuses only

**Error Detection**: `_result_failed(result)` checks for Russian/English error markers.

### `tools/os_utils.py` — Atomic System Tools

**Tools Implemented** (each returns `ToolResult`):
- `get_current_time()` — formatted Russian datetime
- `open_application(app_name)` — via `WindowsAppIndexer`
- `close_application(app_name)` — taskkill /f /im
- `type_text(text)` — pyautogui.write with interval
- `change_volume(action)` — "up/down/mute/NN" via COM `IAudioEndpointVolume`
- `open_website(url_or_query)` — webbrowser + search fallback
- `get_system_status(metric)` — psutil CPU/RAM/battery
- `search_web_tavily(query)` — Tavily API (requires key)
- `execute_cmd_command(command)` — whitelisted: "очистить корзину", "спящий режим", "выключить пк"
- `manage_media(action)` — play_pause/next/prev via media keys
- `manage_windows(action)` — minimize_all (Win+D), close_current (Alt+F4)
- `create_quick_note(text)` — saves to Desktop/notes/timestamp.txt
- `set_timer(minutes)` — background thread with `SpeechService.say()`
- `control_smart_home(device, action)` — stub
- `configure_assistant(setting, value)` — stub
- `save_to_memory(text)` / `search_in_memory(query)` — `LocalMemory`
- `set_reminder(time_str, message)` — `TaskScheduler` (+15min or HH:MM)
- `get_active_reminders()` — lists pending
- `execute_python_code(code)` — sandboxed (see `security/sandbox.py`)
- `mouse_click(x, y, click_type)` — pyautogui click
- `press_keyboard_combination(keys)` — pyautogui hotkey
- `create_workspace_project(project_name, files, content)` — creates folder structure on Desktop
- `scrape_webpage(url)` — requests + BeautifulSoup text extraction
- `get_clipboard_content()` / `set_clipboard_content(text)` — pyperclip
- `run_terminal_command(command)` — `ProcessManager.start_process` + read output
- `list_active_windows()` — `get_visible_window_titles()`
- `focus_window(window_title_part)` — `WindowsAppIndexer.find_app` + `focus_window`
- `get_active_window_title()` — `get_foreground_window_title()`

### `tools/executor.py` — Workspace & Code Execution Tools

**Tools**:
- `create_workspace_project(project_name, files, content)` — creates project structure on Desktop
- `execute_python_code(code)` — **sandboxed execution** via `security/sandbox.py`
- `mouse_click(x, y, click_type)` — coordinates with bounds checking

### `tools/policy.py` — ToolPolicy (Static Allow/Deny Rules)

**Purpose**: Zero-config baseline policy for tool execution.

**Rules** (`DEFAULT_POLICY`):
- `execute_python_code`, `run_terminal_command` → `NEEDS_CONFIRMATION` (user must approve)
- `close_application`, `manage_windows(action=close_current)`, `execute_cmd_command` → `NEEDS_CONFIRMATION` (destructive)
- `mouse_click`, `press_keyboard_combination`, `type_text` → `NEEDS_CONFIRMATION` (GUI write)
- `apply_text_patch`, `write_text_file`, `delete_memory`, `clear_all_memories`, `delete_artifact`, `stop_process`, `git_commit` → `NEEDS_CONFIRMATION` (state-changing)
- All others → `ALLOWED`

**Evaluation** (`evaluate_policy`):
- Input: `PolicyContext(definition, arguments, context)`
- Returns `PolicyDecision`: ALLOWED, DENIED, NEEDS_CONFIRMATION with reason

### `tools/permissions.py` — PermissionManager (User Confirmation Flow)

**Purpose**: Manages pending confirmations with per-operation events.

**Class: `PermissionManager`**
- `_pending: dict[operation_id, asyncio.Event]`
- `check(policy_context)` → `(allowed, denial_reason)`:
  - Evaluates policy
  - If NEEDS_CONFIRMATION: creates event, stores, returns (False, reason)
  - If DENIED: returns (False, reason)
  - Else: (True, None)
- `wait_for_confirmation(policy_context)` — awaits event (with 60s timeout)
- `grant(operation_id)` / `deny(operation_id)` — resolves event
- `cancel_all()` — denies all pending

### `tools/budgets.py` — BudgetManager (Resource Limits)

**Purpose**: Enforces per-turn limits on model calls, tool calls, wall time, repeated tools.

**Classes**:
- `AgentBudget` — max_model_calls=25, max_tool_calls=12, max_wall_time=180s, max_repeated_tool_calls=3
- `BudgetState` — tracks counts, start_time, tool_signatures (with attempt counts)
- `BudgetManager`:
  - `create_state(turn_id, budget)` → `BudgetState`
  - `record_model_call(turn_id)`, `record_tool_call(turn_id, signature)`
  - `is_exhausted(turn_id)` → (bool, reason)
  - `is_tool_repeated(turn_id, signature)` — checks attempt count

### `tools/app_indexer.py` — WindowsAppIndexer (App Discovery & Launch)

**Purpose**: Finds and launches Windows applications via multiple strategies.

**Strategies** (in order):
1. `shell:AppsFolder` COM enumeration (modern/UWP + classic)
2. `Start Menu` shortcuts (`%APPDATA%\Microsoft\Windows\Start Menu\Programs`, `%PROGRAMDATA%\...`)
3. `PATH` executables (`where` command)
4. Known executable map (hardcoded: notepad, calc, explorer, code, chrome, etc.)

**Matching**: `normalize_app_name()` — lower, strip, ё→е, remove .exe, synonyms (блокнот→notepad, обсидиан→obsidian, вскод→code, etc.)

**Launch**: `subprocess.Popen([exe_path], start_new_session=True)` or `os.startfile()` for UWP

**Utilities**: `get_visible_window_titles()`, `get_foreground_window_title()`, `focus_window(title_part)` — Win32 `SetForegroundWindow` + `ShowWindow`

---

## Storage Modules (`modules/storage/`)

### `storage/database.py` — Database (SQLite Wrapper)

**Purpose**: Thread-safe SQLite connection with migrations.

**Features**:
- Single connection (check_same_thread=False), `row_factory=sqlite3.Row`
- `execute()`, `fetchone()`, `fetchall()`, `execute_script()`
- `init_schema()` — creates tables: conversations, messages, memories, artifacts, reminders, plan_steps, background_plans, tool_calls, command_history, settings
- `close()` — commits + closes

### `storage/conversations.py` — ConversationStore

**Purpose**: Persists conversation history per session.

**Methods**:
- `create_session(session_id, title, metadata)` → session_id
- `add_message(session_id, role, content, tool_calls, tool_call_id, metadata)`
- `get_session(session_id)` → dict with messages
- `list_sessions(limit)` → recent sessions
- `delete_session(session_id)`
- `update_session_title()`

### `storage/memories.py` — MemoryStore (SQLite-backed Long-Term Memory)

**Purpose**: Structured key-value memory with categories, separate from BM25 `LocalMemory`.

**Methods**:
- `save(key, value, category="general")` — upsert
- `search(query, limit=10)` — LIKE %query% on key/value
- `get(key)` → value
- `delete(key)`, `clear_all()`, `list_all(category?)`

### `storage/artifacts.py` — ArtifactStore (Large Object Storage)

**Purpose**: Stores large text blobs (logs, code, outputs) with UUID IDs, returns compact references.

**Methods**:
- `store(content, artifact_type="text")` → artifact_id
- `read(artifact_id)` → content
- `delete(artifact_id)`
- `list(limit=50)` → metadata list
- Files stored in `data/artifacts/{id}.txt`

---

## Domain Modules (`modules/domain/`)

### `domain/results.py` — Core Result Types

**Dataclasses**:
- `ToolResult` — success, code, message, data{}, artifacts[], verification, duration_ms, rollback_token, retryable
  - `ok()`, `failure()`, `to_dict()`, `to_model_content()`
- `VerificationResult` — verified (True/False/None), method, confidence, details
- `AssistantResponse` — display_text, speech_text, success, error_code, data{}
  - `ok()`, `failure()`

### `domain/state.py` — RuntimeState (Global Assistant State)

**Enums**:
- `AssistantState`: IDLE, LISTENING, THINKING, SPEAKING, SLEEPING, SHUTTING_DOWN
- `InputMode`: (same as input_hub)

**Class: `RuntimeState`**
- `state`, `input_mode`, `is_active`, `is_shutting_down`
- `set_state()`, `activate()`, `sleep()`, `request_shutdown()`
- `wait_until_active()` — async wait
- `snapshot()` → dict
- Callback on state change (for UI overlay)

### `domain/windows_context.py` — WindowsContext (Session Window Tracking)

**Purpose**: Tracks active application context for reference resolution.

**Methods**:
- `set_application(name)` — current app
- `get_application()` → name
- `set_window_title(title)` — active window
- `get_window_title()` → title
- `resolve_reference(text)` — replaces "там", "тут", "в этом окне", "в активном окне" with actual app/window name

---

## Browser Module (`modules/browser/`)

### `browser/manager.py` — BrowserManager (Playwright Wrapper)

**Purpose**: Manages single persistent Chromium instance for browser agent skills.

**Class: `BrowserManager`**
- `start(headless=False)` — launches browser, creates context/page
- `open_url(url)` — navigates, waits for load
- `get_page_text()` — `page.inner_text("body")`
- `click(selector)` — clicks element
- `fill(selector, value)` — fills input
- `screenshot()` → base64 PNG
- `status()` → {running, url, title}
- `close()` — closes browser

---

## Local Inference (`modules/local/`)

### `local/inference.py` — Local Fallbacks

**Classes**:
- `LocalLLMFallback` — Llama.cpp via `llama_cpp_python`
  - `available` property (checks model file exists)
  - `generate(prompt)` → `LocalInferenceResult(success, text, error)`
  - Model: `data/models/llama-3.2-3b-instruct-q4_k_m.gguf` (configurable via `NOVA_LOCAL_LLM_MODEL`)
  - Params: n_ctx=4096, n_threads=4, temp=0.1, top_p=0.9
- `LocalSTTFallback` — Vosk STT
  - `available` property
  - `transcribe(wav_path)` → `LocalInferenceResult`
  - Model: `NOVA_VOSK_MODEL` env var

**Utilities**:
- `messages_to_local_prompt(messages)` — converts chat history to single prompt with role prefixes
- `LocalInferenceResult` — success, text, error
- `LocalInferenceConfig` — model_path, n_ctx, n_threads, temperature, top_p

---

## Security (`modules/security/`)

### `security/sandbox.py` — Python Sandbox

**Purpose**: Secure execution of untrusted Python code from `execute_python_code` tool.

**Restrictions**:
- **Imports blocked**: os, sys, subprocess, shutil, pathlib, socket, urllib, requests, http, ftplib, smtplib, telnetlib, importlib, pkgutil, runpy, ctypes, multiprocessing, threading (except safe subset), asyncio, signal, resource, gc, sysconfig, platform, cProfile, pstats, trace, faulthandler, _thread, _dummy_thread, importlib.util, importlib.machinery, importlib.abc, importlib.metadata, importlib.resources, zipimport, builtins (restricted), types (restricted), inspect (restricted)
- **Builtins allowed only**: print, len, range, enumerate, zip, map, filter, sorted, reversed, sum, min, max, abs, round, pow, divmod, isinstance, issubclass, hasattr, getattr, setattr, delattr, type, str, int, float, bool, list, tuple, dict, set, frozenset, bytes, bytearray, memoryview, slice, property, staticmethod, classmethod, super, object, Exception, BaseException, ValueError, TypeError, KeyError, IndexError, AttributeError, StopIteration, GeneratorExit, KeyboardInterrupt, SystemExit, NotImplementedError, RuntimeError, ArithmeticError, ZeroDivisionError, OverflowError, ImportError, ModuleNotFoundError, NameError, SyntaxError, IndentationError, TabError, UnicodeError, UnicodeEncodeError, UnicodeDecodeError, UnicodeTranslateError
- **Execution**: `exec()` in restricted globals, 30s timeout via `asyncio.wait_for`
- **Output**: Captures stdout/stderr, returns last expression value if any
- **Result**: `ToolResult` with stdout/stderr/data

---

## UI Modules (`modules/ui/`)

### `ui/overlay.py` — Desktop Overlay Indicator

**Purpose**: Minimal always-on-top window showing Nova status.

**Functions**:
- `start_overlay()` — creates PySide6 QApplication, frameless translucent window
- `stop_overlay()` — closes window, quits app
- `update_status(text, color)` — updates label (СЛУШАЕТ/ДУМАЕТ/ГОВОРИТ/СПИТ/ОШИБКА)

### `ui/desktop.py` — Main Desktop Window (PySide6)

**Purpose**: Full-featured control panel.

**Tabs**:
- **Overview** — live state, quick actions
- **Processes** — list/manage background processes
- **Memory** — browse/delete long-term memories
- **Permissions** — approve/deny pending confirmations
- **Models** — provider/key status, model selection
- **Journal** — command log

**Communication**: Via `CoreDesktopBridge` (see below).

### `ui/core_bridge.py` — CoreDesktopBridge (UI ↔ Core)

**Purpose**: Async bridge between Qt main thread and Nova async core.

**Exposed Methods** (called from Qt):
- `get_state_snapshot()` → RuntimeState + PreferencesSnapshot
- `send_text_command(text)` → submits to InputCoordinator
- `toggle_voice_mode()` → InteractionModeManager.toggle_manual_voice()
- `set_input_mode(mode)` / `set_assistant_profile()` / `set_model_mode()`
- `confirm_pending_operation(op_id)` / `deny_pending_operation()`
- `get_pending_operations()`
- `get_conversation_history()`
- `get_memory_list()` / `delete_memory()` / `clear_all_memories()`
- `get_artifact_list()` / `read_artifact()` / `delete_artifact()`
- `get_background_plans()` / `cancel_background_plan()`
- `terminate_process(process_id)` / `read_process_output()`
- `shutdown()` — triggers RuntimeState shutdown

**Threading**: Uses `asyncio.run_coroutine_threadsafe` to submit to core event loop.

### `ui/desktop_service.py` — DesktopService (Lifecycle)

**Purpose**: Starts/stops Qt application in background thread.

**Class: `DesktopService`**
- `start()` — spawns thread running `QApplication.exec()`
- `stop()` — posts quit event
- `publish(event_type, data)` — emits to connected clients (WebSocket/Qt signals)

### `ui/desktop_protocol.py` — Message Protocol

**Purpose**: Defines event types for UI communication.

**Events**: state_update, assistant_message, command_log, process_update, permission_request, memory_update, artifact_update, plan_update, model_status, shutdown

---

## Windows-Specific Modules (`modules/windows/`)

### `windows/filesystem.py` — File Operations with Backup

**Tools** (all return `ToolResult`):
- `read_text_file(path)` — UTF-8 read
- `write_text_file(path, content, create_backup=True)` — writes, creates `.bak.N` on change
- `apply_text_patch(path, patch)` — unified diff format (+ add, - remove, = replace)
- `get_file_diff(path)` — diff vs latest backup
- `search_files(directory, pattern, max_results=100, recursive=True)` — glob/rglob
- `rollback_file(path)` — restores latest backup

**Backup Logic**: `data/backups/{relative_path}.bak.{N}` (rotating)

### `windows/git_tools.py` — Git Operations

**Tools**:
- `git_status(repo_path)` — porcelain status
- `git_diff(repo_path, staged=False)` — diff
- `git_log(repo_path, max_count=10)` — oneline log
- `git_commit(repo_path, message, add_all=False)` — commit
- `git_branch(repo_path)` — branch list
- `inspect_project(project_path)` — detects language, framework, docker, CI, tests, entry points

### `windows/process_manager.py` — ProcessManager (Background Processes)

**Class: `ProcessManager`**
- `start_process(command[], label?, cwd?)` → process_id (UUID)
  - Stores: Popen object, label, cwd, start_time, stdout/stderr buffers (deque maxlen=1000)
- `get_process_status(process_id)` → {pid, label, status, uptime, returncode}
- `read_process_output(process_id, max_lines=100, stream="stdout")` → lines
- `stop_process(process_id, force=False)` — terminate/kill
- `list_processes()` → all managed
- `cleanup_all()` — force stop all on shutdown

**Streaming**: Background threads read stdout/stderr into deques.

### `windows/project_inspector.py` — ProjectInspector

**Purpose**: Static analysis of project structure.

**`inspect_project(project_path)`** → dict:
- language (Python/JS/TS/Go/Rust/Java/C#/C++/PHP/Ruby/Shell)
- framework (FastAPI/Django/Flask/React/Vue/Next/Express/Nest/Actix/Axum/Spring/Gin/Echo/.NET)
- has_docker, has_git, has_ci, has_tests
- entry_points (main.py, app.py, manage.py, package.json scripts, Cargo.toml, pom.xml, etc.)
- config_files, dependencies

---

## Scripts

### `scripts/install_dependencies.py` — Automated Setup

**Actions**:
1. Creates venv if missing
2. `pip install -r requirements.txt`
3. `pip install torch --index-url https://download.pytorch.org/whl/cpu`
4. `pip install playwright` + `playwright install chromium`
5. Downloads Vosk model (if `NOVA_VOSK_MODEL` set and missing)
6. Downloads Silero model (v5_ru.pt)
7. Downloads local LLM (llama-3.2-3b-instruct-q4_k_m.gguf)

### `scripts/build_installer.py` — PyInstaller Build

**Output**: `dist/Nova.exe` (single-file executable)

**Includes**: All modules, data files (models, configs), hidden imports for PySide6, sounddevice, vosk, llama_cpp, playwright

---

## Testing (`tests/`)

**220+ Tests** covering:
- `test_smoke.py` — basic import/startup
- `test_input_models.py`, `test_input_coordinator.py` — input hub
- `test_intent_router.py` — routing accuracy
- `test_wake_word.py` — wake detection
- `test_speech_service.py` — TTS queue/interrupt
- `test_model_gateway_cooldowns.py` — cooldown logic
- `test_local_inference.py` — fallback paths
- `test_planning.py`, `test_plan_service.py` — plan validation/execution
- `test_background_plans.py` — async plan management
- `test_recovery.py` — error recovery decisions
- `test_direct_executor.py` — LLM-free paths
- `test_request_dispatcher.py`, `test_request_service.py` — request flow
- `test_preferences.py`, `test_interaction_modes.py` — settings
- `test_artifacts.py`, `test_database.py`, `test_conversations.py`, `test_memories.py` — storage
- `test_filesystem.py`, `test_process_manager.py`, `test_git_tools.py`, `test_project_inspector.py` — Windows tools
- `test_skills_v2.py` — high-level skills
- `test_browser_manager.py` — Playwright
- `test_tool_platform.py` — registry/runner/policy
- `test_policy.py`, `test_permissions.py`, `test_budgets.py` — tool platform
- `test_reporting.py` — response building
- `test_security_redteam.py` — sandbox escape attempts
- `test_crash_recovery.py` — crash/restart scenarios

---

## Data Flow Summary

```
User Input (Voice/Text/UI)
         │
         ▼
InputCoordinator (queue)
         │
         ▼
RequestService (sequential processor)
         │
         ▼
RequestDispatcher ──→ ExecutionDecision (IntentRouter)
         │                    │
         │         ┌──────────┴──────────┐
         │         ▼                     ▼
         │   DIRECT              AgentService (LLM loop)
         │   (DirectExecutor)          │
         │                             ▼
         │                    ┌─────────────────┐
         │                    │ Tool Selection  │
         │                    │ (router + heur.)│
         │                    └────────┬────────┘
         │                             ▼
         │                    ToolRunner.execute()
         │                             │
         │                    ┌────────┴────────┐
         │                    ▼                 ▼
         │            PermissionManager    Tool Handler
         │            (Policy + Confirm)   (os_utils, skills, etc.)
         │                    │                 │
         │                    └────────┬────────┘
         │                             ▼
         │                    ToolResult (verified)
         │                             │
         ▼                             ▼
Agent Loop ◀──────────────────────────┘
         │
         ▼
Final Report (local, no LLM)
         │
         ▼
ResponseHandler → SpeechService (TTS queue) + Desktop UI
```

---

## Key Design Patterns

1. **Skill-First Routing**: High-level skills (`write_in_application`) preferred over atomic tools; intent router returns `selected_skill`

2. **Deterministic Final Reports**: Agent never uses LLM for final summary; `reporting.py` builds response from verified tool results

3. **Generation-Based Interrupt**: SpeechService uses generation counter to invalidate stale queue items without cancelling parent tasks

4. **Cooldown Hierarchy**: ModelGateway applies failures at correct granularity (key → route → model → provider)

5. **Budget-Driven Loop**: Agent tracks model calls, tool calls, wall time, repeated tools per turn

5. **Single Request Serialization**: RequestService processes one request at a time to prevent GUI/clipboard conflicts

6. **Dual Transcription**: Wake word captures audio → high-quality re-transcription via Whisper

7. **Local-First Fallback**: Cloud LLM → Local LLM (text-only) → Local STT (Vosk)

8. **Structured Tool Results**: Every tool returns `ToolResult` with verification metadata; deduplication by canonical signature

---

## Extension Points

| Area | Extension Method |
|------|-----------------|
| New Tool | Add schema to `tools/registry.py`, handler to `tools/os_utils.py` or new module, register in `main.py` |
| New Skill | Add method to `WindowsSkills` in `tools/skills.py`, expose via tool schema |
| New Intent | Add `IntentKind`, update `DeterministicIntentRouter.route()`, add case in `DirectRequestExecutor` or `AgentService` |
| New Model Provider | Extend `ModelGateway` with new client, add model lists to `config.py`, update `ModelRouter` |
| New Storage Backend | Implement `BaseMemory` interface, wire in `LocalMemory` init |
| New UI Tab | Add widget to `ui/desktop.py`, expose data via `CoreDesktopBridge` |

---

## Security Model

1. **Sandbox**: `execute_python_code` runs in restricted namespace with import/builtin whitelist
2. **Permission Gates**: `PermissionManager` enforces policy + user confirmation for destructive actions
3. **Path Restrictions**: File tools operate within user directories; system paths blocked
4. **Command Whitelist**: `execute_cmd_command` only allows predefined commands
5. **No Arbitrary Code**: LLM cannot execute unsandboxed Python; no `eval`/`exec` in tool handlers
6. **API Key Isolation**: Keys never logged, never sent to LLM, rotated on failure

---

## Performance Characteristics

| Operation | Typical Latency |
|-----------|-----------------|
| Wake word detection | ~50ms (Vosk streaming) |
| Whisper transcription (Groq) | 500ms–2s |
| Local STT (Vosk) | 200–500ms |
| Silero TTS (CPU) | 100–300ms per chunk |
| LLM call (Groq) | 200–800ms |
| LLM call (OpenRouter) | 500–2000ms |
| Tool execution (atomic) | 50–500ms |
| Skill (write_in_application) | 1–3s |
| Plan execution (5 steps) | 5–15s |

---

## Configuration Reference

See `core/config.py` and `.env.example` for all environment variables.

Critical variables:
- `GROQ_API_KEYS` / `OPENROUTER_API_KEYS` — **required**
- `NOVA_VOSK_MODEL` — path to Vosk model directory (for wake word)
- `NOVA_WAKE_WORD_ENABLED=true` — enables wake word mode
- `NOVA_DESKTOP_UI=false` — disables PySide6 UI
- `NOVA_ENABLE_LOCAL_LLM_FALLBACK=true` — enables local LLM/STT fallback

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "No API keys found" | Missing `.env` | Copy `.env.example` to `.env`, add keys |
| Wake word not working | Vosk model not found | Set `NOVA_VOSK_MODEL` to extracted model dir |
| TTS not speaking | Silero model missing | Run `scripts/install_dependencies.py` |
| Tools not executing | Permission denied | Check Desktop UI → Permissions tab |
| High memory usage | Local LLM loaded | Disable `NOVA_ENABLE_LOCAL_LLM_FALLBACK` |
| "Model route failed" | All keys on cooldown | Wait or add more API keys |

---

This documentation covers the architecture, modules, data flows, and extension points of Nova as of the current codebase. For implementation details, refer to the source files in `modules/`.