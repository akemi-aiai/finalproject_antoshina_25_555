import json
import os
import re
from typing import Any, Dict, List

from .currencies import is_currency_supported
from .exceptions import ValidationError


def validate_currency_code(code: str) -> bool:
    """
    Валидация кода валюты

    Args:
        code: Код валюты для проверки

    Returns:
        True если код валиден
    """
    if not code or not isinstance(code, str):
        return False

    code_upper = code.upper()

    # Проверка формата
    if not re.match(r'^[A-Z0-9]{2,5}$', code_upper):
        return False

    # Проверка поддержки валюты
    return is_currency_supported(code_upper)


def validate_amount(amount: Any) -> float:
    """
    Валидация денежной суммы

    Args:
        amount: Сумма для проверки

    Returns:
        Валидная сумма как float

    Raises:
        ValidationError: Если сумма невалидна
    """
    if not isinstance(amount, (int, float, str)):
        raise ValidationError("Сумма должна быть числом")

    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        raise ValidationError("Сумма должна быть числом")

    if amount_float <= 0:
        raise ValidationError("Сумма должна быть положительной")

    return amount_float


def format_currency_amount(amount: float, currency: str) -> str:
    """Форматирование денежной суммы"""
    from .currencies import get_currency

    try:
        currency_obj = get_currency(currency)

        if hasattr(currency_obj, 'algorithm'):  # Криптовалюта
            return f"{amount:.8f} {currency}"
        else:  # Фиатная валюта
            return f"{amount:.2f} {currency}"

    except Exception:
        # Fallback форматирование
        if currency in ['BTC', 'ETH', 'LTC']:
            return f"{amount:.8f} {currency}"
        else:
            return f"{amount:.2f} {currency}"


def get_supported_currencies_list() -> List[str]:
    """Возвращает список поддерживаемых валют"""
    from .currencies import get_supported_currencies
    currencies = get_supported_currencies()
    return list(currencies.keys())


def format_currency_display(currency_code: str) -> str:
    """Форматирует отображение информации о валюте"""
    from .currencies import get_currency

    try:
        currency = get_currency(currency_code)
        return currency.get_display_info()
    except Exception:
        return f"[UNKNOWN] {currency_code}"


# Сохраняем старые функции для обратной совместимости
def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Загрузка данных из JSON файла (устаревшая функция)"""
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def save_json_file(file_path: str, data: List[Dict[str, Any]]):
    """Сохранение данных в JSON файл (устаревшая функция)"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
