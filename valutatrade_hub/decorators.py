"""
Декораторы для логирования операций
"""
import functools
import time
from typing import Any, Callable

from .infra.settings import settings
from .logging_config import logger


def log_action(action_name: str = None, verbose: bool = False):
    """
    Декоратор для логирования действий пользователя

    Args:
        action_name: Название действия для лога
        verbose: Подробное логирование с дополнительным контекстом
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Определяем имя действия
            actual_action_name = action_name or func.__name__.upper()

            # Собираем базовую информацию для лога
            log_data = {
                "action": actual_action_name,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            }

            # Пытаемся извлечь информацию о пользователе и параметрах из аргументов
            try:
                # Для методов классов, где первый аргумент - self
                if args and hasattr(args[0], 'current_user') and args[0].current_user:
                    log_data["user"] = args[0].current_user.username
                    log_data["user_id"] = args[0].current_user.user_id

                # Извлекаем параметры из аргументов функции
                if actual_action_name in ['BUY', 'SELL'] and len(args) >= 3:
                    log_data["currency"] = str(args[2]).upper()  # currency_code
                    log_data["amount"] = float(args[3]) if len(args) > 3 else 0.0

                if actual_action_name == 'GET_RATE' and len(args) >= 3:
                    log_data["from_currency"] = str(args[2]).upper()
                    log_data["to_currency"] = str(args[3]).upper()

            except (IndexError, AttributeError, ValueError):
                pass  # Если не удалось извлечь - продолжаем без этой информации

            # Добавляем параметры из kwargs
            for key in ['currency', 'amount', 'from_currency', 'to_currency', 'rate', 'base']:
                if key in kwargs and kwargs[key] is not None:
                    log_data[key] = kwargs[key]

            # Логируем начало действия
            logger.info(f"Начало действия: {actual_action_name}", extra=log_data)

            try:
                # Выполняем функцию
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Добавляем информацию о результате
                log_data.update({
                    "result": "OK",
                    "execution_time_sec": round(execution_time, 3)
                })

                # Добавляем дополнительный контекст для verbose режима
                if verbose and result and isinstance(result, tuple):
                    if actual_action_name in ['BUY', 'SELL'] and len(result) >= 2:
                        log_data["cost_usd"] = result[1]  # cost_usd или revenue_usd
                        if len(result) > 2:
                            log_data["rate"] = result[2]  # rate

                # Логируем успешное завершение
                logger.info(f"Действие завершено: {actual_action_name}", extra=log_data)

                return result

            except Exception as e:
                # Логируем ошибку
                log_data.update({
                    "result": "ERROR",
                    "error_type": e.__class__.__name__,
                    "error_message": str(e)
                })

                logger.error(
                    f"Ошибка в действии {actual_action_name}: {str(e)}",
                    extra=log_data,
                    exc_info=settings.get('log_level') == 'DEBUG'  # Подробный traceback только в DEBUG
                )
                raise

        return wrapper
    return decorator


def log_transaction(currency: str = None, amount: float = None):
    """
    Декоратор для логирования финансовых транзакций

    Args:
        currency: Валюта транзакции
        amount: Сумма транзакции
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Извлекаем информацию о транзакции из аргументов
            actual_currency = currency
            actual_amount = amount

            # Если не указаны явно, пытаемся извлечь из аргументов
            if not actual_currency and len(args) > 1:
                actual_currency = args[1]  # Предполагаем, что currency - второй аргумент
            if not actual_amount and len(args) > 2:
                actual_amount = args[2]   # Предполагаем, что amount - третий аргумент

            transaction_info = ""
            if actual_currency and actual_amount:
                transaction_info = f" [{actual_currency} {actual_amount}]"

            # Логируем начало транзакции
            logger.info(f"Начало транзакции: {func.__name__}{transaction_info}")

            try:
                result = func(*args, **kwargs)
                logger.info(f"Транзакция успешна: {func.__name__}{transaction_info}")
                return result

            except Exception as e:
                logger.error(f"Транзакция: {func.__name__}{transaction_info} - {str(e)}")
                raise

        return wrapper
    return decorator
