from typing import List, Optional, Tuple

from ..decorators import log_action
from ..infra.database import db
from ..logging_config import logger
from .exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    UserNotFoundError,
    ValidationError,
)
from .exchange_service import ExchangeService
from .models import Portfolio, User


class UserManager:
    def __init__(self, data_file: str = None):
        self.data_file = data_file

    def _load_users(self) -> List[User]:
        """Загружает пользователей из базы данных"""
        data = db.load_data("users")
        return [User.from_dict(user_data) for user_data in data]

    def _save_users(self, users: List[User]):
        """Сохраняет пользователей в базу данных"""
        data = [user.to_dict() for user in users]
        db.save_data("users", data)

    @log_action("CHECK_USERNAME", verbose=False)
    def is_username_taken(self, username: str) -> bool:
        """Проверяет, занято ли имя пользователя"""
        users = self._load_users()
        return any(user.username == username for user in users)

    @log_action("REGISTER", verbose=True)
    def create_user(self, username: str, password: str) -> User:
        """Создает нового пользователя"""
        if self.is_username_taken(username):
            raise ValidationError(f"Имя пользователя '{username}' уже занято")

        users = self._load_users()

        # Генерация нового ID
        user_id = max([user.user_id for user in users], default=0) + 1

        user = User(user_id, username, password)
        users.append(user)
        self._save_users(users)

        # Создаем пустой портфель для пользователя
        portfolio_manager = PortfolioManager()
        portfolio_manager.create_portfolio(user_id)

        logger.info(f"Зарегистрирован новый пользователь: {username} (ID: {user_id})")
        return user

    @log_action("GET_USER", verbose=False)
    def get_user(self, username: str) -> Optional[User]:
        users = self._load_users()
        for user in users:
            if user.username == username:
                return user
        return None

    @log_action("LOGIN", verbose=True)
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self.get_user(username)
        if not user:
            raise UserNotFoundError(username=username)

        if not user.verify_password(password):
            raise AuthenticationError("Неверный пароль")

        logger.info(f"Успешная аутентификация пользователя: {username}")
        return user


class PortfolioManager:
    def __init__(self, data_file: str = None):
        self.data_file = data_file
        self.exchange_service = ExchangeService()

    def _load_portfolios(self) -> List[Portfolio]:
        """Загружает портфели из базы данных"""
        data = db.load_data("portfolios")
        return [Portfolio.from_dict(portfolio_data) for portfolio_data in data]

    def _save_portfolios(self, portfolios: List[Portfolio]):
        """Сохраняет портфели в базу данных"""
        data = [portfolio.to_dict() for portfolio in portfolios]
        db.save_data("portfolios", data)

    @log_action("GET_PORTFOLIO", verbose=False)
    def get_portfolio(self, user_id: int) -> Optional[Portfolio]:
        portfolios = self._load_portfolios()
        for portfolio in portfolios:
            if portfolio.user_id == user_id:
                return portfolio
        return None

    @log_action("CREATE_PORTFOLIO", verbose=True)
    def create_portfolio(self, user_id: int) -> Portfolio:
        portfolios = self._load_portfolios()
        portfolio = Portfolio(user_id)
        portfolios.append(portfolio)
        self._save_portfolios(portfolios)
        return portfolio

    def ensure_portfolio(self, user_id: int) -> Portfolio:
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            portfolio = self.create_portfolio(user_id)
        return portfolio

    @log_action("BUY", verbose=True)
    def buy_currency(self, user_id: int, currency: str, amount: float) -> Tuple[float, float, float]:
        """
        Покупка валюты

        Returns:
            Tuple[старый_баланс, стоимость_в_USD, курс]
        """
        # Валидация суммы
        if amount <= 0:
            raise ValidationError("Сумма покупки должна быть положительной")

        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            portfolio = self.create_portfolio(user_id)

        currency = currency.upper()

        # Валидация валюты
        from .currencies import get_currency
        try:
            currency_obj = get_currency(currency)
        except CurrencyNotFoundError as e:
            raise ValidationError(str(e))

        # Создаем кошелек если его нет
        if not portfolio.has_wallet(currency):
            portfolio.add_currency(currency)

        wallet = portfolio.get_wallet(currency)
        old_balance = wallet.balance

        # Выполняем пополнение
        wallet.deposit(amount)

        # Рассчитываем стоимость покупки
        rate = self.exchange_service.get_exchange_rate(currency, 'USD')
        if rate is None:
            raise ApiRequestError(f"Не удалось получить курс для {currency}→USD")

        cost_usd = amount * rate

        # Сохраняем изменения
        portfolios = self._load_portfolios()
        for i, p in enumerate(portfolios):
            if p.user_id == user_id:
                portfolios[i] = portfolio
                break
        self._save_portfolios(portfolios)

        logger.info(f"Покупка валюты: пользователь {user_id}, {amount} {currency} по курсу {rate}")

        return old_balance, cost_usd, rate

    @log_action("SELL", verbose=True)
    def sell_currency(self, user_id: int, currency: str, amount: float) -> Tuple[float, float, float]:
        """
        Продажа валюты

        Returns:
            Tuple[старый_баланс, выручка_в_USD, курс]
        """
        # Валидация суммы
        if amount <= 0:
            raise ValidationError("Сумма продажи должна быть положительной")

        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            raise UserNotFoundError(user_id=user_id)

        currency = currency.upper()
        wallet = portfolio.get_wallet(currency)

        if not wallet:
            raise ValidationError(f"У вас нет кошелька '{currency}'")

        old_balance = wallet.balance

        try:
            # Выполняем снятие
            wallet.withdraw(amount)
        except InsufficientFundsError:
            logger.warning(f"Попытка продажи при недостаточных средствах: {currency} {amount}")
            raise

        # Рассчитываем выручку
        rate = self.exchange_service.get_exchange_rate(currency, 'USD')
        if rate is None:
            raise ApiRequestError(f"Не удалось получить курс для {currency}→USD")

        revenue_usd = amount * rate

        # Сохраняем изменения
        portfolios = self._load_portfolios()
        for i, p in enumerate(portfolios):
            if p.user_id == user_id:
                portfolios[i] = portfolio
                break
        self._save_portfolios(portfolios)

        logger.info(f"Продажа валюты: пользователь {user_id}, {amount} {currency} по курсу {rate}")

        return old_balance, revenue_usd, rate


class ExchangeService:
    """Сервис для работы с курсами валют"""

    def __init__(self, rates_file: str = None):
        from .exchange_service import ExchangeService as ES
        self._service = ES(rates_file)

    @log_action("GET_RATE", verbose=True)
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        try:
            # Валидация валют
            from .currencies import get_currency
            get_currency(from_currency)
            get_currency(to_currency)

            rate = self._service.get_exchange_rate(from_currency, to_currency)
            if rate is None:
                raise ApiRequestError(f"Курс {from_currency}→{to_currency} недоступен")

            return rate

        except CurrencyNotFoundError as e:
            raise ValidationError(str(e))

    @log_action("GET_RATE_INFO", verbose=True)
    def get_rate_info(self, from_currency: str, to_currency: str) -> dict:
        try:
            # Валидация валют
            from .currencies import get_currency
            get_currency(from_currency)
            get_currency(to_currency)

            return self._service.get_rate_info(from_currency, to_currency)

        except CurrencyNotFoundError as e:
            raise ValidationError(str(e))
