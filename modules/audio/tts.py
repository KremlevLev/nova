# modules/audio/tts.py
import os
import logging
import sounddevice as sd
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
    """Синтезирует и озвучивает текст через Silero v5 напрямую в ОЗУ с поддержкой прерывания"""
    if not text:
        return
        
    cleaned_text = text.strip()
    
    # ЗАЩИТА ОТ ОШИБОК СИНТЕЗА:
    # Проверяем, содержит ли строка хотя бы одну букву (русскую или английскую).
    # Если букв нет (например, пришли только кавычки, точки, скобки или пробелы), пропускаем.
    if not any(char.isalpha() for char in cleaned_text):
        logger.debug(f"Пропуск озвучки строки без букв: '{cleaned_text}'")
        return
        
    # ФАЗА 1: Прерываемся перед началом работы, если флаг затыкания уже установлен
    if _speech_interrupted:
        logger.debug("Воспроизведение отменено: зафиксирован флаг прерывания речи.")
        return
        
    # Печатаем реплику только если она действительно будет озвучена
    print(f"\n[🔊 Nova Говорит]: {cleaned_text}")
    
    model = _get_silero_engine()
    if not model:
        logger.error("Голосовой движок Silero не запущен.")
        return
        
    try:
        sample_rate = 24000  # 24 кГц
        
        # ФАЗА 2: Проверка непосредственно перед тяжелым синтезом нейросети
        if _speech_interrupted:
            return
            
        # Генерация аудио
        audio = model.apply_tts(
            text=cleaned_text,
            speaker=speaker,
            sample_rate=sample_rate,
            put_accent=True,      # Автоматическое расставление ударений
            put_yo=True           # Автоматическая замена 'е' на 'ё'
        )
        
        # ФАЗА 3: Проверка перед самой отправкой аудио на звуковую карту
        if _speech_interrupted:
            return
            
        audio_data = audio.numpy()
        sd.play(audio_data, sample_rate)
        sd.wait()  # При вызове sd.stop() в другом потоке этот метод мгновенно разблокируется
        
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
            # Если прилетел сигнал стоп — очищаем очередь и выходим
            if _speech_interrupted:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()  # Подтверждаем сброс фоновых элементов
                    except asyncio.QueueEmpty:
                        break
                # Текущий элемент подтвердится автоматически в блоке finally при выходе
                break
                
            await asyncio.to_thread(speak, sentence)
        except Exception as e:
            logger.error(f"Ошибка TTS воркера: {e}")
        finally:
            queue.task_done()  # Вызывается ровно один раз для извлеченного элемента

_speech_interrupted = False

def stop_speaking():
    """Моментально останавливает текущее воспроизведение и взводит флаг прерывания"""
    global _speech_interrupted
    _speech_interrupted = True
    try:
        sd.stop()  # Win32-метод sounddevice мгновенно обрывает поток в динамиках
    except Exception:
        pass
    print("\n[🔇 Nova]: Воспроизведение прервано.")

def is_interrupted() -> bool:
    return _speech_interrupted

def reset_interrupt_flag():
    global _speech_interrupted
    _speech_interrupted = False