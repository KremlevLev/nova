# py -m modules.audio.tts
import os
import logging
import sounddevice as sd
import numpy as np
import re
import asyncio
import torch

logger = logging.getLogger("TTS")

# Путь для хранения JIT-модели Silero v5
MODEL_PATH = "data/v5_ru.pt"
_silero_model = None
_device = torch.device('cpu')

def _get_silero_engine():
    """Ленивая инициализация Silero TTS v5 на CPU"""
    global _silero_model
    if _silero_model is None:
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        
        # Автоматическое скачивание модели при первом запуске
        if not os.path.exists(MODEL_PATH):
            logger.info("Файл модели Silero v5 не найден. Начинаю загрузку с официального сервера...")
            try:
                torch.hub.download_url_to_file('https://models.silero.ai/models/tts/ru/v5_ru.pt', MODEL_PATH)
                logger.info("Модель Silero v5 успешно загружена на диск.")
            except Exception as e:
                logger.error(f"Не удалось скачать модель Silero v5: {e}")
                return None
                
        try:
            logger.info("Загрузка Silero v5 в оперативную память...")
            torch.set_num_threads(4)  # Ограничение потоков для предотвращения перегрузки CPU
            _silero_model = torch.package.PackageImporter(MODEL_PATH).load_pickle("tts_models", "model")
            _silero_model.to(_device)
            logger.info("Модель Silero v5 готова к синтезу речи.")
        except Exception as e:
            logger.error(f"Ошибка при инициализации Silero v5: {e}")
    return _silero_model

def speak(text: str, speaker: str = "baya"):
    """Синтезирует и озвучивает текст через Silero v5 напрямую в ОЗУ"""
    if not text:
        return
        
    print(f"\n[🔊 Nova Говорит]: {text}")
    
    model = _get_silero_engine()
    if not model:
        logger.error("Голосовой движок Silero не запущен.")
        return
        
    try:
        sample_rate = 24000  # 24 кГц — оптимальный баланс качества и скорости на CPU
        
        # Генерация аудио
        audio = model.apply_tts(
            text=text.strip(),
            speaker=speaker,
            sample_rate=sample_rate,
            put_accent=True,      # Автоматическое расставление ударений
            put_yo=True          # Автоматическая замена 'е' на 'ё'
        )
        
        audio_data = audio.numpy()
        sd.play(audio_data, sample_rate)
        sd.wait()
        
    except Exception as e:
        logger.error(f"Ошибка во время синтеза или воспроизведения Silero: {e}")


# --- ГОЛОСОВЫЕ ФИЛЬТРЫ И АСИНХРОННЫЙ ПЛЕЕР (ДЛЯ РАБОТЫ В СОСТАВЕ MAIN.PY) ---

def is_text_code_or_json(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return False
    if "{" in clean and "}" in clean:
        return True
    if '"name":' in clean or '"parameters":' in clean or '"function":' in clean:
        return True
    if clean.startswith("[") and clean.endswith("]"):
        return True
    return False

def is_inside_xml_block(text: str, allowed_tool_names: list[str]) -> bool:
    open_func_tags = text.count("<function=")
    close_func_tags = text.count("</function>")
    if open_func_tags > close_func_tags:
        return True
    for func_name in allowed_tool_names:
        open_count = text.count(f"<{func_name}>")
        close_count = text.count(f"</{func_name}>")
        if open_count > close_count:
            return True
    last_bracket = text.rfind("<")
    if last_bracket > text.rfind(">"):
        return True
    return False

def clean_text_for_speech(text: str, allowed_tool_names: list[str]) -> str:
    cleaned = text
    cleaned = re.sub(r'<function=\w+>.*?</`function>', '', cleaned, flags=re.DOTALL)
    for func_name in allowed_tool_names:
        pattern = re.compile(rf'<{func_name}>.*?</{func_name}>', re.DOTALL)
        cleaned = pattern.sub('', cleaned)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

async def speak_worker(queue: asyncio.Queue):
    while True:
        sentence = await queue.get()
        if sentence is None:
            queue.task_done()
            break
        try:
            await asyncio.to_thread(speak, sentence)
        except Exception as e:
            logger.error(f"Ошибка TTS воркера: {e}")
        finally:
            queue.task_done()


# --- БЛОК ЗАМЕРА СКОРОСТИ ---
if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    
    print("\n--- Запуск теста скорости Silero TTS v5 (Голос: baya) ---")
    
    # 1. Первый запуск (Холодный старт: скачивание + чтение + первый прогрев)
    t0 = time.perf_counter()
    speak("Привет! Это первая фраза. Сейчас модель загружается в оперативную память вашего компьютера.")
    print(f"⏱️ Время первого запуска (с загрузкой моделей): {time.perf_counter() - t0:.2f} сек.\n")
    
    # 2. Второе воспроизведение (Горячий старт из ОЗУ)
    t0 = time.perf_counter()
    speak("А это вторая фраза. Она должна сгенерироваться гораздо быстрее, так как файлы уже в оперативной памяти.")
    print(f"⏱️ Время второго запуска (горячий старт): {time.perf_counter() - t0:.2f} сек.\n")
    
    # 3. Третий запуск (Реальный системный ответ)
    t0 = time.perf_counter()
    speak("Блокнот успешно открыт.")
    print(f"⏱️ Время генерации короткого ответа: {time.perf_counter() - t0:.2f} сек.\n")