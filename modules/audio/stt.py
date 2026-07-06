# py -m modules.audio.stt
import os
import logging
import speech_recognition as sr
from faster_whisper import WhisperModel

# Фикс возможной ошибки с библиотеками на Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger("STT")
logging.basicConfig(level=logging.INFO)
class VoiceListener:
    def __init__(self):
        # Используем модель "small" (весит ~400мб, скачается сама при первом запуске). 
        # Она в 10 раз умнее маленького Vosk. Если у вас мощный ПК, можно поставить "medium".
        logger.info("Загрузка нейросети Whisper (Уши)...")
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.recognizer = sr.Recognizer()
        
        # === НАСТРОЙКА ПАУЗ (То, что решит вашу проблему) ===
        # Сколько секунд тишины ждать, прежде чем завершить фразу
        self.recognizer.pause_threshold = 1.5 
        # Автоматическая подстройка под шум кулеров
        self.recognizer.dynamic_energy_threshold = True 
        
        logger.info("Whisper успешно загружен!")

    def listen(self) -> str:
        """Умное прослушивание с подавлением шума и ожиданием конца фразы"""
        with sr.Microphone() as source:
            print("\n[🎤] Калибровка фона...")
            # Слушаем фон 1 секунду, чтобы отсечь шум компьютера
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            
            print("[🎤] Говорите (я дождусь конца фразы)...")
            try:
                # Слушаем микрофон (ждет, пока вы не замолчите на 1.5 секунды)
                audio = self.recognizer.listen(source, timeout=None)
                
                # Сохраняем аудио во временный файл (Whisper так работает быстрее всего)
                temp_file = "data/temp_mic.wav"
                os.makedirs("data", exist_ok=True)
                with open(temp_file, "wb") as f:
                    f.write(audio.get_wav_data())
                    
                # Распознаем текст с помощью Whisper
                segments, _ = self.model.transcribe(temp_file, language="ru", beam_size=5)
                
                # Склеиваем результат
                text = " ".join([segment.text for segment in segments]).strip()
                
                if text:
                    print(f"[Вы сказали]: {text}")
                return text
                
            except Exception as e:
                logger.error(f"Ошибка при распознавании речи: {e}")
                return ""