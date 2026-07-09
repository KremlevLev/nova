# modules/audio/stt.py
import os
import wave
import logging
import numpy as np
import sounddevice as sd
import requests
from core.config import GROQ_API_KEY

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
logger = logging.getLogger("STT")

# Известные галлюцинации Whisper при обработке фонового шума или тишины
WHISPER_HALLUCINATIONS = {
    "спасибо", "спасибо.", "спасибо за внимание", "продолжение следует",
    "минут", "вы", "я", "пожалуйста", "пожалуйста.", "просмотр", 
    "субтитры", "продолжение", "спасибо за просмотр"
}

class VoiceListener:
    def __init__(self):
        logger.info("Инициализация захвата звука (Уши)...")
        if not GROQ_API_KEY:
            logger.warning("Критическая ошибка: GROQ_API_KEY не обнаружен в конфигурации!")
            
        self.sample_rate = 16000
        self.block_size = 2048
        self.silence_duration = 1.2  # Время ожидания тишины перед отправкой
        self.energy_threshold = None  # Базовое значение порога
        logger.info("Система аудиозахвата готова. Инференс: Groq API (whisper-large-v3)")

    def _get_rms(self, data):
        return np.sqrt(np.mean(np.square(data.astype(np.float32) / 32768.0)))

    def listen(self, should_abort=None) -> str:
        with sd.InputStream(samplerate=self.sample_rate, channels=1, blocksize=self.block_size, dtype='int16') as stream:
            
            # ОТКАЗОУСТОЙЧИВАЯ ОДНОКРАТНАЯ КАЛИБРОВКА:
            if not hasattr(self, 'energy_threshold') or self.energy_threshold is None:
                print("\n[🎤] Калибровка фона (выполняется один раз при запуске)...")
                bg_rms_list = []
                for _ in range(int(self.sample_rate / self.block_size)):
                    data, overflow = stream.read(self.block_size)
                    bg_rms_list.append(self._get_rms(data))
                
                self.energy_threshold = np.mean(bg_rms_list) * 2.5
                if self.energy_threshold < 0.012:
                    self.energy_threshold = 0.012
                print(f"[🎤] Калибровка завершена. Базовый порог RMS VAD: {self.energy_threshold:.4f}")
            
            print(f"[🎤] Слушаю (порог RMS VAD: {self.energy_threshold:.4f})...")
            audio_buffer = []
            started_speaking = False
            max_silence_chunks = int((self.silence_duration * self.sample_rate) / self.block_size)
            silence_chunks = 0
            active_blocks_count = 0  
            
            while True:
                # МГНОВЕННЫЙ ВЫХОД: если хоткей перевел ассистента в сон, закрываем поток за 128мс
                if should_abort and should_abort():
                    logger.debug("[STT] Запись остановлена: ассистент переведен в режим сна.")
                    return ""
                
                data, overflow = stream.read(self.block_size)
                rms = self._get_rms(data)
                
                if rms > self.energy_threshold:
                    started_speaking = True
                    silence_chunks = 0
                    active_blocks_count += 1
                    audio_buffer.append(data)
                elif started_speaking:
                    silence_chunks += 1
                    audio_buffer.append(data)
                    if silence_chunks > max_silence_chunks:
                        break
                else:
                    audio_buffer.append(data)
                    if len(audio_buffer) > int((0.5 * self.sample_rate) / self.block_size):
                        audio_buffer.pop(0)

        # Дополнительная проверка на случай, если прерывание произошло на выходе из контекста
        if should_abort and should_abort():
            return ""

        # ЛОКАЛЬНАЯ ФИЛЬТРАЦИЯ ШУМОВЫХ ВСПЛЕСКОВ (<256 мс)
        if active_blocks_count < 2:
            logger.debug(f"[STT Skip] Отклонен короткий шум ({active_blocks_count} блоков VAD).")
            return ""

        temp_file = "data/temp_mic.wav"
        os.makedirs("data", exist_ok=True)
        final_audio = np.concatenate(audio_buffer)
        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(final_audio.tobytes())
            
        if not GROQ_API_KEY:
            return ""

        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            with open(temp_file, "rb") as f:
                files = {"file": ("temp_mic.wav", f, "audio/wav")}
                data = {
                    "model": "whisper-large-v3-turbo", 
                    "language": "ru",
                    "temperature": "0.0"
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=60.0)
            
            if response.status_code == 200:
                text = response.json().get("text", "").strip()
                if text:
                    clean_text = text.lower().strip().rstrip(".!?")
                    if clean_text in WHISPER_HALLUCINATIONS:
                        logger.debug(f"[STT] Отсечена галлюцинация Whisper: '{text}'")
                        return ""
                    
                    print(f"[Вы сказали]: {text}")
                    return text
            return ""
        except Exception as e:
            logger.error(f"Ошибка Groq API STT: {e}")
            return ""