# modules/ui/overlay.py
import tkinter as tk
import threading
import queue
import logging

logger = logging.getLogger("Overlay")

# Потокобезопасная очередь для передачи состояний из основного цикла в GUI
_gui_queue = queue.Queue()
_overlay_thread = None

class NovaOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Overlay")
        
        # Убираем рамки Windows (делаем окно borderless)
        self.root.overrideredirect(True)
        # Окно всегда поверх всех остальных окон
        self.root.attributes("-topmost", True)
        # Полупрозрачность окна
        self.root.attributes("-alpha", 0.9)
        
        # Позиционируем виджет в правый нижний угол экрана
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width, height = 200, 48
        
        # Отступ 20px справа и 60px снизу (над панелью задач)
        x = screen_width - width - 20
        y = screen_height - height - 60
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Дизайн в темных тонах
        self.root.configure(bg="#121214")
        
        # Рисуем светодиод-индикатор статуса
        self.canvas = tk.Canvas(self.root, width=16, height=16, bg="#121214", highlightthickness=0)
        self.canvas.pack(side="left", padx=(15, 10))
        self.led = self.canvas.create_oval(2, 2, 14, 14, fill="#555555")  # Серый по умолчанию (Спит)
        
        # Текстовая метка состояния
        self.label = tk.Label(
            self.root, 
            text="СПИТ", 
            fg="#88888F", 
            bg="#121214", 
            font=("Segoe UI", 10, "bold")
        )
        self.label.pack(side="left")
        
        # Запускаем фоновый опрос очереди событий раз в 100 мс
        self.root.after(100, self.process_queue)

    def process_queue(self):
        try:
            while True:
                status = _gui_queue.get_nowait()
                self.update_ui(status)
                _gui_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def update_ui(self, status: str):
        # Соответствие цветов и текста состояниям
        states = {
            "СПИТ": ("#555555", "#88888F"),        # Серый индикатор, серый текст
            "СЛУШАЕТ": ("#00FF66", "#00FF66"),     # Ярко-зеленый (активный слух)
            "ДУМАЕТ": ("#FFCC00", "#FFCC00"),      # Желтый (обработка LLM)
            "ГОВОРИТ": ("#0099FF", "#0099FF")      # Синий (синтез TTS)
        }
        color, text_color = states.get(status, ("#555555", "#88888F"))
        
        self.canvas.itemconfig(self.led, fill=color)
        self.label.config(text=status, fg=text_color)

def _run_gui():
    try:
        root = tk.Tk()
        app = NovaOverlay(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Ошибка в цикле GUI: {e}")

def start_overlay():
    """Запускает окно оверлея в отдельном потоке"""
    global _overlay_thread
    if _overlay_thread is None:
        _overlay_thread = threading.Thread(target=_run_gui, daemon=True)
        _overlay_thread.start()
        logger.info("Визуальный оверлей успешно запущен.")

def update_status(status: str):
    """Отправляет новое состояние ассистента в GUI ('СПИТ', 'СЛУШАЕТ', 'ДУМАЕТ', 'ГОВОРИТ')"""
    _gui_queue.put(status)