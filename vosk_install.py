# py -m vosk_install
import os
import urllib.request
import zipfile
import shutil

def progress_callback(block_num, block_size, total_size):
    """Отображает прогресс скачивания в консоли."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, downloaded * 100 / total_size)
        print(f"\rСкачивание: {percent:.1f}% ({downloaded / (1024*1024):.2f} MB из {total_size / (1024*1024):.2f} MB)", end="")
    else:
        print(f"\rСкачано: {downloaded / (1024*1024):.2f} MB", end="")

def download_and_setup_model():
    model_name = "vosk-model-small-ru-0.22"
    url = f"https://alphacephei.com/vosk/models/{model_name}.zip"
    
    # Пытаемся получить путь к папке со скриптом. 
    # Если запуск в Jupyter, используем текущую рабочую директорию.
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
        
    # Формируем целевой путь относительно папки со скриптом
    target_dir = os.path.join(base_dir, "data", "vosk")
    zip_path = os.path.join(target_dir, f"{model_name}.zip")
    
    # Показываем точный путь в консоли для проверки
    print(f"Целевая папка на компьютере:\n--> {os.path.abspath(target_dir)}\n")
    
    # Создаем структуру папок
    os.makedirs(target_dir, exist_ok=True)
    
    # 1. Скачивание архива
    print(f"Начало скачивания модели {model_name}...")
    try:
        urllib.request.urlretrieve(url, zip_path, reporthook=progress_callback)
        print("\nСкачивание завершено.")
    except Exception as e:
        print(f"\nНе удалось скачать модель. Ошибка: {e}")
        return

    # 2. Распаковка архива
    print("Распаковка архива...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        print("Архив успешно распакован.")
    except Exception as e:
        print(f"Не удалось распаковать архив. Ошибка: {e}")
        return
    finally:
        # Удаляем временный zip-файл
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print("Временный zip-файл удален.")

    # Если вы хотите, чтобы файлы модели (папки 'am', 'graph' и др.) лежали 
    # напрямую в 'nova/data/vosk/', а не в подпапке 'vosk-model-small-ru-0.22',
    # раскомментируйте блок ниже:
    
    # extracted_folder = os.path.join(target_dir, model_name)
    # if os.path.exists(extracted_folder):
    #     for file_name in os.listdir(extracted_folder):
    #         shutil.move(os.path.join(extracted_folder, file_name), target_dir)
    #     os.rmdir(extracted_folder)
    #     print(f"Файлы перемещены непосредственно в {target_dir}")

if __name__ == "__main__":
    download_and_setup_model()