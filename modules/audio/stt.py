# py -m modules.audio.stt
import os
import wave
import logging
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# Защита от конфликта библиотек в Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger("STT")

class VoiceListener:
    def __init__(self):
        logger.info("Загрузка нейросети Whisper (Уши)...")
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        
        # Настройки аудио
        self.sample_rate = 16000
        self.block_size = 2048
        self.silence_duration = 1.5  # <--- ТЕ САМЫЕ ПОЛТОРЫ СЕКУНДЫ ОЖИДАНИЯ
        
        logger.info("Whisper успешно загружен!")

    def _get_rms(self, data):
        """Математическое вычисление громкости (Root Mean Square) куска аудио"""
        # Превращаем звук в числа от -1.0 до 1.0 и считаем среднюю громкость
        return np.sqrt(np.mean(np.square(data.astype(np.float32) / 32768.0)))

    def listen(self) -> str:
        """Слушает микрофон, автоматически калибрует шум и ждет конца фразы"""
        # Открываем микрофон через sounddevice (работает без PyAudio!)
        with sd.InputStream(samplerate=self.sample_rate, channels=1, blocksize=self.block_size, dtype='int16') as stream:
            
            print("\n[🎤] Калибровка фона...")
            bg_rms_list = []
            
            # Читаем 1 секунду тишины, чтобы понять, как сильно шумит кулер ПК
            for _ in range(int(self.sample_rate / self.block_size)):
                data, overflow = stream.read(self.block_size)
                bg_rms_list.append(self._get_rms(data))
            
            # Ставим порог срабатывания: средний шум комнаты x 2.0
            energy_threshold = np.mean(bg_rms_list) * 2.0
            if energy_threshold < 0.005:  # Если в комнате идеальная тишина, ставим минимальный порог
                energy_threshold = 0.005
            
            print("[🎤] Говорите (я дождусь конца фразы)...")
            
            audio_buffer = []
            started_speaking = False
            silence_chunks = 0
            
            # Считаем, сколько чанков нужно для 1.5 секунд тишины
            max_silence_chunks = int((self.silence_duration * self.sample_rate) / self.block_size)
            
            while True:
                data, overflow = stream.read(self.block_size)
                rms = self._get_rms(data)
                
                if rms > energy_threshold:
                    # Человек начал говорить
                    started_speaking = True
                    silence_chunks = 0
                    audio_buffer.append(data)
                elif started_speaking:
                    # Человек молчит (пауза между словами)
                    silence_chunks += 1
                    audio_buffer.append(data)
                    
                    if silence_chunks > max_silence_chunks:
                        break # Тишина длилась 1.5 секунды - завершаем фразу!
                else:
                    # Держим в буфере полсекунды записи ДО того как человек начал говорить, 
                    # чтобы не "съедалась" первая буква первого слова
                    audio_buffer.append(data)
                    if len(audio_buffer) > int((0.5 * self.sample_rate) / self.block_size):
                        audio_buffer.pop(0)

        # Сохраняем записанный голос во временный файл
        temp_file = "data/temp_mic.wav"
        os.makedirs("data", exist_ok=True)
        
        final_audio = np.concatenate(audio_buffer)
        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(final_audio.tobytes())
            
        # Отправляем файл в Whisper
        try:
            segments, _ = self.model.transcribe(temp_file, language="ru", beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            
            if text:
                print(f"[Вы сказали]: {text}")
            return text
        except Exception as e:
            logger.error(f"Ошибка при распознавании речи: {e}")
            return ""