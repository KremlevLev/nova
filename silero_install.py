# silero_install.py
import os
import sys

# Проверка наличия PyTorch перед запуском
try:
    import torch
except ImportError:
    print("Ошибка: Библиотека 'torch' не найдена. Сначала выполните: pip install -r requirements.txt")
    sys.exit(1)

MODEL_PATH = "data/v5_ru.pt"

def install_voice_model():
    print("=== Установка голосового движка Silero TTS ===")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    if not os.path.exists(MODEL_PATH):
        print(f"Файл {MODEL_PATH} не найден. Начинаю скачивание модели Silero v5_ru...")
        try:
            # Используем встроенный в torch загрузчик
            torch.hub.download_url_to_file('https://models.silero.ai/models/tts/ru/v5_ru.pt', MODEL_PATH)
            print("Загрузка успешно завершена.")
        except Exception as e:
            print(f"Критическая ошибка при скачивании модели: {e}")
            sys.exit(1)
    else:
        print("Модель Silero v5 уже присутствует в локальной папке.")

    print("\nВыполняю первый тестовый прогрев модели...")
    try:
        # Установка оптимальных потоков
        torch.set_num_threads(4)
        model = torch.package.PackageImporter(MODEL_PATH).load_pickle("tts_models", "model")
        model.to(torch.device('cpu'))
        print("Проверка инициализации пройдена! Голосовой движок готов к работе.")
    except Exception as e:
        print(f"Ошибка при инициализации модели: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_voice_model()