from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .utils import load_json_file, save_json_file


class ExchangeService:
    def __init__(self, rates_file: str = "data/rates.json"):
        self.rates_file = rates_file
        self._rates_cache = self._load_rates()

    def _load_rates(self) -> Dict[str, Any]:
        """Загружает курсы из файла"""
        data = load_json_file(self.rates_file)
        if not data:
            # Инициализируем базовыми курсами если файла нет
            data = {
                "EUR_USD": {"rate": 1.0786, "updated_at": datetime.now().isoformat()},
                "BTC_USD": {"rate": 59337.21, "updated_at": datetime.now().isoformat()},
                "ETH_USD": {"rate": 3720.00, "updated_at": datetime.now().isoformat()},
                "source": "StubService",
                "last_refresh": datetime.now().isoformat()
            }
            self._save_rates(data)
        return data

    def _save_rates(self, data: Dict[str, Any]):
        """Сохраняет курсы в файл"""
        save_json_file(self.rates_file, data)

    def _is_rate_fresh(self, rate_data: Dict[str, Any]) -> bool:
        """Проверяет актуальность курса (считаем свежим если обновлен менее 5 минут назад)"""
        if "updated_at" not in rate_data:
            return False

        try:
            updated_at = datetime.fromisoformat(rate_data["updated_at"])
            return datetime.now() - updated_at < timedelta(minutes=5)
        except (ValueError, TypeError):
            return False

    def _fetch_rate_from_stub(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Заглушка для получения курса (в реальном приложении здесь был бы API вызов)"""
        stub_rates = {
            "USD_EUR": 0.927, "EUR_USD": 1.0786,
            "USD_BTC": 0.00001685, "BTC_USD": 59337.21,
            "USD_ETH": 0.0002688, "ETH_USD": 3720.00,
            "USD_RUB": 98.42, "RUB_USD": 0.01016,
            "BTC_ETH": 15.95, "ETH_BTC": 0.0627,
            "EUR_BTC": 0.0000156, "BTC_EUR": 64102.56,
        }

        pair = f"{from_currency}_{to_currency}"
        return stub_rates.get(pair)

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Получает курс обмена между валютами"""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}_{to_currency}"

        # Проверяем кеш
        if pair in self._rates_cache and self._is_rate_fresh(self._rates_cache[pair]):
            return self._rates_cache[pair]["rate"]

        # Получаем новый курс из заглушки
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

        return rate

    def get_rate_info(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """Получает информацию о курсе с метаданными"""
        rate = self.get_exchange_rate(from_currency, to_currency)
        pair = f"{from_currency.upper()}_{to_currency.upper()}"

        if rate is None:
            return {}

        rate_data = self._rates_cache.get(pair, {})
        return {
            "rate": rate,
            "updated_at": rate_data.get("updated_at", datetime.now().isoformat()),
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper()
        }
