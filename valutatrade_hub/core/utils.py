import json
import os
from typing import Any, Dict, List


def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Загрузка данных из JSON файла"""
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def save_json_file(file_path: str, data: List[Dict[str, Any]]):
    """Сохранение данных в JSON файл"""
    # Создаем папку если ее нет
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def format_currency_amount(amount: float, currency: str) -> str:
    """Форматирование денежной суммы"""
    if currency in ['BTC', 'ETH']:
        return f"{amount:.8f} {currency}"
    else:
        return f"{amount:.2f} {currency}"

