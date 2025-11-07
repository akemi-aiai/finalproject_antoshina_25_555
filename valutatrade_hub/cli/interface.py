import cmd
import shlex
from typing import Dict

from prettytable import PrettyTable

from ..core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    UserNotFoundError,
    ValidationError,
)
from ..core.usecases import ExchangeService, PortfolioManager, UserManager
from ..core.utils import (
    format_currency_amount,
    format_currency_display,
    get_supported_currencies_list,
)
from ..decorators import log_action
from ..logging_config import logger


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
        except ValueError as e:
            raise ValidationError(f"Ошибка разбора аргументов: {e}") from e

    def _check_auth(self) -> bool:
        """Проверяет авторизацию пользователя"""
        if not self.current_user:
            print("Сначала выполните login")
            return False
        return True

    @log_action("Регистрация пользователя")
    def do_register(self, args):
        """Регистрация нового пользователя: register --username <name> --password <pass>"""
        try:
            print("Начало регистрации")
            parsed_args = self._parse_args(args)
            username = parsed_args.get('username')
            password = parsed_args.get('password')

            if not username or not password:
                print("Использование: register --username <name> --password <pass>")
                return
            print(f"Создания пользователя: {username}")
            user = self.user_manager.create_user(username, password)
            print(f"Пользователь '{username}' зарегистрирован (id={user.user_id}). Войдите: login --username {username} --password ****")
            print("Теперь выполните login для входа в систему")

        except ValidationError as e:
            print(f"Ошибка регистрации: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при регистрации: {e}")
            print(f"Неожиданная ошибка: {e}")

    @log_action("Вход в систему")
    def do_login(self, args):
        """Вход в систему: login --username <name> --password <pass>"""
        try:
            print("Попытка входа")
            parsed_args = self._parse_args(args)
            username = parsed_args.get('username')
            password = parsed_args.get('password')

            if not username or not password:
                print("Использование: login --username <name> --password <pass>")
                return

            print(f"Аутентификация пользователя {username}")
            user = self.user_manager.authenticate_user(username, password)

            if user:
                self.current_user = user
                self.current_portfolio = self.portfolio_manager.ensure_portfolio(user.user_id)
                self.prompt = f"wallet[{username}]> "
                print(f"Вы вошли как '{username}'")
            else:
                print("Неверное имя пользователя или пароль")

        except (UserNotFoundError, AuthenticationError) as e:
            print(f"Ошибка входа: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при входе: {e}")
            print(f"Ошибка входа: {e}")


    def do_logout(self, args):
        """Выход из системы: logout"""
        if self.current_user:
            logger.info(f"Выход пользователя: {self.current_user.username}")
        self.current_user = None
        self.current_portfolio = None
        self.prompt = "wallet> "
        print("Вы вышли из системы")

    @log_action("Просмотр портфеля")
    def do_show_portfolio(self, args):
        """Показать портфель: show_portfolio [--base <currency>]"""
        if not self._check_auth():
            return

        try:
            # ПЕРЕЗАГРУЖАЕМ СВЕЖИЕ ДАННЫЕ
            from ..core.usecases import PortfolioManager
            portfolio_manager = PortfolioManager()
            fresh_portfolio = portfolio_manager.get_portfolio(self.current_user.user_id)

            if not fresh_portfolio:
                print("Портфель не найден")
                return

            self.current_portfolio = fresh_portfolio  # ОБНОВЛЯЕМ КЕШ

            parsed_args = self._parse_args(args)
            base_currency = parsed_args.get('base', 'USD').upper()

            portfolio = self.current_portfolio
            wallets = portfolio.wallets

            if not wallets:
                print("Ваш портфель пуст. Используйте 'buy' для покупки валюты.")
                return

            table = PrettyTable()
            table.field_names = ["Валюта", "Описание", "Баланс", f"В {base_currency}"]
            table.align = "r"
            table.align["Валюта"] = "l"
            table.align["Описание"] = "l"

            total_value = 0.0

            # ВЫВОДИМ ВСЕ ВАЛЮТЫ
            for currency, wallet in wallets.items():
                balance = wallet.balance

                if currency == base_currency:
                    value_in_base = balance
                else:
                    rate = self.exchange_service.get_exchange_rate(currency, base_currency)
                    if rate is None:
                        print(f"Не удалось получить курс для {currency}→{base_currency}")
                        value_in_base = 0
                    else:
                        value_in_base = wallet.balance * rate

                total_value += value_in_base

                # Получаем информацию о валюте для отображения
                currency_display = format_currency_display(currency)

                table.add_row([
                    currency,
                    currency_display,
                    format_currency_amount(balance, currency),
                    format_currency_amount(value_in_base, base_currency)
                ])

            print(f"Портфель пользователя '{self.current_user.username}' (база: {base_currency}):")
            print(table)
            print("-" * 60)
            print(f"ИТОГО: {format_currency_amount(total_value, base_currency)}")

        except Exception as e:
            logger.error(f"Ошибка при показе портфеля: {e}")
            print(f"Ошибка показа портфеля: {e}")


    @log_action("BUY", verbose=True)
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

            # Валидация суммы
            try:
                amount = float(amount_str)
                if amount <= 0:
                    print("Ошибка: сумма должна быть положительным числом")
                    return
            except ValueError:
                print("Ошибка: сумма должна быть числом")
                return

            currency = currency.upper()

            old_balance, cost_usd, rate = self.portfolio_manager.buy_currency(
                self.current_user.user_id, currency, amount
            )

            print(f"Покупка выполнена: {format_currency_amount(amount, currency)} по курсу {rate:,.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"   - {currency}: было {format_currency_amount(old_balance, currency)} → стало {format_currency_amount(old_balance + amount, currency)}")
            print(f"Оценочная стоимость покупки: ${cost_usd:,.2f}")


        except InsufficientFundsError as e:
            print(f"Ошибка: {e}")
        except (ValidationError, CurrencyNotFoundError) as e:
            print(f"Ошибка: {e}")
            if "неизвестная валюта" in str(e).lower():
                print("Используйте команду 'currencies' для просмотра доступных валют")
        except ApiRequestError as e:
            print(f"Ошибка получения курса: {e}")
            print("Повторите попытку позже")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при покупке: {e}")
            print(f"Неожиданная ошибка: {e}")

    @log_action("SELL", verbose=True)
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

            # Валидация суммы
            try:
                amount = float(amount_str)
                if amount <= 0:
                    print("Ошибка: сумма должна быть положительным числом")
                    return
            except ValueError:
                print("Ошибка: сумма должна быть числом")
                return

            currency = currency.upper()

            old_balance, revenue_usd, rate = self.portfolio_manager.sell_currency(
                self.current_user.user_id, currency, amount
            )

            print(f"Продажа выполнена: {format_currency_amount(amount, currency)} по курсу {rate:,.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"- {currency}: было {format_currency_amount(old_balance, currency)} → стало {format_currency_amount(old_balance - amount, currency)}")
            print(f"Оценочная выручка: ${revenue_usd:,.2f}")

        except InsufficientFundsError as e:
            print(f"Ошибка: {e}")
            print("Проверьте баланс вашего кошелька")
        except (ValidationError, CurrencyNotFoundError) as e:
            print(f"Ошибка: {e}")
            if "нет кошелька" in str(e).lower():
                print("Валюта создаётся автоматически при первой покупке")
        except ApiRequestError as e:
            print(f"Ошибка получения курса: {e}")
            print("Повторите попытку позже")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при продаже: {e}")
            print(f"Неожиданная ошибка: {e}")

    @log_action("GET_RATE", verbose=True)
    def do_get_rate(self, args):
        """Получить курс валюты: get_rate --from <currency> --to <currency>"""
        try:
            parsed_args = self._parse_args(args)
            from_currency = parsed_args.get('from')
            to_currency = parsed_args.get('to')

            if not from_currency or not to_currency:
                print("Использование: get_rate --from <currency> --to <currency>")
                return

            from_currency = from_currency.upper()
            to_currency = to_currency.upper()

            rate_info = self.exchange_service.get_rate_info(from_currency, to_currency)

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

            print(f"Курс {from_currency}→{to_currency}: {rate:,.6f}")
            print(f"Обратный курс {to_currency}→{from_currency}: {reverse_rate:,.6f}")
            print(f"Обновлено: {formatted_date}")

        except (CurrencyNotFoundError, ValidationError) as e:
            print(f"Ошибка: {e}")
            print("\nДоступные валюты:")
            self._show_supported_currencies()
        except ApiRequestError as e:
            print(f"Ошибка: {e}")
            print("Повторите попытку позже или проверьте доступность сервиса")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении курса: {e}")
            print(f"Ошибка получения курса: {e}")

    def do_show_rates(self, args):
        """Показать актуальные курсы: show-rates [--currency <код>] [--top <N>] [--base <валюта>]"""
        try:
            parsed_args = self._parse_args(args)
            currency_filter = parsed_args.get('currency')
            top_str = parsed_args.get('top')
            base_currency = parsed_args.get('base', 'USD').upper()

            from ..parser_service.storage import ParserStorage
            storage = ParserStorage()

            # Загружаем кеш
            cache_data = storage.load_cache()
            rates = cache_data.get("pairs", {})
            last_refresh = cache_data.get("last_refresh")

            if not rates:
                print("Локальный кеш курсов пуст.")
                print("Выполните 'update_rates', чтобы загрузить данные")
                return

            # Фильтруем и сортируем курсы
            filtered_rates = self._filter_rates(rates, currency_filter, base_currency)

            if not filtered_rates:
                if currency_filter:
                    print(f"Курс для '{currency_filter}' не найден в кеше.")
                    print("Проверьте правильность кода валюты или обновите курсы")
                else:
                    print("Нет курсов, соответствующих фильтрам")
                return

            # Применяем топ-N фильтр
            if top_str:
                try:
                    top_n = int(top_str)
                    if top_n <= 0:
                        print("Параметр --top должен быть положительным числом")
                        return
                    # Сортируем по курсу (дорогие сначала) и берем топ-N
                    sorted_rates = sorted(
                        filtered_rates.items(),
                        key=lambda x: x[1]["rate"],
                        reverse=True
                    )[:top_n]
                    filtered_rates = dict(sorted_rates)
                except ValueError:
                    print("Параметр --top должен быть числом")
                    return

            # Выводим результаты
            self._display_rates_table(filtered_rates, last_refresh, base_currency)

        except Exception as e:
            logger.error(f"Ошибка при показе курсов: {e}")
            print(f"Ошибка показа курсов: {e}")

    def _filter_rates(self, rates: Dict, currency_filter: str, base_currency: str) -> Dict:
        """Фильтрует курсы по валюте и базовой валюте"""
        filtered = {}

        for pair, rate_data in rates.items():
            from_curr, to_curr = pair.split("_")

            # Применяем фильтр по валюте
            if currency_filter:
                currency_upper = currency_filter.upper()
                if currency_upper not in [from_curr, to_curr]:
                    continue

            # Применяем фильтр по базовой валюте
            if base_currency != 'USD':  # Пока поддерживаем только USD как базовую
                print("Поддержка других базовых валют кроме USD в разработке")
                break

            filtered[pair] = rate_data

        return filtered

    def _display_rates_table(self, rates: Dict, last_refresh: str, base_currency: str):
        """Отображает курсы в виде таблицы"""
        from datetime import datetime

        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["Валютная пара", "Курс", "Обновлено", "Источник"]
        table.align = "r"
        table.align["Валютная пара"] = "l"
        table.align["Источник"] = "l"

        # Сортируем по алфавиту
        sorted_rates = sorted(rates.items())

        for pair, rate_data in sorted_rates:
            rate = rate_data["rate"]
            updated_at = rate_data["updated_at"]
            source = rate_data["source"]

            # Форматируем время
            try:
                dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                time_str = dt.strftime("%m-%d %H:%M")
            except (ValueError, TypeError):
                time_str = updated_at[:16]


            # Форматируем курс в зависимости от величины
            if rate < 0.001:
                rate_str = f"{rate:.8f}"
            elif rate < 1:
                rate_str = f"{rate:.6f}"
            elif rate < 1000:
                rate_str = f"{rate:.4f}"
            else:
                rate_str = f"{rate:,.2f}"

            table.add_row([pair, rate_str, time_str, source])

        # Заголовок с информацией о времени обновления
        refresh_info = ""
        if last_refresh:
            try:
                dt = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
                refresh_info = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                refresh_info = last_refresh

        print(f"Актуальные курсы (база: {base_currency})")
        if refresh_info:
            print(f"Кеш обновлен: {refresh_info}")
        print("-" * 60)
        print(table)
        print(f"Всего пар: {len(rates)}")



    def _show_supported_currencies(self):
        """Показывает список поддерживаемых валют"""
        try:
            currencies = get_supported_currencies_list()
            if currencies:
                print("Поддерживаемые валюты:", ", ".join(sorted(currencies)))
            else:
                print("Нет доступных валют")
        except Exception as e:
            logger.error(f"Ошибка при получении списка валют: {e}")
            print("Не удалось получить список валют")

    @log_action("Просмотр информации о пользователе")
    def do_info(self, args):
        """Показать информацию о пользователе: info"""
        if not self._check_auth():
            return

        try:
            user_info = self.current_user.get_user_info()
            table = PrettyTable()
            table.field_names = ["Поле", "Значение"]

            for key, value in user_info.items():
                table.add_row([key, value])

            print(table)

        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            print(f"Ошибка: {e}")


    @log_action("UPDATE_RATES", verbose=True)
    def do_update_rates(self, args):
        """Обновить курсы валют: update-rates [--source <coingecko|exchangerate>]"""
        try:
            parsed_args = self._parse_args(args)
            source = parsed_args.get('source')

            print("Запуск обновления курсов валют...")

            from ..parser_service.updater import get_updater
            updater = get_updater()

            # Определяем источники для обновления
            sources = None
            if source:
                if source not in ['coingecko', 'exchangerate']:
                    print("Неверный источник. Допустимые значения: coingecko, exchangerate")
                    return
                sources = [source]
                print(f"Обновление только из источника: {source}")
            else:
                print("Обновление из всех источников...")

            # Выполняем обновление
            results = updater.run_update(sources)

            # Выводим результаты
            print("\nРезультаты обновления:")
            print("-" * 40)

            if results["success"]:
                print("Обновление завершено успешно!")
            else:
                print("Обновление завершено с ошибками")

            # Статус по источникам
            for source_info in results["sources_processed"]:
                status_icon = "OK" if source_info["status"] == "success" else "FAIL"
                print(f"   {status_icon} {source_info['source']}: {source_info['rates_count']} курсов")
                if source_info["status"] == "error":
                    print(f"      Ошибка: {source_info['error']}")


            # Общая статистика
            print("\nОбщая статистика:")
            print(f"Всего курсов: {results['rates_fetched']}")
            print(f"Время: {results['timestamp'][11:19]}")

            # Ошибки
            if results["errors"]:
                print(f"\nОшибки ({len(results['errors'])}):")
                for error in results["errors"]:
                    print(f"   - {error}")

            # Совет по исправлению ошибок
            if not results["success"]:
                print("\nСоветы по устранению ошибок:")
                print("   - Проверьте подключение к интернету")
                print("   - Убедитесь, что API ключи настроены правильно")
                print("   - Проверьте лимиты запросов к API")
                print("   - Используйте 'parser-status' для диагностики")

        except Exception as e:
            logger.error(f"Ошибка при обновлении курсов: {e}")
            print(f"Критическая ошибка при обновлении курсов: {e}")



        """Показать статус парсер-сервиса: parser-status"""
        try:
            from ..parser_service.scheduler import get_scheduler
            from ..parser_service.updater import RatesUpdater

            updater = RatesUpdater()
            scheduler = get_scheduler()

            # Получаем статус обновления
            update_status = updater.get_update_status()
            scheduler_status = scheduler.get_status()

            print("Статус Parser Service:")
            print("-" * 40)

            # Статус планировщика

            print("Планировщик:")
            status_icon = "✔" if scheduler_status["is_running"] else "✖"
            print(f"{status_icon} Статус: {'Запущен' if scheduler_status['is_running'] else 'Остановлен'}")
            print(f"Интервал: {scheduler_status['update_interval_minutes']} мин")
            print(f"Поток: {'Активен' if scheduler_status['thread_alive'] else 'Неактивен'}")


            # Статус последнего обновления
            print("\nПоследнее обновление:")
            if update_status["last_update"]:
                from datetime import datetime
                try:
                    last_update = datetime.fromisoformat(update_status["last_update"])
                    formatted_time = last_update.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"Время: {formatted_time}")
                except (ValueError, TypeError):
                    print(f"Время: {update_status['last_update']}")
            else:
                print("Время: Никогда")

            print(f"Всего пар: {update_status['total_pairs']}")
            print(f"Размер данных: {update_status['storage_size']} байт")

            # Информация о конфигурации
            print("\nКонфигурация:")
            from ..parser_service.config import ParserConfig
            config_ok = ParserConfig.validate_config()
            config_icon = "✔" if config_ok else "no"
            status_text = "Настроены" if config_ok else "Требуют настройки"
            print(f"{config_icon} API ключи: {status_text}")
            print(f"Фиатные валюты: {len(ParserConfig.SUPPORTED_FIAT_CURRENCIES)}")
            print(f"Криптовалюты: {len(ParserConfig.SUPPORTED_CRYPTO_CURRENCIES)}")


        except Exception as e:
            logger.error(f"Ошибка при получении статуса парсера: {e}")
            print(f"Ошибка получения статуса: {e}")

    def do_parser_status(self, args):
        """Показать статус парсер-сервиса: parser-status"""
        try:
            from ..parser_service.config import config
            from ..parser_service.scheduler import get_scheduler
            from ..parser_service.updater import get_updater

            updater = get_updater()
            scheduler = get_scheduler()

            # Получаем статусы
            update_status = updater.get_update_status()
            scheduler_status = scheduler.get_status()
            config_valid = config.validate_config()

            print("Статус Parser Service:")
            print("-" * 40)

            # Статус конфигурации
            print("\nКонфигурация:")
            print(f"Настройки: {'Валидны' if config_valid else 'Требуют внимания'}")
            print(f"ExchangeRate-API: {'Настроен' if config.EXCHANGERATE_API_KEY != '935b702352e0c8d731dae5e3' else 'Не настроен'}")
            print(f"CoinGecko: {'Настроен' if config.COINGECKO_API_KEY else 'Публичный доступ'}")
            print(f"Фиатные валюты: {len(config.FIAT_CURRENCIES)}")
            print(f"₿ Криптовалюты: {len(config.CRYPTO_CURRENCIES)}")

            # Статус планировщика
            print("\nПланировщик:")
            status_icon = "✔" if scheduler_status["is_running"] else "✖"
            status_text = "Запущен" if scheduler_status["is_running"] else "Остановлен"
            print(f"   {status_icon} Статус: {status_text}")
            print(f"   Интервал: {scheduler_status['update_interval_minutes']} мин")
            thread_status = "Активен" if scheduler_status["thread_alive"] else "Неактивен"
            print(f"   Поток: {thread_status}")


            # Статус данных
            print("\nДанные:")
            cache_status = update_status["cache"]
            history_status = update_status["history"]

            cache_icon = "✔" if cache_status["is_fresh"] else "!"
            status_text = "актуален" if cache_status["is_fresh"] else "устарел"
            print(f"   {cache_icon} Кеш: {cache_status['total_pairs']} пар ({status_text})")


            if cache_status["last_refresh"]:
                try:
                    from datetime import datetime
                    last_update = datetime.fromisoformat(cache_status["last_refresh"].replace('Z', '+00:00'))
                    print(f"Последнее обновление: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
                except (ValueError, TypeError):
                    print(f"Последнее обновление: {cache_status['last_refresh']}")


            print(f"История: {history_status['total_records']} записей")

            # Советы
            print("\nСоветы:")
            if not config_valid:
                print("   - Настройте API ключи в переменных окружения")
            if not cache_status["is_fresh"]:
                print("   - Выполните 'update-rates' для обновления данных")
            if not scheduler_status["is_running"]:
                print("   - Запустите 'start-parser' для автоматического обновления")

        except Exception as e:
            logger.error(f"Ошибка при получении статуса парсера: {e}")
            print(f"Ошибка получения статуса: {e}")


    from typing import Dict, List

    from prettytable import PrettyTable
    def _display_history_table(self, history: List[Dict], pair: str):
        """Отображает историю курсов в виде таблицы"""

        table = PrettyTable()
        table.field_names = ["#", "Курс", "Изменение", "Время", "Источник"]
        table.align = "r"
        table.align["Источник"] = "l"

        # Вычисляем изменения
        for i in range(1, len(history)):
            current_rate = history[i]["rate"]
            prev_rate = history[i-1]["rate"]
            if prev_rate != 0:
                change_percent = ((current_rate - prev_rate) / prev_rate) * 100
                history[i]["change"] = change_percent
            else:
                history[i]["change"] = 0

        if history:
            history[0]["change"] = 0

        # Заполняем таблицу (новые записи первыми)
        for i, record in enumerate(history):
            rate = record["rate"]
            change = record.get("change", 0)
            timestamp = record["timestamp"]
            source = record["source"]

            # Форматируем время
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime("%m-%d %H:%M")
            except (ValueError, TypeError):
                time_str = timestamp[:16]


            # Форматируем изменение
            change_icon = "+" if change > 0 else "-" if change < 0 else "0"
            change_str = f"{change_icon} {change:+.2f}%"

            # Форматируем курс
            if rate < 0.001:
                rate_str = f"{rate:.8f}"
            elif rate < 1:
                rate_str = f"{rate:.6f}"
            else:
                rate_str = f"{rate:,.4f}"

            table.add_row([i+1, rate_str, change_str, time_str, source])

        print(f"История курсов {pair}:")
        print("-" * 70)
        print(table)
        print(f"Показано записей: {len(history)}")

        # Статистика изменений
        if len(history) > 1:
            first_rate = history[-1]["rate"]  # Самая старая запись
            last_rate = history[0]["rate"]    # Самая новая запись
            total_change = ((last_rate - first_rate) / first_rate) * 100
            print(f"Общее изменение: {total_change:+.2f}%")

    # Существующие команды оставляем без изменений
    def do_start_parser(self, args):
        """Запустить фоновое обновление курсов: start-parser"""
        try:
            from ..parser_service.scheduler import get_scheduler

            scheduler = get_scheduler()
            scheduler.start()

            print("Фоновое обновление курсов запущено")
            print("Используйте 'parser-status' для проверки статуса")
            print("Используйте 'stop-parser' для остановки")

        except Exception as e:
            logger.error(f"Ошибка при запуске парсера: {e}")
            print(f"Ошибка запуска парсера: {e}")

    def do_stop_parser(self, args):
        """Остановить фоновое обновление курсов: stop-parser"""
        try:
            from ..parser_service.scheduler import get_scheduler

            scheduler = get_scheduler()
            scheduler.stop()

            print("Фоновое обновление курсов остановлено")

        except Exception as e:
            logger.error(f"Ошибка при остановке парсера: {e}")
            print(f"Ошибка остановки парсера: {e}")

    def do_supported_pairs(self, args):
        """Показать поддерживаемые валютные пары: supported-pairs"""
        try:
            from ..parser_service.config import config

            print("Поддерживаемые валютные пары:")
            print("=" * 50)

            print("\nФиатные валюты (к USD):")
            fiat_pairs = [f"{curr}_USD" for curr in config.FIAT_CURRENCIES if curr != "USD"]
            for i, pair in enumerate(sorted(fiat_pairs), 1):
                print(f"   {i:2d}. {pair}")

            print(f"\nВсего фиатных пар: {len(fiat_pairs)}")

            print("\nКриптовалюты (к USD и обратно):")
            crypto_pairs = []
            for crypto in config.CRYPTO_CURRENCIES:
                crypto_pairs.append(f"{crypto}_USD")
                crypto_pairs.append(f"USD_{crypto}")

            # Показываем первые 12 пар
            for i, pair in enumerate(sorted(crypto_pairs)[:12], 1):
                print(f"   {i:2d}. {pair}")

            if len(crypto_pairs) > 12:
                print(f"   ... и еще {len(crypto_pairs) - 12} пар")

            print(f"\nВсего крипто пар: {len(crypto_pairs)}")
            print(f"Всего пар всего: {len(fiat_pairs) + len(crypto_pairs)}")

            print("\nИспользуйте 'show-rates --currency <код>' для просмотра конкретной валюты")
            print("Используйте 'show-rates --top N' для просмотра топ-N самых дорогих валют")

        except Exception as e:
            logger.error(f"Ошибка при получении списка пар: {e}")
            print(f"Ошибка получения списка пар: {e}")

    def do_rates_history(self, args):
        """Показать историю курсов: rates-history [--pair <пара>] [--limit <число>]"""
        try:
            parsed_args = self._parse_args(args)
            pair = parsed_args.get('pair', 'BTC_USD').upper()
            limit_str = parsed_args.get('limit', '10')

            # Валидация пары
            if '_' not in pair:
                print("Неверный формат пары. Используйте: BTC_USD, EUR_USD и т.д.")
                return

            try:
                limit = int(limit_str)
                if limit <= 0 or limit > 50:
                    print("Лимит должен быть от 1 до 50")
                    return
            except ValueError:
                print("Лимит должен быть числом")
                return

            from ..parser_service.storage import ParserStorage

            storage = ParserStorage()
            history = storage.get_rate_history(pair, limit)

            if not history:
                print(f"История для пары {pair} не найдена")
                print("Проверьте правильность пары или выполните 'update_rates'")
                return

            self._display_history_table(history, pair)

        except Exception as e:
            logger.error(f"Ошибка при получении истории курсов: {e}")
            print(f"Ошибка получения истории: {e}")


        """Показать поддерживаемые валютные пары: supported_pairs"""
        try:
            from ..parser_service.config import config

            print("Поддерживаемые валютные пары:")
            print("=" * 50)

            print("\nФиатные валюты (к USD):")
            fiat_pairs = [f"{curr}_USD" for curr in config.FIAT_CURRENCIES if curr != "USD"]
            for i, pair in enumerate(sorted(fiat_pairs), 1):
                print(f"   {i:2d}. {pair}")

            print(f"\nВсего фиатных пар: {len(fiat_pairs)}")

            print("\nКриптовалюты (к USD и обратно):")
            crypto_pairs = []
            for crypto in config.CRYPTO_CURRENCIES:
                crypto_pairs.append(f"{crypto}_USD")
                crypto_pairs.append(f"USD_{crypto}")

            # Показываем первые 12 пар
            for i, pair in enumerate(sorted(crypto_pairs)[:12], 1):
                print(f"   {i:2d}. {pair}")

            if len(crypto_pairs) > 12:
                print(f"   ... и еще {len(crypto_pairs) - 12} пар")

            print(f"\nВсего крипто пар: {len(crypto_pairs)}")
            print(f"Всего пар всего: {len(fiat_pairs) + len(crypto_pairs)}")

            print("\nИспользуйте 'show_rates --currency <код>' для просмотра конкретной валюты")
            print("Используйте 'show_rates --top N' для просмотра топ-N самых дорогих валют")

        except Exception as e:
            logger.error(f"Ошибка при получении списка пар: {e}")
            print(f"Ошибка получения списка пар: {e}")

    def do_currencies(self, args):
        """Показать все поддерживаемые валюты: currencies"""
        try:
            from ..core.currencies import get_supported_currencies

            currencies = get_supported_currencies()
            if not currencies:
                print("Нет доступных валют")
                return

            table = PrettyTable()
            table.field_names = ["Код", "Тип", "Название", "Доп. информация"]
            table.align = "l"

            # ИСПРАВЛЕНИЕ: показываем ВСЕ валюты
            for code, currency in sorted(currencies.items()):
                currency_type = "CRYPTO" if hasattr(currency, 'algorithm') else "FIAT"

                if currency_type == "FIAT":
                    additional = f"Страна: {currency.issuing_country}"
                else:
                    additional = f"Алгоритм: {currency.algorithm}"

                table.add_row([
                    code,
                    currency_type,
                    currency.name,
                    additional
                ])

            print("Поддерживаемые валюты:")
            print(table)
            print(f"Всего валют: {len(currencies)}")

        except Exception as e:
            logger.error(f"Ошибка при получении списка валют: {e}")
            print(f"Ошибка: {e}")



    def do_refresh_rates(self, args):
        """Принудительно обновить курсы валют: refresh_rates"""
        try:
            from ..core.exchange_service import ExchangeService
            exchange_service = ExchangeService()
            exchange_service.refresh_rates()
            print("Курсы валют успешно обновлены")
        except Exception as e:
            logger.error(f"Ошибка при обновлении курсов: {e}")
            print(f"Ошибка обновления курсов: {e}")

    def do_debug(self, args):
        """Показать отладочную информацию: debug"""
        print("=== Отладочная информация ===")
        print(f"Текущий пользователь: {self.current_user.username if self.current_user else 'None'}")
        print(f"Портфель: {'Есть' if self.current_portfolio else 'Нет'}")

        if self.current_portfolio:
            print(f"Количество кошельков: {len(self.current_portfolio.wallets)}")
            for currency, wallet in self.current_portfolio.wallets.items():
                print(f"  - {currency}: {wallet.balance}")

    def do_exit(self, args):
        """Выход из приложения: exit"""
        if self.current_user:
            logger.info(f"Завершение сессии пользователя: {self.current_user.username}")
        print("До свидания!")
        return True

    # Обработчики ошибок по умолчанию
    def default(self, line):
        print(f"Неизвестная команда: {line}")
        print("Введите 'help' для списка команд")

    def emptyline(self):
        # При пустой строке ничего не делаем (не повторяем предыдущую команду)
        pass

        """Сокращение для show_portfolio"""
        self.do_show_portfolio("")

    def do_br(self, args):
        """Сокращение для get_rate"""
        self.do_get_rate(args)

    def do_curr(self, args):
        """Сокращение для currencies"""
        self.do_currencies(args)

    def do_rr(self, args):
        """Сокращение для refresh_rates"""
        self.do_refresh_rates(args)


        """Сокращение для stop_parser"""
        self.do_stop_parser(args)


        """Сокращение для supported_pairs"""
        self.do_supported_pairs(args)

    def do_ur(self, args):
        """Сокращение для update_rates"""
        self.do_update_rates(args)

    def do_sr(self, args):
        """Сокращение для show_rates"""
        self.do_show_rates(args)

    def do_ps(self, args):
        """Сокращение для parser_status"""
        self.do_parser_status(args)

    def do_rh(self, args):
        """Сокращение для rates_history"""
        self.do_rates_history(args)

    def do_sp(self, args):
        """Сокращение для start_parser"""
        self.do_start_parser(args)

    def do_stp(self, args):
        """Сокращение для stop_parser"""
        self.do_stop_parser(args)

    def do_pairs(self, args):
        """Сокращение для supported_pairs"""
        self.do_supported_pairs(args)
