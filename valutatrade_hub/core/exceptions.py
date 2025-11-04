"""
Пользовательские исключения для системы управления валютным кошельком
"""

class WalletError(Exception):
    """Базовое исключение для ошибок кошелька"""
    pass


class InsufficientFundsError(WalletError):
    """Недостаточно средств на счете"""

    def __init__(self, available: float, required: float, currency_code: str):
        self.available = available
        self.required = required
        self.currency_code = currency_code
        super().__init__(
            f"Недостаточно средств: доступно {available} {currency_code}, требуется {required} {currency_code}"
        )


class CurrencyNotFoundError(WalletError):
    """Неизвестная валюта"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(WalletError):
    """Ошибка при обращении к внешнему API"""

    def __init__(self, reason: str = "неизвестная ошибка"):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class UserNotFoundError(WalletError):
    """Пользователь не найден"""

    def __init__(self, username: str = None, user_id: int = None):
        self.username = username
        self.user_id = user_id
        if username:
            super().__init__(f"Пользователь '{username}' не найден")
        elif user_id:
            super().__init__(f"Пользователь с ID {user_id} не найден")
        else:
            super().__init__("Пользователь не найден")


class AuthenticationError(WalletError):
    """Ошибка аутентификации"""
    pass


class ValidationError(WalletError):
    """Ошибка валидации данных"""
    pass
