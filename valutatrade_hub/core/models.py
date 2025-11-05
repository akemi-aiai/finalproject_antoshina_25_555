import hashlib
import secrets
from datetime import datetime
from typing import Dict, Optional

from ..decorators import log_action, log_transaction
from .currencies import CurrencyNotFoundError, get_currency
from .exceptions import InsufficientFundsError, ValidationError


class User:
    def __init__(self, user_id: int, username: str, password: str,
                 salt: str = None, registration_date: datetime = None):
        self._user_id = user_id
        self._username = username
        self._salt = salt or self._generate_salt()
        self._hashed_password = self._hash_password(password, self._salt)
        self._registration_date = registration_date or datetime.now()

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str):
        if not value or not isinstance(value, str):
            raise ValidationError("Имя пользователя не может быть пустым")
        if len(value.strip()) < 3:
            raise ValidationError("Имя пользователя должно содержать не менее 3 символов")
        self._username = value

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def _generate_salt(self) -> str:
        return secrets.token_hex(8)

    def _hash_password(self, password: str, salt: str) -> str:
        if len(password) < 4:
            raise ValidationError("Пароль должен содержать не менее 4 символов")
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @log_action("Получение информации о пользователе")
    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }

    @log_action("Смена пароля")
    def change_password(self, new_password: str):
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        return self._hashed_password == self._hash_password(password, self._salt)

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict):
        registration_date = datetime.fromisoformat(data["registration_date"])
        user = cls(
            user_id=data["user_id"],
            username=data["username"],
            password="temp",
            salt=data["salt"],
            registration_date=registration_date
        )
        user._hashed_password = data["hashed_password"]
        return user


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        # Валидация и получение информации о валюте
        try:
            self._currency = get_currency(currency_code)
        except CurrencyNotFoundError as e:
            raise ValidationError(f"Неизвестная валюта '{currency_code}'") from e

        self._balance = balance


    @property
    def currency_code(self) -> str:
        return self._currency.code

    @property
    def currency(self):
        return self._currency

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise ValidationError("Баланс должен быть числом")
        if value < 0:
            raise ValidationError("Баланс не может быть отрицательным")
        self._balance = float(value)

    @log_transaction()
    def deposit(self, amount: float):
        if amount <= 0:
            raise ValidationError("Сумма пополнения должна быть положительной")
        self.balance += amount

    @log_transaction()
    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValidationError("Сумма снятия должна быть положительной")
        if amount > self.balance:
            raise InsufficientFundsError(
                available=self.balance,
                required=amount,
                currency_code=self.currency_code
            )
        self.balance -= amount

    @log_action("Получение информации о балансе")
    def get_balance_info(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "currency_name": self._currency.name,
            "balance": self._balance,
            "display_info": self._currency.get_display_info()
        }

    def to_dict(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )


class Portfolio:
    def __init__(self, user_id: int, wallets: Dict[str, Wallet] = None):
        self._user_id = user_id
        self._wallets = wallets or {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        return self._wallets.copy()

    @log_action("Добавление валюты в портфель")
    def add_currency(self, currency_code: str):
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            raise ValidationError(f"Кошелек для валюты {currency_code} уже существует")

        # Валидируем валюту через фабрику
        get_currency(currency_code)

        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())

    def has_wallet(self, currency_code: str) -> bool:
        return currency_code.upper() in self._wallets

    @log_action("Расчет общей стоимости портфеля")
    def get_total_value(self, base_currency: str = 'USD') -> float:
        from .usecases import ExchangeService
        exchange_service = ExchangeService()
        total_value = 0.0

        # Валидируем базовую валюту
        try:
            get_currency(base_currency)
        except CurrencyNotFoundError as e:
            raise ValidationError(f"Неизвестная базовая валюта '{base_currency}'") from e


        for currency, wallet in self._wallets.items():
            if currency == base_currency:
                total_value += wallet.balance
            else:
                rate = exchange_service.get_exchange_rate(currency, base_currency)
                if rate is None:
                    raise ValidationError(f"Не удалось получить курс для {currency}→{base_currency}")
                total_value += wallet.balance * rate

        return total_value

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "wallets": {
                currency: wallet.to_dict()
                for currency, wallet in self._wallets.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict):
        wallets = {
            currency: Wallet.from_dict(wallet_data)
            for currency, wallet_data in data["wallets"].items()
        }
        return cls(user_id=data["user_id"], wallets=wallets)
