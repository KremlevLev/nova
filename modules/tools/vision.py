# modules/tools/vision.py
from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Any

from modules.domain.results import ToolResult

logger = logging.getLogger("VisionTools")


class VisionToolkit:
    """
    Инструменты для работы с визуальными данными.
    
    - Screenshot capture - захват экрана
    - Vision reasoning - анализ изображений через LLM
    - OCR integration - распознавание текста на изображениях
    """

    @staticmethod
    def capture_screenshot(
        monitor: int = 0,
        region: tuple[int, int, int, int] | None = None,
    ) -> ToolResult:
        """
        Делает скриншот экрана или области.
        
        Args:
            monitor: Номер монитора (0 - основной)
            region: Область (x, y, width, height) или None для всего экрана
            
        Returns:
            ToolResult с путем к файлу скриншота
        """
        try:
            from PIL import ImageGrab
        except ImportError:
            return ToolResult.failure(
                "VISION_TOOL_NOT_AVAILABLE",
                "PIL/Pillow не установлен. Установите: pip install Pillow",
            )
        
        try:
            if region:
                x, y, width, height = region
                bbox = (x, y, x + width, y + height)
                image = ImageGrab.grab(bbox=bbox, all_screens=True)
            else:
                image = ImageGrab.grab(all_screens=True)
            
            # Сохраняем во временный файл
            temp_dir = Path(tempfile.gettempdir())
            screenshot_path = temp_dir / f"nova_screenshot_{id(image)}.png"
            image.save(screenshot_path, format="PNG")
            
            return ToolResult.ok(
                "Скриншот сохранен",
                data={
                    "path": str(screenshot_path),
                    "width": image.width,
                    "height": image.height,
                },
            )
            
        except Exception as e:
            logger.exception("Screenshot capture failed")
            return ToolResult.failure(
                "SCREENSHOT_FAILED",
                f"Не удалось сделать скриншот: {e}",
            )

    @staticmethod
    def image_to_base64(image_path: str | Path) -> ToolResult:
        """
        Конвертирует изображение в base64 для передачи модели.
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            ToolResult с base64 данными
        """
        try:
            image_path = Path(image_path)
            
            if not image_path.exists():
                return ToolResult.failure(
                    "FILE_NOT_FOUND",
                    f"Файл не найден: {image_path}",
                )
            
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            
            return ToolResult.ok(
                "Изображение конвертировано",
                data={
                    "base64": base64_data,
                    "format": image_path.suffix.lstrip(".").lower(),
                },
            )
            
        except Exception as e:
            logger.exception("Image to base64 conversion failed")
            return ToolResult.failure(
                "IMAGE_CONVERSION_FAILED",
                f"Не удалось конвертировать изображение: {e}",
            )

    @staticmethod
    def analyze_image(
        image_path: str | Path,
        prompt: str = "Опиши, что ты видишь на этом изображении.",
    ) -> ToolResult:
        """
        Анализирует изображение через vision-модель.
        
        Args:
            image_path: Путь к изображению
            prompt: Запрос для анализа
            
        Returns:
            ToolResult с описанием изображения
        """
        try:
            image_path = Path(image_path)
            
            if not image_path.exists():
                return ToolResult.failure(
                    "FILE_NOT_FOUND",
                    f"Файл не найден: {image_path}",
                )
            
            # Читаем изображение
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            
            # Формируем сообщение для vision модели
            vision_message = [
                {
                    "type": "text",
                    "text": prompt,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_data}",
                    },
                },
            ]
            
            return ToolResult.ok(
                "Изображение готово для анализа",
                data={
                    "message_content": vision_message,
                    "format": "gpt_vision",
                },
            )
            
        except Exception as e:
            logger.exception("Image analysis preparation failed")
            return ToolResult.failure(
                "IMAGE_ANALYSIS_FAILED",
                f"Не удалось подготовить изображение для анализа: {e}",
            )

    @staticmethod
    def ocr_image(
        image_path: str | Path,
    ) -> ToolResult:
        """
        Распознает текст на изображении через vision-модель.
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            ToolResult с распознанным текстом
        """
        try:
            image_path = Path(image_path)
            
            if not image_path.exists():
                return ToolResult.failure(
                    "FILE_NOT_FOUND",
                    f"Файл не найден: {image_path}",
                )
            
            # Читаем изображение
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            
            # Формируем сообщение для OCR через vision модель
            vision_message = [
                {
                    "type": "text",
                    "text": "Распознаи текст на этом изображении. Верни только распознанный текст без дополнительных пояснений.",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_data}",
                    },
                },
            ]
            
            return ToolResult.ok(
                "Изображение готово для OCR",
                data={
                    "message_content": vision_message,
                    "format": "ocr_vision",
                },
            )
            
        except Exception as e:
            logger.exception("OCR preparation failed")
            return ToolResult.failure(
                "OCR_FAILED",
                f"Не удалось подготовить изображение для OCR: {e}",
            )


def create_vision_tools() -> dict[str, Any]:
    """Создает словарь vision инструментов для регистрации."""
    return {
        "screenshot": VisionToolkit.capture_screenshot,
        "analyze_image": VisionToolkit.analyze_image,
        "image_to_base64": VisionToolkit.image_to_base64,
    }