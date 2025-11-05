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
            "EUR_USD": {"rate": 1.0786, "updated_at": datetime.now().isoformat()},
            "BTC_USD": {"rate": 59337.21, "updated_at": datetime.now().isoformat()},
            "ETH_USD": {"rate": 3720.00, "updated_at": datetime.now().isoformat()},
            "USD_RUB": {"rate": 98.42, "updated_at": datetime.now().isoformat()},
            "source": "StubService",
            "last_refresh": datetime.now().isoformat()
        }
        db.save_data("rates", default_rates)
        return default_rates

    def _is_rate_fresh(self, rate_data: Dict[str, Any]) -> bool:
        """Проверяет актуальность курса"""
        if "updated_at" not in rate_data:
            return False

        try:
            updated_at = datetime.fromisoformat(rate_data["updated_at"])
            ttl_seconds = settings.get("rates_ttl_seconds", 300)
            return datetime.now() - updated_at < timedelta(seconds=ttl_seconds)
        except (ValueError, TypeError):
            return False

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
        """Получает курс обмена между валютами"""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}_{to_currency}"

        # Проверяем кеш
        if pair in self._rates_cache and self._is_rate_fresh(self._rates_cache[pair]):
            logger.debug(f"Используется кешированный курс: {pair}")
            return self._rates_cache[pair]["rate"]

        # Получаем новый курс из заглушки
        logger.info(f"Запрос нового курса: {pair}")
        rate = self._fetch_rate_from_stub(from_currency, to_currency)

        if rate is not None:
            # Обновляем кеш
            self._rates_cache[pair] = {
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
        """Получает информацию о курсе с метаданными"""
        rate = self.get_exchange_rate(from_currency, to_currency)
        pair = f"{from_currency.upper()}_{to_currency.upper()}"

        if rate is None:
            raise ApiRequestError(f"Курс {from_currency}→{to_currency} недоступен")

        rate_data = self._rates_cache.get(pair, {})
        return {
            "rate": rate,
            "updated_at": rate_data.get("updated_at", datetime.now().isoformat()),
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "pair": pair
        }

    @log_action("Принудительное обновление курсов")
    def refresh_rates(self):
        """Принудительно обновляет все курсы"""
        logger.info("Начало принудительного обновления курсов")

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
        for from_curr, to_curr in supported_pairs:
            rate = self._fetch_rate_from_stub(from_curr, to_curr)
            if rate is not None:
                pair = f"{from_curr}_{to_curr}"
                self._rates_cache[pair] = {
                    "rate": rate,
                    "updated_at": datetime.now().isoformat()
                }
                updated_count += 1

        if updated_count > 0:
            self._rates_cache["last_refresh"] = datetime.now().isoformat()
            self._rates_cache["source"] = "StubService"
            self._save_rates(self._rates_cache)
            logger.info(f"Обновлено курсов: {updated_count}")
        else:
            logger.warning("Не удалось обновить ни одного курса")
