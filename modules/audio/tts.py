# py -m modules.audio.tts
import pyttsx3
import logging

logger = logging.getLogger("TTS")

def init_engine():
    engine = pyttsx3.init()
    
    # Пытаемся найти русский голос в системе
    voices = engine.getProperty('voices')
    for voice in voices:
        if 'ru' in voice.languages or 'Russian' in voice.name or 'Ирина' in voice.name or 'Pavel' in voice.name:
            engine.setProperty('voice', voice.id)
            break
            
    # Настройки голоса
    engine.setProperty('rate', 180) # Скорость речи (по умолчанию обычно 200)
    engine.setProperty('volume', 1.0) # Громкость (от 0 до 1)
    
    return engine

# Инициализируем один раз при импорте
engine = init_engine()

def speak(text: str):
    """Озвучивает переданный текст"""
    if not text:
        return
        
    print(f"\n[🔊 Nova Говорит]: {text}")
    engine.say(text)
    engine.runAndWait()
