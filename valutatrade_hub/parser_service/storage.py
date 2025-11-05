"""
Модуль для работы с хранилищем данных парсер-сервиса
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..logging_config import logger
from .config import config


class ParserStorage:
    """Класс для работы с хранилищем данных парсер-сервиса"""

    def __init__(self):
        self.history_file = config.HISTORY_FILE_PATH
        self.cache_file = config.RATES_FILE_PATH

    def _ensure_data_directory(self):
        """Создает директорию для данных если она не существует"""
        data_dir = os.path.dirname(self.history_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

    def _atomic_write(self, file_path: str, data: Any):
        """
        Атомарная запись в файл через временный файл

        Args:
            file_path: Путь к файлу
            data: Данные для записи
        """
        self._ensure_data_directory()

        # Создаем временный файл
        temp_fd, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(file_path),
            prefix=os.path.basename(file_path) + ".",
            suffix=".tmp"
        )

        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            # Атомарно заменяем старый файл новым
            os.replace(temp_path, file_path)

        except Exception as e:
            # Удаляем временный файл в случае ошибки
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise e

    def save_historical_record(self, record: Dict[str, Any]):
        """
        Сохраняет историческую запись курса

        Args:
            record: Запись курса для сохранения
        """
        try:
            # Загружаем существующие данные
            data = self.load_historical_data()

            # Добавляем новую запись
            record_id = record["id"]
            if "history" not in data:
                data["history"] = {}

            data["history"][record_id] = record

            # Обновляем метаданные
            data["metadata"] = {
                "last_update": datetime.now(timezone.utc).isoformat(),
                "total_records": len(data["history"]),
                "version": "1.0"
            }

            # Сохраняем атомарно
            self._atomic_write(self.history_file, data)
            logger.debug(f"Сохранена историческая запись: {record_id}")

        except Exception as e:
            logger.error(f"Ошибка сохранения исторической записи: {e}")
            raise

    def load_historical_data(self) -> Dict[str, Any]:
        """
        Загружает исторические данные курсов

        Returns:
            Словарь с историческими данными
        """
        if not os.path.exists(self.history_file):
            return {
                "history": {},
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "total_records": 0,
                    "version": "1.0"
                }
            }

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка загрузки исторических данных: {e}")
            return {
                "history": {},
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "total_records": 0,
                    "version": "1.0"
                }
            }

    def update_cache(self, rates: Dict[str, Dict[str, Any]]):
        """
        Обновляет кеш текущих курсов

        Args:
            rates: Словарь с текущими курсами
        """
        try:
            cache_data = {
                "pairs": rates,
                "last_refresh": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "total_pairs": len(rates),
                    "source": "ParserService"
                }
            }

            # Сохраняем атомарно
            self._atomic_write(self.cache_file, cache_data)
            logger.info(f"Обновлен кеш курсов: {len(rates)} пар")

        except Exception as e:
            logger.error(f"Ошибка обновления кеша: {e}")
            raise

    def load_cache(self) -> Dict[str, Any]:
        """
        Загружает данные из кеша

        Returns:
            Словарь с данными кеша
        """
        if not os.path.exists(self.cache_file):
            return {
                "pairs": {},
                "last_refresh": None,
                "metadata": {"total_pairs": 0}
            }

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка загрузки кеша: {e}")
            return {
                "pairs": {},
                "last_refresh": None,
                "metadata": {"total_pairs": 0}
            }

    def get_cache_rates(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает текущие курсы из кеша

        Returns:
            Словарь с текущими курсами
        """
        cache_data = self.load_cache()
        return cache_data.get("pairs", {})

    def is_cache_fresh(self, ttl_seconds: int = 300) -> bool:
        """
        Проверяет актуальность кеша

        Args:
            ttl_seconds: Время жизни кеша в секундах

        Returns:
            True если кеш актуален
        """
        cache_data = self.load_cache()
        last_refresh = cache_data.get("last_refresh")

        if not last_refresh:
            return False

        try:
            last_update = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return (now - last_update).total_seconds() < ttl_seconds
        except (ValueError, TypeError):
            return False

    def get_rate_history(self, pair: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Возвращает историю курса для указанной пары

        Args:
            pair: Валютная пара
            limit: Максимальное количество записей

        Returns:
            Список исторических записей
        """
        data = self.load_historical_data()
        history = []

        for _, record in data.get("history", {}).items():
            if (record.get("from_currency") == pair.split("_")[0] and
                record.get("to_currency") == pair.split("_")[1]):
                history.append(record)

    # Сортируем по времени (новые сначала)
        history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return history[:limit] if limit else history
