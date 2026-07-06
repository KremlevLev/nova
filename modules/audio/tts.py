# py -m modules.audio.tts
import pyttsx3
import logging

logger = logging.getLogger("TTS")

def speak(text: str):
    """Озвучивает текст, безопасно создавая движок при каждом вызове (защита от зависаний)"""
    if not text:
        return
        
    print(f"\n[🔊 Nova Говорит]: {text}")
    
    try:
        # pythoncom нужен, чтобы Windows не блокировал звук в асинхронных потоках
        import pythoncom
        pythoncom.CoInitialize() 
        
        engine = pyttsx3.init()
        
        voices = engine.getProperty('voices')
        for voice in voices:
            if 'ru' in voice.languages or 'Russian' in voice.name or 'Ирина' in voice.name or 'Pavel' in voice.name:
                engine.setProperty('voice', voice.id)
                break
                
        engine.setProperty('rate', 180)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.error(f"Ошибка голосового движка: {e}")