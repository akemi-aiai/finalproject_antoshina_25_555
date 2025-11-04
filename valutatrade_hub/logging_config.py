"""
Конфигурация логирования для приложения
"""
import json
import logging
import os
from logging.handlers import RotatingFileHandler

from infra.settings import settings


class JSONFormatter(logging.Formatter):
    """Форматтер для JSON логов"""

    def format(self, record):
        # Базовые поля для всех логов
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Добавляем дополнительные поля из extra
        if hasattr(record, 'action'):
            log_data["action"] = record.action
        if hasattr(record, 'user'):
            log_data["user"] = record.user
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'currency'):
            log_data["currency"] = record.currency
        if hasattr(record, 'amount'):
            log_data["amount"] = record.amount
        if hasattr(record, 'rate'):
            log_data["rate"] = record.rate
        if hasattr(record, 'base'):
            log_data["base"] = record.base
        if hasattr(record, 'result'):
            log_data["result"] = record.result
        if hasattr(record, 'error_type'):
            log_data["error_type"] = record.error_type
        if hasattr(record, 'error_message'):
            log_data["error_message"] = record.error_message
        if hasattr(record, 'execution_time_sec'):
            log_data["execution_time_sec"] = record.execution_time_sec

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """Настройка системы логирования"""
    # Создаем логгер
    logger = logging.getLogger('valutatrade')

    # Устанавливаем уровень логирования
    log_level = getattr(logging, settings.get('log_level', 'INFO'))
    logger.setLevel(log_level)

    # Очищаем существующие handlers (на случай перезагрузки)
    logger.handlers.clear()

    # Форматтер для человекочитаемых логов
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # JSON форматтер для структурированных логов
    json_formatter = JSONFormatter()

    # Консольный handler (человекочитаемый)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Файловый handler для действий (JSON формат)
    actions_log_file = settings.get('log_file', 'logs/actions.log')
    os.makedirs(os.path.dirname(actions_log_file), exist_ok=True)

    actions_handler = RotatingFileHandler(
        actions_log_file,
        maxBytes=settings.get('max_log_size_mb', 10) * 1024 * 1024,  # 10 MB
        backupCount=settings.get('backup_count', 5)
    )
    actions_handler.setLevel(logging.INFO)
    actions_handler.setFormatter(json_formatter)
    actions_handler.addFilter(lambda record: hasattr(record, 'action'))  # Только логи с действиями

    # Файловый handler для всех логов (человекочитаемый)
    general_log_file = 'logs/valutatrade.log'
    os.makedirs(os.path.dirname(general_log_file), exist_ok=True)

    general_handler = RotatingFileHandler(
        general_log_file,
        maxBytes=settings.get('max_log_size_mb', 10) * 1024 * 1024,
        backupCount=settings.get('backup_count', 5)
    )
    general_handler.setLevel(logging.DEBUG)
    general_handler.setFormatter(simple_formatter)

    # Добавляем handlers
    logger.addHandler(console_handler)
    logger.addHandler(actions_handler)
    logger.addHandler(general_handler)

    # Предотвращаем передачу логов корневому логгеру
    logger.propagate = False

    return logger


# Глобальный логгер
logger = setup_logging()
