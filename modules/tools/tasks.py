# modules/tools/tasks.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional

class TaskScheduler:
    """
    Модульный планировщик задач.
    Сохраняет задачи в JSON-файл и позволяет ставить напоминания/будильники.
    """
    def __init__(self, storage_path: str = "data/tasks/tasks.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.tasks: List[Dict[str, Any]] = []
        self._load_tasks()

    def _load_tasks(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except Exception as e:
                print(f"[Scheduler Error]: Ошибка загрузки задач: {e}")

    def _save_tasks(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Scheduler Error]: Ошибка сохранения задач: {e}")

    def add_reminder(self, time_str: str, message: str) -> str:
        """
        Добавляет напоминание.
        time_str может быть в формате:
        - "HH:MM" (сегодня в указанное время)
        - Абсолютная дата и время "YYYY-MM-DD HH:MM:SS"
        - Относительное время в минутах (например, "+15" - через 15 минут)
        """
        now = datetime.datetime.now()
        target_time: datetime.datetime
        
        try:
            # Сценарий 1: Относительное время в минутах (+15)
            if time_str.startswith("+"):
                minutes = int(time_str[1:])
                target_time = now + datetime.timedelta(minutes=minutes)
            
            # Сценарий 2: Только время (HH:MM)
            elif len(time_str) == 5 and ":" in time_str:
                hour, minute = map(int, time_str.split(":"))
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # Если время уже прошло сегодня, переносим на завтра
                if target_time < now:
                    target_time += datetime.timedelta(days=1)
                    
            # Сценарий 3: Полная дата (YYYY-MM-DD HH:MM)
            else:
                target_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                
        except Exception as e:
            return f"Ошибка: Неверный формат времени '{time_str}'. Используйте '+минуты' (например, '+10') или 'ЧЧ:ММ' (например, '15:30')."

        task_id = f"task_{int(target_time.timestamp())}"
        
        new_task = {
            "id": task_id,
            "type": "reminder",
            "time": target_time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
            "completed": False
        }
        
        self.tasks.append(new_task)
        self._save_tasks()
        
        formatted_time = target_time.strftime("%H:%M (сегодня)" if target_time.date() == now.date() else "%d.%m в %H:%M")
        return f"Напоминание успешно установлено на {formatted_time}."

    def list_reminders(self) -> str:
        """Возвращает список активных напоминаний"""
        active_tasks = [t for t in self.tasks if not t.get("completed", False)]
        if not active_tasks:
            return "У вас нет активных напоминаний."
            
        result = "Ваши активные задачи:\n"
        for i, task in enumerate(active_tasks, 1):
            result += f"{i}. [{task['time']}] {task['message']} (ID: {task['id']})\n"
        return result

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает список задач, время выполнения которых наступило"""
        now = datetime.datetime.now()
        pending = []
        
        for task in self.tasks:
            if not task.get("completed", False):
                task_time = datetime.datetime.strptime(task["time"], "%Y-%m-%d %H:%M:%S")
                if now >= task_time:
                    pending.append(task)
                    
        return pending

    def mark_completed(self, task_id: str):
        """Помечает задачу как выполненную"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = True
                break
        self._save_tasks()