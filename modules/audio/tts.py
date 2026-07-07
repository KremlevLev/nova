# py -m modules.audio.tts
import logging
import os
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig  # Импортируем SynthesisConfig
import numpy as np

logger = logging.getLogger("TTS")

# Путь к локальной ONNX модели Piper в папке data
MODEL_PATH = "data/piper_model.onnx"

# Глобальный объект синглтона для голоса
_voice_engine = None

def _get_piper_engine():
    """Инициализирует движок Piper один раз за запуск"""
    global _voice_engine
    if _voice_engine is None:
        if not os.path.exists(MODEL_PATH):
            logger.error(f"Файл модели Piper не найден в {MODEL_PATH}!")
            return None
        try:
            logger.info("Загрузка локальной ONNX модели Piper TTS через официальную библиотеку...")
            
            # Загружаем модель. Piper сам найдет рядом файл .json, прочитает настройки 
            # и создаст внутри сессию onnxruntime с оптимизацией под CPU.
            _voice_engine = PiperVoice.load(MODEL_PATH)
            
            logger.info(f"Движок Piper успешно запущен. Частота: {_voice_engine.config.sample_rate} Гц")
        except Exception as e:
            logger.error(f"Ошибка инициализации Piper движка: {e}")
    return _voice_engine

def speak(text: str):
    """Озвучивает русский текст через Piper ONNX напрямую в аудиокарту"""
    if not text:
        return
        
    print(f"\n[🔊 Nova Говорит]: {text}")
    
    voice = _get_piper_engine()
    if not voice:
        return
    
    try:
        # Очищаем текст от лишних пробелов по краям
        prepared_text = text.strip()

        # Создаем конфигурацию синтеза речи
        # Параметр length_scale управляет скоростью: < 1.0 (например, 0.9) — быстрее; > 1.0 — медленнее.
        syn_config = SynthesisConfig(
            length_scale=0.9,  # Умеренно быстрая, естественная скорость для русского голоса
            volume=1.0         # Максимальная громкость
        )

        # Вызываем метод .synthesize, передавая настроенный конфиг
        audio_chunks = voice.synthesize(prepared_text, syn_config=syn_config)
        
        # Собираем байты (PCM int16), обращаясь к свойству .audio_int16_bytes каждого чанка
        audio_bytes = b"".join(chunk.audio_int16_bytes for chunk in audio_chunks)
        
        # Переводим сырые байты в одномерный массив numpy int16
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

        # Воспроизводим моно-звук напрямую через sounddevice
        sd.play(audio_data, voice.config.sample_rate)
        sd.wait()  # Ожидаем окончания воспроизведения фразы
        
    except Exception as e:
        logger.error(f"Ошибка генерации или воспроизведения Piper: {e}")


# Блок для мгновенной проверки модуля
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_phrase = (
    "Привет. Я обновил движок синтеза речи, так что теперь всё работает локально и без задержек. "
    "По железу проверил — нагрузка в норме, оперативки хватает, система крутится стабильно. "
    "В общем, я на связи и готов кодить. Какой у нас план? Начнем с разбора кода, "
    "или нужно подтянуть какие-то логи и проверить задачи?"
)

    speak(test_phrase)