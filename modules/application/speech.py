# modules/application/speech.py
from __future__ import annotations

import asyncio
import itertools
import logging
import re

from modules.audio.tts import (
    reset_interrupt_flag,
    speak,
    stop_speaking,
)
from modules.domain.state import AssistantState, RuntimeState


logger = logging.getLogger("SpeechService")


def prepare_text_for_speech(
    text: str,
    *,
    max_total_characters: int = 700,
) -> str:
    """
    Убирает из экранного ответа элементы, которые не следует озвучивать:
    Markdown-таблицы, код, URL и лишнюю разметку.
    """
    if not text:
        return ""

    clean = text.strip()

    # Удаляем многострочные блоки кода.
    clean = re.sub(
        r"```.*?```",
        " Код показан на экране. ",
        clean,
        flags=re.DOTALL,
    )

    prepared_lines: list[str] = []

    for raw_line in clean.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        # Markdown-таблицы не озвучиваем.
        if line.startswith("|") and line.endswith("|"):
            continue

        # Разделители Markdown-таблиц.
        if re.fullmatch(r"[\s|:\-]+", line):
            continue

        # Заголовки превращаем в обычный текст.
        line = re.sub(r"^#{1,6}\s*", "", line)

        # Убираем маркировку списка.
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)

        # Убираем Markdown emphasis.
        line = line.replace("**", "")
        line = line.replace("__", "")
        line = line.replace("`", "")

        # URL не стоит произносить целиком.
        line = re.sub(
            r"https?://\S+",
            "ссылка показана на экране",
            line,
            flags=re.IGNORECASE,
        )

        prepared_lines.append(line)

    clean = " ".join(prepared_lines)
    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) <= max_total_characters:
        return clean

    shortened = clean[:max_total_characters]

    # Обрезаем на последнем завершении предложения.
    sentence_end = max(
        shortened.rfind("."),
        shortened.rfind("!"),
        shortened.rfind("?"),
    )

    if sentence_end >= 120:
        shortened = shortened[:sentence_end + 1]
    else:
        last_space = shortened.rfind(" ")
        if last_space > 0:
            shortened = shortened[:last_space]

        shortened = shortened.rstrip(" ,;:-") + "."

    return (
        shortened
        + " Подробности показаны на экране."
    )


def split_speech_chunks(
    text: str,
    *,
    max_chunk_characters: int = 450,
) -> list[str]:
    """
    Делит речь на безопасные фрагменты для Silero.
    """
    clean = re.sub(r"\s+", " ", text).strip()

    if not clean:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        clean,
    )

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(sentence) > max_chunk_characters:
            words = sentence.split()
            temporary = ""

            for word in words:
                candidate = (
                    f"{temporary} {word}".strip()
                )

                if (
                    temporary
                    and len(candidate) > max_chunk_characters
                ):
                    chunks.append(temporary)
                    temporary = word
                else:
                    temporary = candidate

            if temporary:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(temporary)

            continue

        candidate = f"{current} {sentence}".strip()

        if (
            current
            and len(candidate) > max_chunk_characters
        ):
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


class SpeechService:
    def __init__(self, runtime: RuntimeState) -> None:
        self.runtime = runtime
        self._queue: asyncio.PriorityQueue = (
            asyncio.PriorityQueue()
        )
        self._counter = itertools.count()
        self._worker: asyncio.Task | None = None
        self._closed = False
        self._generation = 0

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(
                self._run(),
                name="nova-speech-worker",
            )

    async def say(
        self,
        text: str,
        *,
        priority: int = 10,
        wait: bool = True,
    ) -> None:
        if self._closed:
            return

        speech_text = prepare_text_for_speech(text)

        if not speech_text:
            return

        loop = asyncio.get_running_loop()
        completed = loop.create_future()
        generation = self._generation

        await self._queue.put(
            (
                priority,
                next(self._counter),
                generation,
                speech_text,
                completed,
            )
        )

        if wait:
            try:
                await completed
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Не удалось озвучить сообщение."
                )

    async def interrupt(self) -> None:
        self._generation += 1

        await asyncio.to_thread(stop_speaking)

        while not self._queue.empty():
            try:
                (
                    _priority,
                    _counter,
                    _generation,
                    _text,
                    future,
                ) = self._queue.get_nowait()

                if future and not future.done():
                    future.cancel()

                self._queue.task_done()

            except asyncio.QueueEmpty:
                break

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        await self.interrupt()

        if self._worker is not None:
            await self._queue.put(
                (
                    -100,
                    next(self._counter),
                    self._generation,
                    None,
                    None,
                )
            )

            await asyncio.gather(
                self._worker,
                return_exceptions=True,
            )

            self._worker = None

    async def _run(self) -> None:
        while True:
            (
                _priority,
                _counter,
                generation,
                text,
                completed,
            ) = await self._queue.get()

            try:
                if text is None:
                    return

                if generation != self._generation:
                    if completed and not completed.done():
                        completed.cancel()
                    continue

                reset_interrupt_flag()

                await self.runtime.set_state(
                    AssistantState.SPEAKING
                )

                chunks = split_speech_chunks(text)

                for chunk in chunks:
                    if generation != self._generation:
                        break

                    await asyncio.to_thread(
                        speak,
                        chunk,
                    )

                if completed and not completed.done():
                    if generation == self._generation:
                        completed.set_result(None)
                    else:
                        completed.cancel()

            except Exception as exc:
                logger.exception(
                    "Ошибка синтеза речи."
                )

                if completed and not completed.done():
                    completed.set_exception(exc)

            finally:
                self._queue.task_done()

                if not self.runtime.is_shutting_down:
                    next_state = (
                        AssistantState.LISTENING
                        if self.runtime.is_active
                        else AssistantState.SLEEPING
                    )

                    await self.runtime.set_state(
                        next_state
                    )
