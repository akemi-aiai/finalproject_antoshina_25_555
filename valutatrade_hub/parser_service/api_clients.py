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
        """
        Получает курсы валют от API

        Returns:
            Словарь с курсами в формате {валютная_пара: курс}

        Raises:
            ApiRequestError: Если запрос не удался
        """
        pass

    def _make_request(self, url: str, params: Dict = None) -> Dict[str, Any]:
        start_time = time.time()

        for attempt in range(config.MAX_RETRIES):
            try:
                logger.debug(f"API запрос: {url} (попытка {attempt + 1})")

                response = self.session.get(
                    url,
                    params=params,
                    timeout=config.REQUEST_TIMEOUT
                )

                request_time = int((time.time() - start_time) * 1000)

                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 5
                    logger.warning(f"Превышен лимит запросов. Ожидание {wait_time} сек...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                return {
                    "data": response.json(),
                    "meta": {
                        "request_ms": request_time,
                        "status_code": response.status_code,
                        "etag": response.headers.get('ETag', ''),
                        "url": url
                    }
                }

            except requests.exceptions.Timeout as e:
                logger.warning(f"Таймаут запроса (попытка {attempt + 1})")
                if attempt == config.MAX_RETRIES - 1:
                    raise ApiRequestError("Таймаут при обращении к API") from e

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Ошибка соединения (попытка {attempt + 1})")
                if attempt == config.MAX_RETRIES - 1:
                    raise ApiRequestError("Ошибка соединения с API") from e

            except requests.exceptions.HTTPError as e:
                if response.status_code == 401:
                    raise ApiRequestError("Неверный API ключ") from e
                elif response.status_code == 403:
                    raise ApiRequestError("Доступ к API запрещен") from e
                else:
                    raise ApiRequestError(f"HTTP ошибка {response.status_code}: {e}") from e

            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса: {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise ApiRequestError(f"Ошибка при обращении к API: {e}") from e

        # Ждем перед следующей попыткой
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

        raise ApiRequestError("Не удалось выполнить запрос после всех попыток")




class CoinGeckoClient(BaseApiClient):
    """Клиент для CoinGecko API (криптовалюты)"""

    def fetch_rates(self) -> Dict[str, float]:
        """
        Получает курсы криптовалют от CoinGecko

        Returns:
            Словарь с курсами в формате {валютная_пара: курс}
        """
        logger.info("Получение курсов криптовалют от CoinGecko...")

        url = config.COINGECKO_URL
        params = config.get_coingecko_params()

        try:
            result = self._make_request(url, params)
            api_data = result["data"]

            if not api_data:
                raise ApiRequestError("Пустой ответ от CoinGecko API")

            # Парсим ответ в стандартизированный формат
            rates = {}
            for crypto_id, coin_data in api_data.items():
                # Находим тикер по ID
                ticker = None
                for ticker_code, coin_id in config.CRYPTO_ID_MAP.items():
                    if coin_id == crypto_id:
                        ticker = ticker_code
                        break

                if ticker and 'usd' in coin_data:
                    pair = f"{ticker}_{config.BASE_CURRENCY}"
                    rates[pair] = coin_data['usd']

            logger.info(f"Успешно получено {len(rates)} крипто курсов от CoinGecko")
            return rates

        except ApiRequestError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении курсов от CoinGecko: {e}")
            raise ApiRequestError(f"Ошибка парсинга данных CoinGecko: {e}") from e



class ExchangeRateApiClient(BaseApiClient):
    """Клиент для ExchangeRate-API (фиатные валюты)"""

    def fetch_rates(self) -> Dict[str, float]:
        """
        Получает курсы фиатных валют от ExchangeRate-API

        Returns:
            Словарь с курсами в формате {валютная_пара: курс}
        """
        logger.info("Получение курсов фиатных валют от ExchangeRate-API...")

        url = config.get_exchangerate_url()

        try:
            result = self._make_request(url)
            api_data = result["data"]

            # Проверяем успешность ответа
            if api_data.get('result') != 'success':
                error_type = api_data.get('error-type', 'unknown')
                raise ApiRequestError(f"API вернуло ошибку: {error_type}")

            # Парсим ответ в стандартизированный формат
            rates = {}
            base_currency = api_data.get('base_code', config.BASE_CURRENCY)

            for currency, rate in api_data.get('rates', {}).items():
                if currency in config.FIAT_CURRENCIES and currency != base_currency:
                    pair = f"{currency}_{base_currency}"
                    rates[pair] = 1 / rate  # Конвертируем в USD->валюта

            logger.info(f"Успешно получено {len(rates)} фиатных курсов от ExchangeRate-API")
            return rates

        except ApiRequestError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении курсов от ExchangeRate-API: {e}")
            raise ApiRequestError(f"Ошибка парсинга данных ExchangeRate-API: {e}") from e


class APIFactory:
    """Фабрика для создания API клиентов"""

    @staticmethod
    def create_client(api_type: str) -> BaseApiClient:
        """
        Создает API клиент по типу

        Args:
            api_type: Тип API ('coingecko' или 'exchangerate')

        Returns:
            API клиент

        Raises:
            ValueError: Если тип API неизвестен
        """
        if api_type == 'coingecko':
            return CoinGeckoClient()
        elif api_type == 'exchangerate':
            return ExchangeRateApiClient()
        else:
            raise ValueError(f"Неизвестный тип API: {api_type}")
