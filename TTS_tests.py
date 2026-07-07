import os
import sys
import json
import argparse
import numpy as np
import soundfile as sf
import onnxruntime as ort
from pathlib import Path
from tokenizers import Tokenizer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', type=str, required=True)
    parser.add_argument('--text', type=str, required=True)
    parser.add_argument('--instruct', type=str, default="")
    parser.add_argument('--language', type=str, default="Russian")
    parser.add_argument('--out', type=str, default="qwen3_perfect.wav")
    args = parser.parse_args()

    model_dir = Path(args.model_path)
    manifest_path = model_dir / "manifest.json"
    tokenizer_path = model_dir / "tokenizer.json"

    print("Читаем манифест и токенизатор...")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    tokenizer = Tokenizer.from_file(str(tokenizer_path))

    # Загружаем ONNX сессии на процессоре
    providers = ['CPUExecutionProvider']
    opts = ort.SessionOptions()
    sessions = {}

    print("Загружаем ONNX модели в память CPU...")
    for model_key, model_info in manifest["sub_models"].items():
        onnx_file = model_info["filename"]
        full_path = model_dir / onnx_file
        print(f" -> Загрузка {onnx_file}...")
        sessions[model_key] = ort.InferenceSession(str(full_path), sess_options=opts, providers=providers)

    print(f"Кодируем текст для языка: {args.language}...")
    # Кодируем текст в нампи-массивы с правильным именем входа text_ids
    input_ids = np.array([tokenizer.encode(args.text).ids], dtype=np.int64)
    
    # Готовим промпт для голоса
    prompt_text = args.instruct if args.instruct else "A pleasant, youthful Russian female voice."
    prompt_ids = np.array([tokenizer.encode(prompt_text).ids], dtype=np.int64)

    print("Генерация звука пошла (процессор считает цепочку)...")
    
    # Выполняем расчёт по цепочке моделей согласно архитектуре Qwen3
    text_emb = sessions["text_embed"].run(None, {"text_ids": input_ids})[0]
    voice_emb = sessions["text_embed"].run(None, {"text_ids": prompt_ids})[0]

    # Передаем эмбеддинги в предсказатель кодов
    predictor_outputs = sessions["code_predictor"].run(None, {
        "text_embeddings": text_emb,
        "voice_embeddings": voice_emb
    })[0]

    # Декодируем токены в финальный звук
    audio_features = sessions["tok_decoder"].run(None, {"input_features": predictor_outputs})[0]

    # Сохраняем результат (Qwen3 выдает поток 24кГц)
    audio_data = audio_features.flatten()
    sf.write(args.out, audio_data, 24000)
    print(f"Победа! Проверяй файл {args.out} в папке проекта!")

if __name__ == "__main__":
    main()
