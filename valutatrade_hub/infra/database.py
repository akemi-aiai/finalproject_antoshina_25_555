"""
Singleton для управления JSON-хранилищем данных
"""
import json
import os
from typing import Any, Dict, List, Optional

from .settings import settings


class DatabaseManager:
    """
    Singleton для абстракции над JSON-хранилищем

    Реализация через метакласс для демонстрации альтернативного подхода.
    Это более надежный способ для сложных синглтонов.
    """

    class _DatabaseMeta(type):
        """Метакласс для реализации синглтона"""

        _instances = {}

        def __call__(cls, *args, **kwargs):
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Защита от повторной инициализации
            self._data_cache: Dict[str, Any] = {}
            self._initialized = True

    def _get_file_path(self, entity: str) -> str:
        """Возвращает путь к файлу JSON для сущности"""
        filename = f"{entity}.json"
        return settings.get_data_path(filename)

    def _ensure_data_directory(self):
        """Создает директорию для данных если она не существует"""
        data_dir = settings.get("data_directory", "data")
        os.makedirs(data_dir, exist_ok=True)

    def load_data(self, entity: str) -> List[Dict[str, Any]]:
        """
        Загружает данные для сущности из JSON файла

        Args:
            entity: Имя сущности (users, portfolios, rates)

        Returns:
            Список словарей с данными
        """
        if entity in self._data_cache:
            return self._data_cache[entity]

        file_path = self._get_file_path(entity)

        if not os.path.exists(file_path):
            self._data_cache[entity] = []
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._data_cache[entity] = data
                return data
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading {entity}: {e}")
            return []

    def save_data(self, entity: str, data: List[Dict[str, Any]]):
        """
        Сохраняет данные для сущности в JSON файл

        Args:
            entity: Имя сущности
            data: Данные для сохранения
        """
        self._ensure_data_directory()
        file_path = self._get_file_path(entity)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            self._data_cache[entity] = data
        except Exception as e:
            print(f"Error saving {entity}: {e}")
            raise

    def clear_cache(self, entity: Optional[str] = None):
        """
        Очищает кеш данных

        Args:
            entity: Если указано, очищает только эту сущность, иначе все
        """
        if entity:
            self._data_cache.pop(entity, None)
        else:
            self._data_cache.clear()


# Глобальный экземпляр синглтона
db = DatabaseManager()
