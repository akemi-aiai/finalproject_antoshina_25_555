import hashlib
import secrets
from datetime import datetime
from typing import Dict, Optional


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
            raise ValueError("Имя пользователя не может быть пустым")
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
            raise ValueError("Пароль должен содержать не менее 4 символов")
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }

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
        self.currency_code = currency_code.upper()
        self._balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self.balance += amount

    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if amount > self.balance:
            raise ValueError(f"Недостаточно средств: доступно {self.balance} {self.currency_code}, требуется {amount}")
        self.balance -= amount

    def get_balance_info(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self._balance
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

    def add_currency(self, currency_code: str):
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            raise ValueError(f"Кошелек для валюты {currency_code} уже существует")
        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())

    def has_wallet(self, currency_code: str) -> bool:
        return currency_code.upper() in self._wallets

    def get_total_value(self, base_currency: str = 'USD') -> float:
        from .usecases import ExchangeService
        exchange_service = ExchangeService()
        total_value = 0.0

        for currency, wallet in self._wallets.items():
            if currency == base_currency:
                total_value += wallet.balance
            else:
                rate = exchange_service.get_exchange_rate(currency, base_currency)
                if rate:
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
