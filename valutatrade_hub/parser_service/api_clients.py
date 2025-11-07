"""
API клиенты для работы с внешними сервисами курсов валют
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict

import requests

from ..core.exceptions import ApiRequestError
from ..logging_config import logger
from .config import config


class BaseApiClient(ABC):
    """Абстрактный базовый класс для API клиентов"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ValutatradeHub/1.0',
            'Accept': 'application/json'
        })

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """Получает курсы фиатных валют от ExchangeRate-API"""
        logger.info("Получение курсов фиатных валют от ExchangeRate-API...")

        try:
            url = config.get_exchangerate_url()
            result = self._make_request(url)
            api_data = result["data"]

            # Проверяем успешность ответа
            if api_data.get('result') != 'success':
                error_msg = api_data.get('error-type', 'unknown error')
                raise ApiRequestError(f"ExchangeRate-API error: {error_msg}")

            rates = {}
            base_currency = api_data.get('base_code', config.BASE_CURRENCY)

            for currency, rate in api_data.get('rates', {}).items():
                if currency in config.FIAT_CURRENCIES and currency != base_currency:

                    if base_currency == "USD":
                        # Если база USD, то курс уже в правильном формате: USD->валюта
                        pair = f"{currency}_{base_currency}"
                        rates[pair] = rate
                    else:
                        # Если нужна конвертация
                        pair = f"{currency}_{config.BASE_CURRENCY}"
                        # Логика конвертации зависит от API ответа

            logger.info(f"Получено {len(rates)} фиатных курсов от ExchangeRate-API")
            return rates

        except Exception as e:
            logger.error(f"Ошибка получения фиатных курсов: {e}")
            return {}


    def _make_request(self, url: str, params: Dict = None) -> Dict[str, Any]:
        """Выполняет HTTP запрос с повторными попытками"""
        for attempt in range(config.MAX_RETRIES):
            try:
                logger.debug(f"API запрос: {url} (попытка {attempt + 1})")
                response = self.session.get(
                    url,
                    params=params,
                    timeout=config.REQUEST_TIMEOUT
                )
                response.raise_for_status()

                return {
                    "data": response.json(),
                    "meta": {
                        "status_code": response.status_code,
                        "url": url
                    }
                }

            except requests.exceptions.RequestException as e:
                logger.warning(f"Ошибка запроса (попытка {attempt + 1}): {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise ApiRequestError(f"Ошибка API: {e}") from e
                time.sleep(2 ** attempt)

        raise ApiRequestError("Не удалось выполнить запрос")


class CoinGeckoClient(BaseApiClient):
    """Клиент для CoinGecko API (криптовалюты)"""

    def fetch_rates(self) -> Dict[str, float]:
        """Получает курсы криптовалют от CoinGecko"""
        logger.info("Получение курсов криптовалют от CoinGecko...")

        try:
            url = config.COINGECKO_URL
            params = config.get_coingecko_params()

            result = self._make_request(url, params)
            api_data = result["data"]

            if not api_data:
                logger.warning("Пустой ответ от CoinGecko")
                return {}

            # ИСПРАВЛЕНО: используем config.CRYPTO_ID_MAP (экземпляр)
            rates = {}
            for crypto_id, coin_data in api_data.items():
                # Находим тикер по ID через config.CRYPTO_ID_MAP
                for ticker_code, coin_id in config.CRYPTO_ID_MAP.items():
                    if coin_id == crypto_id and 'usd' in coin_data:
                        pair = f"{ticker_code}_{config.BASE_CURRENCY}"
                        rates[pair] = coin_data['usd']
                        break

            logger.info(f"Получено {len(rates)} крипто курсов от CoinGecko")
            return rates

        except Exception as e:
            logger.error(f"Ошибка получения крипто курсов: {e}")
            return {}


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для ExchangeRate-API (фиатные валюты)"""

    def fetch_rates(self) -> Dict[str, float]:
        """Получает курсы фиатных валют от ExchangeRate-API"""
        logger.info("Получение курсов фиатных валют от ExchangeRate-API...")

        try:
            url = config.get_exchangerate_url()
            result = self._make_request(url)
            api_data = result["data"]

            # Проверяем успешность ответа
            if api_data.get('result') != 'success':
                error_msg = api_data.get('error-type', 'unknown error')
                raise ApiRequestError(f"ExchangeRate-API error: {error_msg}")

            # ИСПРАВЛЕНО: используем config.FIAT_CURRENCIES (экземпляр)
            rates = {}
            base_currency = api_data.get('base_code', config.BASE_CURRENCY)

            for currency, rate in api_data.get('rates', {}).items():
                if currency in config.FIAT_CURRENCIES and currency != base_currency:
                    pair = f"{currency}_{base_currency}"
                    rates[pair] = 1 / rate  # Конвертируем в USD->валюта

            logger.info(f"Получено {len(rates)} фиатных курсов от ExchangeRate-API")
            return rates

        except Exception as e:
            logger.error(f"Ошибка получения фиатных курсов: {e}")
            return {}


class APIFactory:
    """Фабрика для создания API клиентов"""

    @staticmethod
    def create_client(api_type: str) -> BaseApiClient:
        """Создает API клиент по типу"""
        if api_type == 'coingecko':
            return CoinGeckoClient()
        elif api_type == 'exchangerate':
            return ExchangeRateApiClient()
        else:
            raise ValueError(f"Неизвестный тип API: {api_type}")
