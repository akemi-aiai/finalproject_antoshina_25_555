"""
Конфигурация для Parser Service
"""
import os
from typing import Dict, Tuple


class ParserConfig:
    """Конфигурация парсер-сервиса"""

    # API ключи (сначала из переменных окружения, если нет — из settings)
    try:
        from ..infra.settings import settings
        _settings = settings
    except ImportError:
        # Если settings недоступен, используем значения по умолчанию
        class DefaultSettings:
            exchangerate_api_key = "your_exchangerate_api_key_here"
            coingecko_api_key = ""
        _settings = DefaultSettings()

    EXCHANGERATE_API_KEY: str = os.getenv(
        "EXCHANGERATE_API_KEY",
        getattr(_settings, 'exchangerate_api_key', 'your_exchangerate_api_key_here')
    )
    COINGECKO_API_KEY: str = os.getenv(
        "COINGECKO_API_KEY",
        getattr(_settings, 'coingecko_api_key', '')
    )

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "RUB")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL", "ADA", "DOT", "DOGE", "LTC", "XRP", "BNB", "MATIC")

    # Словарь соответствий для CoinGecko
    CRYPTO_ID_MAP: Dict[str, str] = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "ADA": "cardano",
        "DOT": "polkadot",
        "DOGE": "dogecoin",
        "LTC": "litecoin",
        "XRP": "ripple",
        "BNB": "binancecoin",
        "MATIC": "matic-network"
    }

    # Пути к файлам
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
    MAX_RETRIES: int = 3
    UPDATE_INTERVAL_MINUTES: int = 5

    @classmethod
    def validate_config(cls) -> bool:
        """Проверяет корректность конфигурации"""
        issues = []

        if cls.EXCHANGERATE_API_KEY == 'your_exchangerate_api_key_here':
            issues.append("ExchangeRate-API ключ не настроен")

        if not cls.FIAT_CURRENCIES:
            issues.append("Нет поддерживаемых фиатных валют")

        if not cls.CRYPTO_CURRENCIES:
            issues.append("Нет поддерживаемых криптовалют")

        if issues:
            print(f"Проблемы конфигурации: {', '.join(issues)}")
            return False

        return True

    @classmethod
    def get_exchangerate_url(cls) -> str:
        """Возвращает полный URL для ExchangeRate-API"""
        return f"{cls.EXCHANGERATE_API_URL}/{cls.EXCHANGERATE_API_KEY}/latest/{cls.BASE_CURRENCY}"

    @classmethod
    def get_coingecko_params(cls) -> Dict[str, str]:
        """Возвращает параметры для CoinGecko API"""
        crypto_ids = ",".join(cls.CRYPTO_ID_MAP.values())
        return {
            'ids': crypto_ids,
            'vs_currencies': 'usd'
        }


# Глобальный экземпляр конфигурации
config = ParserConfig()
