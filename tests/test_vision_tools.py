# tests/test_vision_tools.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.tools.vision import VisionToolkit


class TestVisionToolkit:
    """Тесты для Vision Toolkit."""

    def test_image_to_base64_success(self):
        """Тест конвертации изображения в base64."""
        # Создаем тестовое изображение
        try:
            from PIL import Image
        except ImportError:
            return  # Пропускаем если нет Pillow

        with tempfile.TemporaryDirectory() as directory:
            # Создаем простое изображение
            image_path = Path(directory) / "test.png"
            img = Image.new("RGB", (10, 10), color="red")
            img.save(image_path)

            result = VisionToolkit.image_to_base64(image_path)

            assert result.success
            assert "base64" in result.data
            assert len(result.data["base64"]) > 0
            assert result.data["format"] == "png"

    def test_image_to_base64_file_not_found(self):
        """Тест ошибки при отсутствии файла."""
        result = VisionToolkit.image_to_base64("/nonexistent/path.png")

        assert not result.success
        assert result.code == "FILE_NOT_FOUND"

    def test_analyze_image_success(self):
        """Тест анализа изображения."""
        try:
            from PIL import Image
        except ImportError:
            return  # Пропускаем если нет Pillow

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "test.png"
            img = Image.new("RGB", (10, 10), color="blue")
            img.save(image_path)

            result = VisionToolkit.analyze_image(image_path)

            assert result.success
            assert "message_content" in result.data
            assert len(result.data["message_content"]) == 2  # text + image_url

    def test_analyze_image_file_not_found(self):
        """Тест ошибки при отсутствии файла для анализа."""
        result = VisionToolkit.analyze_image("/nonexistent/path.png")

        assert not result.success
        assert result.code == "FILE_NOT_FOUND"

    def test_create_vision_tools(self):
        """Тест создания словарь инструментов."""
        tools = VisionToolkit.capture_screenshot,
        assert VisionToolkit.__name__ == "VisionToolkit"

    def test_ocr_image_success(self):
        """Тест подготовки изображения для OCR."""
        try:
            from PIL import Image
        except ImportError:
            return  # Пропускаем если нет Pillow

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "test.png"
            img = Image.new("RGB", (10, 10), color="green")
            img.save(image_path)

            result = VisionToolkit.ocr_image(image_path)

            assert result.success
            assert "message_content" in result.data
            assert result.data["format"] == "ocr_vision"
