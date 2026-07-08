# modules/audio/stt.py
import os
import wave
import logging
import numpy as np
import sounddevice as sd
import requests
from core.config import GROQ_API_KEY

# Защита от конфликта библиотек в Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger("STT")

class VoiceListener:
    def __init__(self):
        logger.info("Инициализация захвата звука (Уши)...")
        if not GROQ_API_KEY:
            logger.warning("Критическая ошибка: GROQ_API_KEY не обнаружен в конфигурации!")
            
        # Настройки аудио
        self.sample_rate = 16000
        self.block_size = 2048
        self.silence_duration = 1.2  # Время ожидания тишины (сокращено с 1.5 для скорости)
        logger.info("Система аудиозахвата готова. Инференс: Groq API (whisper-large-v3-turbo)")

    def _get_rms(self, data):
        """Математическое вычисление громкости (Root Mean Square) куска аудио"""
        return np.sqrt(np.mean(np.square(data.astype(np.float32) / 32768.0)))

    def listen(self) -> str:
        """Слушает микрофон, автоматически калибрует шум и ждет конца фразы"""
        with sd.InputStream(samplerate=self.sample_rate, channels=1, blocksize=self.block_size, dtype='int16') as stream:
            
            print("\n[🎤] Калибровка фона...")
            bg_rms_list = []
            
            # Читаем 1 секунду тишины, чтобы понять шум комнаты
            for _ in range(int(self.sample_rate / self.block_size)):
                data, overflow = stream.read(self.block_size)
                bg_rms_list.append(self._get_rms(data))
            
            # Порог срабатывания: средний шум комнаты x 2.0
            energy_threshold = np.mean(bg_rms_list) * 2.0
            if energy_threshold < 0.005:
                energy_threshold = 0.005
            
            print("[🎤] Говорите (я дождусь конца фразы)...")
            
            audio_buffer = []
            started_speaking = False
            silence_chunks = 0
            
            # Вычисляем лимит чанков тишины
            max_silence_chunks = int((self.silence_duration * self.sample_rate) / self.block_size)
            
            while True:
                data, overflow = stream.read(self.block_size)
                rms = self._get_rms(data)
                
                if rms > energy_threshold:
                    started_speaking = True
                    silence_chunks = 0
                    audio_buffer.append(data)
                elif started_speaking:
                    silence_chunks += 1
                    audio_buffer.append(data)
                    
                    if silence_chunks > max_silence_chunks:
                        break  # Зафиксировано окончание фразы
                else:
                    # Удерживаем пред-запись (0.5 сек), чтобы не обрезать начало фразы
                    audio_buffer.append(data)
                    if len(audio_buffer) > int((0.5 * self.sample_rate) / self.block_size):
                        audio_buffer.pop(0)

        # Сохраняем записанный аудиопоток во временный WAV-файл
        temp_file = "data/temp_mic.wav"
        os.makedirs("data", exist_ok=True)
        
        final_audio = np.concatenate(audio_buffer)
        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(final_audio.tobytes())
            
        # Отправка WAV-файла на транскрибацию в Groq API
        if not GROQ_API_KEY:
            logger.error("Ошибка распознавания: GROQ_API_KEY отсутствует.")
            return ""

        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}"
            }
            
            with open(temp_file, "rb") as f:
                files = {
                    "file": ("temp_mic.wav", f, "audio/wav")
                }
                data = {
                    "model": "whisper-large-v3-turbo",
                    "language": "ru" # Жесткое указание языка исключает галлюцинации и ускоряет инференс
                }
                
                response = requests.post(url, headers=headers, files=files, data=data, timeout=8.0)
            
            if response.status_code == 200:
                text = response.json().get("text", "").strip()
                if text:
                    print(f"[Вы сказали]: {text}")
                return text
            else:
                logger.error(f"Ошибка Groq API STT (HTTP {response.status_code}): {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"Не удалось связаться с Groq API STT: {e}")
            return ""