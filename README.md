<div align="center">

# ⚡ Nova — ваш локальный ИИ-агент для Windows

### **Голосовой ассистент, инженерный копилот и автоматизатор рабочего стола**

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-90%2B%20passing-brightgreen.svg)](tests/)

</div>

---

## 🎥 Что умеет Nova

| Возможность | Пример команды |
|---|---|
| 🎤 Голосовое управление | «Открой Obsidian и напиши стих» |
| 🖥️ Управление окнами | «Сверни все окна», «Открой блокнот» |
| 📝 Запись в приложения | «Напиши заметку в Obsidian» |
| 🐚 Терминал и процессы | «Запусти сервер», «Покажи логи» |
| 📁 Файлы и Git | «Сделай коммит», «Покажи diff» |
| 🔍 Поиск в интернете | «Найди документацию по FastAPI» |
| ⏰ Напоминания | «Напомни через 10 минут проверить тесты» |
| 🧠 Долговременная память | «Запомни, мой любимый редактор — VS Code» |
| 🔄 Отказоустойчивость | Автоматический fallback между Groq и OpenRouter |
| 🔒 Безопасность | Подтверждение опасных действий, запрет записи в системные каталоги |

---

## 🚀 Быстрый старт

### 1. Установите Python 3.14

Скачайте с [python.org](https://www.python.org/downloads/) и установите, обязательно отметьте **Add to PATH**.

### 2. Клонируйте репозиторий

```powershell
git clone https://github.com/ваш-username/nova.git
cd nova
```

### 3. Настройте API-ключи

Создайте файл `.env` в корне проекта:

```env
GROQ_API_KEYS=gsk_ваш_ключ
OPENROUTER_API_KEYS=sk-or-ваш_ключ
```

**Где взять ключи:**
* **Groq**: [console.groq.com](https://console.groq.com) — бесплатно, до 30 запросов в минуту.
* **OpenRouter**: [openrouter.ai](https://openrouter.ai) — бесплатные модели, резервный провайдер.

### 4. Установите зависимости

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 5. Запустите Nova

```powershell
python -m main
```

### 6. Активируйте голос

Нажмите `Ctrl+Shift+Space` и скажите:
> *Открой блокнот и напиши привет*

---

## 🎮 Горячие клавиши

| Клавиша | Действие |
|---|---|
| `Ctrl+Shift+Space` | Включить/выключить голосовой режим |
| `Esc` | Прервать речь Nova |
| `Ctrl+Shift+Q` | Прервать речь Nova |

---

## 🧪 Тестирование

```powershell
# Запустить все тесты
python -m pytest -v

# Запустить конкретный тест
python -m pytest tests/test_speech_service.py -v
```

---

## 🏗️ Архитектура

```text
nova/
├── core/              # Конфигурация, системный промпт
├── modules/
│   ├── application/   # Агент, речь, отчёты
│   ├── audio/         # STT (Whisper), TTS (Silero)
│   ├── brain/         # LLM, память, роутер моделей
│   ├── domain/        # Результаты, состояния, события
│   ├── storage/       # SQLite, история, память
│   ├── tools/         # Реестр, раннер, политики, навыки
│   └── windows/       # Файлы, процессы, Git, UI Automation
├── data/              # Локальные данные (память, логи, бэкапы)
├── tests/             # 90+ тестов
└── main.py            # Точка входа
```

---

## 📊 Прогресс разработки

| Этап | Статус |
|---|---|
| Голосовой lifecycle | ✅ |
| Cooldown ключей и моделей | ✅ |
| Единая платформа инструментов | ✅ |
| Policy Engine и HITL | ✅ |
| Process Manager | ✅ |
| Файловая система с backup | ✅ |
| Git-инструменты | ✅ |
| Инспектор проектов | ✅ |
| SQLite и память | ✅ |
| Artifact Store | 🟡 |
| UI Automation | ⬜ |
| Desktop UI | ⬜ |
| Браузерный агент | ⬜ |
| Локальные модели | ⬜ |

---

## 🤝 Вклад в проект

Pull Request'ы приветствуются. Пожалуйста, убедитесь, что тесты проходят:

```powershell
python -m pytest -v
```

---

## 📄 Лицензия

[MIT](LICENSE)
```
