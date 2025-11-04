import cmd
import shlex

from prettytable import PrettyTable

from ..core.usecases import ExchangeService, PortfolioManager, UserManager
from ..core.utils import format_currency_amount


class WalletCLI(cmd.Cmd):
    intro = "Добро пожаловать в систему управления валютным кошельком!\nВведите 'help' для списка команд."
    prompt = "wallet> "

    def __init__(self):
        super().__init__()
        self.user_manager = UserManager()
        self.portfolio_manager = PortfolioManager()
        self.exchange_service = ExchangeService()
        self.current_user = None
        self.current_portfolio = None

    def _parse_args(self, args: str) -> dict:
        """Парсит аргументы в формате --key value"""
        try:
            parts = shlex.split(args)
            result = {}
            i = 0
            while i < len(parts):
                if parts[i].startswith('--'):
                    key = parts[i][2:]
                    if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                        result[key] = parts[i + 1]
                        i += 2
                    else:
                        result[key] = True
                        i += 1
                else:
                    i += 1
            return result
        except Exception as err:
            raise ValueError("Something went wrong") from err

    def _check_auth(self) -> bool:
        """Проверяет авторизацию пользователя"""
        if not self.current_user:
            print("Сначала выполните login")
            return False
        return True

    def do_register(self, args):
        """Регистрация нового пользователя: register --username <name> --password <pass>"""
        try:
            parsed_args = self._parse_args(args)
            username = parsed_args.get('username')
            password = parsed_args.get('password')

            if not username or not password:
                print("Использование: register --username <name> --password <pass>")
                return

            user = self.user_manager.create_user(username, password)
            print(f"Пользователь '{username}' зарегистрирован (id={user.user_id}). Войдите: login --username {username} --password ****")

        except ValueError as e:
            print(f"Ошибка регистрации: {e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")

    def do_login(self, args):
        """Вход в систему: login --username <name> --password <pass>"""
        try:
            parsed_args = self._parse_args(args)
            username = parsed_args.get('username')
            password = parsed_args.get('password')

            if not username or not password:
                print("Использование: login --username <name> --password <pass>")
                return

            user = self.user_manager.authenticate_user(username, password)

            if user:
                self.current_user = user
                self.current_portfolio = self.portfolio_manager.ensure_portfolio(user.user_id)
                self.prompt = f"wallet[{username}]> "
                print(f"Вы вошли как '{username}'")
            else:
                print("Неверное имя пользователя или пароль")

        except Exception as e:
            print(f"Ошибка входа: {e}")

    def do_logout(self, args):
        """Выход из системы: logout"""
        self.current_user = None
        self.current_portfolio = None
        self.prompt = "wallet> "
        print("Вы вышли из системы")

    def do_show_portfolio(self, args):
        """Показать портфель: show-portfolio [--base <currency>]"""
        if not self._check_auth():
            return

        try:
            parsed_args = self._parse_args(args)
            base_currency = parsed_args.get('base', 'USD').upper()

            # Проверяем валидность базовой валюты
            if base_currency not in ['USD', 'EUR', 'BTC', 'ETH']:
                print(f"Неизвестная базовая валюта '{base_currency}'")
                return

            portfolio = self.current_portfolio
            wallets = portfolio.wallets

            if not wallets:
                print("Ваш портфель пуст. Используйте 'buy' для покупки валюты.")
                return

            table = PrettyTable()
            table.field_names = ["Валюта", "Баланс", f"В {base_currency}"]
            table.align = "r"
            table.align["Валюта"] = "l"

            total_value = 0.0

            for currency, wallet in wallets.items():
                balance = wallet.balance

                if currency == base_currency:
                    value_in_base = balance
                else:
                    rate = self.exchange_service.get_exchange_rate(currency, base_currency)
                    if rate is None:
                        print(f"Не удалось получить курс для {currency}→{base_currency}")
                        return
                    value_in_base = balance * rate

                total_value += value_in_base

                table.add_row([
                    currency,
                    format_currency_amount(balance, currency),
                    format_currency_amount(value_in_base, base_currency)
                ])

            print(f"Портфель пользователя '{self.current_user.username}' (база: {base_currency}):")
            print(table)
            print("-" * 50)
            print(f"ИТОГО: {format_currency_amount(total_value, base_currency)}")

        except Exception as e:
            print(f"Ошибка показа портфеля: {e}")

    def do_buy(self, args):
        """Купить валюту: buy --currency <code> --amount <number>"""
        if not self._check_auth():
            return

        try:
            parsed_args = self._parse_args(args)
            currency = parsed_args.get('currency')
            amount_str = parsed_args.get('amount')

            if not currency or not amount_str:
                print("Использование: buy --currency <code> --amount <number>")
                return

            try:
                amount = float(amount_str)
                if amount <= 0:
                    print("'amount' должен быть положительным числом")
                    return
            except ValueError:
                print("'amount' должен быть числом")
                return

            currency = currency.upper()

            # Получаем курс для отчета
            rate = self.exchange_service.get_exchange_rate(currency, 'USD')
            if rate is None:
                print(f"Не удалось получить курс для {currency}→USD")
                return

            old_balance, cost_usd = self.portfolio_manager.buy_currency(
                self.current_user.user_id, currency, amount
            )

            print(f"Покупка выполнена: {format_currency_amount(amount, currency)} по курсу {rate:,.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"- {currency}: было {format_currency_amount(old_balance, currency)} → стало {format_currency_amount(old_balance + amount, currency)}")
            print(f"Оценочная стоимость покупки: ${cost_usd:,.2f}")

        except ValueError as e:
            print(f"Ошибка покупки: {e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")

    def do_sell(self, args):
        """Продать валюту: sell --currency <code> --amount <number>"""
        if not self._check_auth():
            return

        try:
            parsed_args = self._parse_args(args)
            currency = parsed_args.get('currency')
            amount_str = parsed_args.get('amount')

            if not currency or not amount_str:
                print("Использование: sell --currency <code> --amount <number>")
                return

            try:
                amount = float(amount_str)
                if amount <= 0:
                    print("'amount' должен быть положительным числом")
                    return
            except ValueError:
                print("'amount' должен быть числом")
                return

            currency = currency.upper()

            # Получаем курс для отчета
            rate = self.exchange_service.get_exchange_rate(currency, 'USD')
            if rate is None:
                print(f"Не удалось получить курс для {currency}→USD")
                return

            old_balance, revenue_usd = self.portfolio_manager.sell_currency(
                self.current_user.user_id, currency, amount
            )

            print(f"Продажа выполнена: {format_currency_amount(amount, currency)} по курсу {rate:,.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"- {currency}: было {format_currency_amount(old_balance, currency)} → стало {format_currency_amount(old_balance - amount, currency)}")
            print(f"Оценочная выручка: ${revenue_usd:,.2f}")

        except ValueError as e:
            print(f"Ошибка продажи: {e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")

    def do_get_rate(self, args):
        """Получить курс валюты: get-rate --from <currency> --to <currency>"""
        try:
            parsed_args = self._parse_args(args)
            from_currency = parsed_args.get('from')
            to_currency = parsed_args.get('to')

            if not from_currency or not to_currency:
                print("Использование: get-rate --from <currency> --to <currency>")
                return

            from_currency = from_currency.upper()
            to_currency = to_currency.upper()

            rate_info = self.exchange_service.get_rate_info(from_currency, to_currency)

            if not rate_info:
                print(f"Курс {from_currency}→{to_currency} недоступен. Повторите попытку позже.")
                return

            rate = rate_info['rate']
            updated_at = rate_info['updated_at']

            # Форматируем дату
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                 formatted_date = updated_at

            # Вычисляем обратный курс
            reverse_rate = 1 / rate if rate != 0 else 0

            print(f"Курс {from_currency}→{to_currency}: {rate:,.6f} (обновлено: {formatted_date})")
            print(f"Обратный курс {to_currency}→{from_currency}: {reverse_rate:,.6f}")

        except Exception as e:
            print(f"Ошибка получения курса: {e}")

    def do_info(self, args):
        """Показать информацию о пользователе: info"""
        if not self._check_auth():
            return

        user_info = self.current_user.get_user_info()
        table = PrettyTable()
        table.field_names = ["Поле", "Значение"]

        for key, value in user_info.items():
            table.add_row([key, value])

        print(table)

    def do_exit(self, args):
        """Выход из приложения: exit"""
        print("До свидания!")
        return True

    # Альтернативные короткие команды
    def do_sp(self, args):
        """Сокращение для show-portfolio"""
        self.do_show_portfolio(args)

    def do_br(self, args):
        """Сокращение для get-rate"""
        self.do_get_rate(args)
