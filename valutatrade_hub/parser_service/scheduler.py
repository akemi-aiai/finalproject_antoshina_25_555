"""
Планировщик для периодического обновления курсов
"""
import threading
from typing import Optional, Dict, Any

from ..logging_config import logger
from .config import ParserConfig
from .updater import RatesUpdater


class RatesScheduler:
    """Планировщик для автоматического обновления курсов"""

    def __init__(self):
        self.updater = RatesUpdater()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

    def start(self):
        """
        Запускает фоновое обновление курсов
        """
        if self._is_running:
            logger.warning("Планировщик уже запущен")
            return

        logger.info("Запуск планировщика обновления курсов")
        self._stop_event.clear()
        self._is_running = True

        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="RatesScheduler"
        )
        self._scheduler_thread.start()

    def stop(self):
        """
        Останавливает фоновое обновление курсов
        """
        if not self._is_running:
            return

        logger.info("Остановка планировщика обновления курсов")
        self._stop_event.set()
        self._is_running = False

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)

    def _scheduler_loop(self):
        """
        Основной цикл планировщика
        """
        logger.info(f"Планировщик запущен. Интервал: {ParserConfig.UPDATE_INTERVAL_MINUTES} мин")

        while not self._stop_event.is_set():
            try:
                # Выполняем обновление
                results = self.updater.update_all_rates()

                if results["success"]:
                    logger.debug(f"Фоновое обновление завершено. "
                                f"Обновлено пар: {results['updated_pairs']}")
                else:
                    logger.warning(f"Фоновое обновление завершено с ошибками: {results['errors']}")

            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")

            # Ждем указанный интервал или until stop
            self._stop_event.wait(ParserConfig.UPDATE_INTERVAL_MINUTES * 60)

        logger.info("Планировщик остановлен")

    def get_status(self) -> Dict[str, Any]:
        """
        Возвращает статус планировщика

        Returns:
            Словарь со статусом
        """
        return {
            "is_running": self._is_running,
            "update_interval_minutes": ParserConfig.UPDATE_INTERVAL_MINUTES,
            "thread_alive": self._scheduler_thread.is_alive() if self._scheduler_thread else False
        }


# Глобальный экземпляр планировщика
_scheduler_instance: Optional[RatesScheduler] = None


def get_scheduler() -> RatesScheduler:
    """
    Возвращает глобальный экземпляр планировщика (синглтон)

    Returns:
        Экземпляр RatesScheduler
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RatesScheduler()
    return _scheduler_instance
