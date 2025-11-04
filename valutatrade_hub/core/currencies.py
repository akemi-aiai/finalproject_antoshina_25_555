"""
Модуль для работы с валютами - базовые классы и фабрика
"""
from abc import ABC, abstractmethod
from typing import Dict

from .exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс для валют"""

    def __init__(self, name: str, code: str):
        self._validate_code(code)
        self._validate_name(name)

        self._name = name
        self._code = code.upper()

    @property
    def name(self) -> str:
        return self._name

    @property
    def code(self) -> str:
        return self._code

    def _validate_code(self, code: str):
        """Валидация кода валюты"""
        if not code or not isinstance(code, str):
            raise ValueError("Код валюты не может быть пустым")
        if not (2 <= len(code) <= 5):
            raise ValueError("Код валюты должен содержать от 2 до 5 символов")
        if not code.replace(" ", "").isalnum():
            raise ValueError("Код валюты должен содержать только буквы и цифры")

    def _validate_name(self, name: str):
        """Валидация названия валюты"""
        if not name or not isinstance(name, str):
            raise ValueError("Название валюты не может быть пустым")
        if len(name.strip()) == 0:
            raise ValueError("Название валюты не может состоять только из пробелов")

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строковое представление для UI/логов"""
        pass

    def __str__(self) -> str:
        return self.get_display_info()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', code='{self.code}')"


class FiatCurrency(Currency):
    """Фиатная валюта (традиционные деньги)"""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self._issuing_country = issuing_country

    @property
    def issuing_country(self) -> str:
        return self._issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта"""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0):
        super().__init__(name, code)
        self._algorithm = algorithm
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def market_cap(self) -> float:
        return self._market_cap

    @market_cap.setter
    def market_cap(self, value: float):
        if value < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")
        self._market_cap = value

    def get_display_info(self) -> str:
        mcap_str = f"{self.market_cap:.2e}" if self.market_cap > 1e6 else f"{self.market_cap:,.2f}"
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap_str})"


# Реестр валют (синглтон через модуль)
_currency_registry: Dict[str, Currency] = {}


def _initialize_currency_registry():
    """Инициализация реестра базовыми валютами"""
    global _currency_registry

    # Фиатные валюты
    _currency_registry["USD"] = FiatCurrency("US Dollar", "USD", "United States")
    _currency_registry["EUR"] = FiatCurrency("Euro", "EUR", "Eurozone")
    _currency_registry["RUB"] = FiatCurrency("Russian Ruble", "RUB", "Russia")

    # Криптовалюты
    _currency_registry["BTC"] = CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12)
    _currency_registry["ETH"] = CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11)
    _currency_registry["LTC"] = CryptoCurrency("Litecoin", "LTC", "Scrypt", 5.8e9)


def get_currency(code: str) -> Currency:
    """
    Фабричный метод для получения валюты по коду

    Args:
        code: Код валюты (например, "USD", "BTC")

    Returns:
        Объект Currency

    Raises:
        CurrencyNotFoundError: Если валюта с таким кодом не найдена
    """
    if not _currency_registry:
        _initialize_currency_registry()

    code_upper = code.upper()
    if code_upper not in _currency_registry:
        raise CurrencyNotFoundError(code)

    return _currency_registry[code_upper]


def register_currency(currency: Currency):
    """
    Регистрация новой валюты в реестре

    Args:
        currency: Объект валюты для регистрации
    """
    global _currency_registry
    _currency_registry[currency.code] = currency


def get_supported_currencies() -> Dict[str, Currency]:
    """Возвращает словарь всех поддерживаемых валют"""
    if not _currency_registry:
        _initialize_currency_registry()
    return _currency_registry.copy()


def is_currency_supported(code: str) -> bool:
    """Проверяет, поддерживается ли валюта"""
    if not _currency_registry:
        _initialize_currency_registry()
    return code.upper() in _currency_registry
