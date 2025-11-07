from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..decorators import log_action
from ..infra.database import db
from ..infra.settings import settings
from ..logging_config import logger
from .currencies import get_currency
from .exceptions import ApiRequestError, CurrencyNotFoundError, ValidationError


class ExchangeService:
    def __init__(self, rates_file: str = None):
        self.rates_file = rates_file
        self._rates_cache = self._load_rates()
        self._ttl_seconds = settings.get("rates_ttl_seconds", 300)  # 5 минут по умолчанию

    def _load_rates(self) -> Dict[str, Any]:
        """Загружает курсы из базы данных"""
        data = db.load_data("rates")
        if not data:
            # Инициализируем базовыми курсами если данных нет
            data = self._initialize_default_rates()
        return data

    def _save_rates(self, data: Dict[str, Any]):
        """Сохраняет курсы в базу данных"""
        db.save_data("rates", data)

    def _initialize_default_rates(self) -> Dict[str, Any]:
        """Инициализирует базовые курсы по умолчанию"""
        default_rates = {
            "rates": {
                "EUR_USD": {"rate": 1.0786, "updated_at": datetime.now().isoformat()},
                "BTC_USD": {"rate": 59337.21, "updated_at": datetime.now().isoformat()},
                "ETH_USD": {"rate": 3720.00, "updated_at": datetime.now().isoformat()},
                "USD_RUB": {"rate": 98.42, "updated_at": datetime.now().isoformat()},
            },
            "source": "StubService",
            "last_refresh": datetime.now().isoformat(),
            "metadata": {"total_rates": 4}
        }
        db.save_data("rates", default_rates)
        return default_rates

    def _is_rate_fresh(self, rate_data: Dict[str, Any]) -> bool:
        """Проверяет актуальность курса с TTL"""
        if "updated_at" not in rate_data:
            return False

        try:
            updated_at = datetime.fromisoformat(rate_data["updated_at"].replace('Z', '+00:00'))
            now = datetime.now().replace(tzinfo=None) if updated_at.tzinfo else datetime.now()
            time_diff = now - updated_at.replace(tzinfo=None) if updated_at.tzinfo else now - updated_at
            return time_diff < timedelta(seconds=self._ttl_seconds)
        except (ValueError, TypeError) as e:
            logger.warning(f"Ошибка проверки актуальности курса: {e}")
            return False

    def _get_rate_with_ttl_check(self, pair: str) -> Optional[float]:
        """Получает курс с проверкой TTL"""
        rate_data = self._rates_cache.get("rates", {}).get(pair)

        if not rate_data:
            return None

        if self._is_rate_fresh(rate_data):
            logger.debug(f"Курс {pair} актуален, используется кеш")
            return rate_data["rate"]
        else:
            logger.warning(f"Курс {pair} устарел (TTL: {self._ttl_seconds} сек)")
            return None

    def _fetch_rate_from_stub(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Заглушка для получения курса (в реальном приложении здесь был бы API вызов)"""
        # Валидируем валюты
        try:
            get_currency(from_currency)
            get_currency(to_currency)
        except CurrencyNotFoundError as e:
            raise ValidationError(str(e)) from e

        stub_rates = {
            "USD_EUR": 0.927, "EUR_USD": 1.0786,
            "USD_BTC": 0.00001685, "BTC_USD": 59337.21,
            "USD_ETH": 0.0002688, "ETH_USD": 3720.00,
            "USD_RUB": 0.01016, "RUB_USD": 98.42,
            "BTC_ETH": 15.95, "ETH_BTC": 0.0627,
            "EUR_BTC": 0.0000156, "BTC_EUR": 64102.56,
            "EUR_ETH": 0.0029, "ETH_EUR": 345.0,
        }

        pair = f"{from_currency}_{to_currency}"
        return stub_rates.get(pair)

    @log_action("Получение курса обмена")
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Получает курс обмена между валютами с проверкой TTL"""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}_{to_currency}"

        # Проверяем кеш с TTL
        cached_rate = self._get_rate_with_ttl_check(pair)
        if cached_rate is not None:
            return cached_rate

        # Если курс устарел или отсутствует, получаем новый
        logger.info(f"Запрос нового курса (TTL истек): {pair}")
        rate = self._fetch_rate_from_stub(from_currency, to_currency)

        if rate is not None:
            # Обновляем кеш
            if "rates" not in self._rates_cache:
                self._rates_cache["rates"] = {}

            self._rates_cache["rates"][pair] = {
                "rate": rate,
                "updated_at": datetime.now().isoformat()
            }
            self._rates_cache["last_refresh"] = datetime.now().isoformat()
            self._rates_cache["source"] = "StubService"
            self._save_rates(self._rates_cache)
            logger.info(f"Курс обновлен: {pair} = {rate}")
        else:
            logger.warning(f"Курс не найден: {pair}")

        return rate

    @log_action("Получение информации о курсе")
    def get_rate_info(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """Получает информацию о курсе с метаданными и проверкой TTL"""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return {
                "rate": 1.0,
                "updated_at": datetime.now().isoformat(),
                "from_currency": from_currency,
                "to_currency": to_currency,
                "pair": f"{from_currency}_{to_currency}",
                "is_fresh": True,
                "ttl_seconds": self._ttl_seconds
            }

        pair = f"{from_currency}_{to_currency}"
        rate_data = self._rates_cache.get("rates", {}).get(pair, {})

        # Проверяем актуальность
        is_fresh = self._is_rate_fresh(rate_data)
        rate = self.get_exchange_rate(from_currency, to_currency)

        if rate is None:
            raise ApiRequestError(f"Курс {from_currency}→{to_currency} недоступен")

        return {
            "rate": rate,
            "updated_at": rate_data.get("updated_at", datetime.now().isoformat()),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "pair": pair,
            "is_fresh": is_fresh,
            "ttl_seconds": self._ttl_seconds,
            "needs_refresh": not is_fresh
        }

    @log_action("Принудительное обновление курсов")
    def refresh_rates(self):
        """Принудительно обновляет все курсы"""
        logger.info(f"Начало принудительного обновления курсов (TTL: {self._ttl_seconds} сек)")

        # Получаем список всех пар из stub_rates
        supported_pairs = [
            ("USD", "EUR"), ("EUR", "USD"),
            ("USD", "BTC"), ("BTC", "USD"),
            ("USD", "ETH"), ("ETH", "USD"),
            ("USD", "RUB"), ("RUB", "USD"),
            ("BTC", "ETH"), ("ETH", "BTC"),
            ("EUR", "BTC"), ("BTC", "EUR"),
            ("EUR", "ETH"), ("ETH", "EUR"),
        ]

        updated_count = 0
        new_rates = {}

        for from_curr, to_curr in supported_pairs:
            rate = self._fetch_rate_from_stub(from_curr, to_curr)
            if rate is not None:
                pair = f"{from_curr}_{to_curr}"
                new_rates[pair] = {
                    "rate": rate,
                    "updated_at": datetime.now().isoformat()
                }
                updated_count += 1

        if updated_count > 0:
            self._rates_cache["rates"] = new_rates
            self._rates_cache["last_refresh"] = datetime.now().isoformat()
            self._rates_cache["source"] = "StubService"
            self._rates_cache["metadata"] = {"total_rates": updated_count}
            self._save_rates(self._rates_cache)
            logger.info(f"Обновлено курсов: {updated_count}")
        else:
            logger.warning("Не удалось обновить ни одного курса")

    def get_ttl_info(self) -> Dict[str, Any]:
        """Возвращает информацию о TTL настройках"""
        return {
            "ttl_seconds": self._ttl_seconds,
            "ttl_minutes": self._ttl_seconds // 60,
            "total_cached_rates": len(self._rates_cache.get("rates", {})),
            "last_refresh": self._rates_cache.get("last_refresh")
        }
