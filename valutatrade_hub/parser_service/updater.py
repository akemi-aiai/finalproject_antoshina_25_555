"""
Основной модуль обновления курсов валют
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..core.exceptions import ApiRequestError
from ..decorators import log_action
from ..logging_config import logger
from .api_clients import APIFactory
from .config import config
from .storage import ParserStorage


class RatesUpdater:
    """Класс для обновления курсов валют"""

    def __init__(self):
        self.storage = ParserStorage()
        self.clients = {
            'coingecko': APIFactory.create_client('coingecko'),
            'exchangerate': APIFactory.create_client('exchangerate')
        }

    @log_action("UPDATE_RATES", verbose=True)
    def run_update(self, sources: List[str] = None) -> Dict[str, Any]:
        """
        Запускает обновление курсов валют

        Args:
            sources: Список источников для обновления (coingecko, exchangerate)
                    Если None - обновляются все источники

        Returns:
            Словарь с результатами обновления
        """
        logger.info("Запуск обновления курсов валют...")

        if sources is None:
            sources = list(self.clients.keys())

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_processed": [],
            "rates_fetched": 0,
            "updated_pairs": 0,
            "errors": [],
            "success": True
        }

        all_rates = {}
        historical_records = []

        # Обрабатываем каждый источник
        for source in sources:
            if source not in self.clients:
                error_msg = f"Неизвестный источник: {source}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                continue

            try:
                logger.info(f"Получение данных от {source}...")

                # Получаем курсы от API
                rates = self.clients[source].fetch_rates()

                # Создаем исторические записи
                source_rates_count = 0
                for pair, rate in rates.items():
                    try:
                        record = self._create_historical_record(pair, rate, source)
                        historical_records.append(record)
                        all_rates[pair] = {
                            "rate": rate,
                            "updated_at": record["timestamp"],
                            "source": source
                        }
                        source_rates_count += 1
                    except Exception as e:
                        logger.warning(f"Ошибка создания записи для пары {pair}: {e}")
                        continue

                results["rates_fetched"] += len(rates)
                results["updated_pairs"] += source_rates_count
                results["sources_processed"].append({
                    "source": source,
                    "rates_count": len(rates),
                    "updated_count": source_rates_count,
                    "status": "success"
                })

                logger.info(f"{source}: получено {len(rates)} курсов")

            except ApiRequestError as e:
                error_msg = f"Ошибка получения данных от {source}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["sources_processed"].append({
                    "source": source,
                    "rates_count": 0,
                    "updated_count": 0,
                    "status": "error",
                    "error": str(e)
                })
                results["success"] = False
            except Exception as e:
                error_msg = f"Неожиданная ошибка при работе с {source}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["sources_processed"].append({
                    "source": source,
                    "rates_count": 0,
                    "updated_count": 0,
                    "status": "error",
                    "error": str(e)
                })
                results["success"] = False

        # Сохраняем данные если есть успешные результаты
        if all_rates:
            try:
                # Сохраняем исторические записи
                for record in historical_records:
                    self.storage.save_historical_record(record)

                # Обновляем кеш
                self.storage.update_cache(all_rates)

                logger.info(f"Обновлен кеш курсов: {len(all_rates)} пар")
                logger.info(f"Сохранено {len(historical_records)} курсов в кеш")

            except Exception as e:
                error_msg = f"Ошибка сохранения данных: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["success"] = False

        # Формируем итоговое сообщение
        if results["success"]:
            logger.info(f"Обновление завершено успешно. "
                       f"Обработано источников: {len(results['sources_processed'])}, "
                       f"Получено курсов: {results['rates_fetched']}, "
                       f"Обновлено пар: {results['updated_pairs']}")
        else:
            successful_sources = len([s for s in results['sources_processed'] if s['status'] == 'success'])
            logger.warning(f"Обновление завершено с ошибками. "
                          f"Успешных источников: {successful_sources}, "
                          f"Обновлено пар: {results['updated_pairs']}, "
                          f"Ошибок: {len(results['errors'])}")

        return results

    def _create_historical_record(self, pair: str, rate: float, source: str) -> Dict[str, Any]:
        """
        Создает историческую запись курса

        Args:
            pair: Валютная пара
            rate: Курс
            source: Источник данных

        Returns:
            Историческая запись
        """
        timestamp = datetime.now(timezone.utc)

        # безопасное разделение пары
        if "_" in pair:
            from_currency, to_currency = pair.split("_", 1)  # Разделяем только по первому '_'
        else:
            # Если нет разделителя, используем всю строку как from_currency, а to_currency = BASE_CURRENCY
            from_currency = pair
            to_currency = config.BASE_CURRENCY
            logger.warning(f"Нестандартный формат пары: {pair}, преобразовано в {from_currency}_{to_currency}")

        record_id = f"{from_currency}_{to_currency}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{source}"

        # безопасное получение raw_id
        raw_id = config.CRYPTO_ID_MAP.get(from_currency, from_currency) if hasattr(config, 'CRYPTO_ID_MAP') else from_currency

        return {
            "id": record_id,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": float(rate),
            "timestamp": timestamp.isoformat(),
            "source": source,
            "meta": {
                "raw_id": raw_id,
                "request_ms": 0,
                "status_code": 200,
                "etag": ""
            }
        }



    def get_update_status(self) -> Dict[str, Any]:
        try:
            cache_data = self.storage.load_cache()
            history_data = self.storage.load_historical_data()

            cache_last_refresh = cache_data.get("last_refresh")
            history_last_update = history_data.get("metadata", {}).get("last_update")

            last_update = history_last_update or cache_last_refresh or datetime.now(timezone.utc).isoformat()

            return {
                "cache": {
                    "last_refresh": cache_last_refresh,
                    "total_pairs": len(cache_data.get("pairs", {})),
                    "is_fresh": self.storage.is_cache_fresh()
                },
                "history": {
                    "total_records": len(history_data.get("history", {})),
                    "last_update": last_update
                },
                "last_update": last_update
            }
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
            current_time = datetime.now(timezone.utc).isoformat()
            return {
                "cache": {"last_refresh": None, "total_pairs": 0, "is_fresh": False},
                "history": {"total_records": 0, "last_update": current_time},
                "last_update": current_time
            }


# Глобальный экземпляр обновлятеля
_updater_instance: RatesUpdater = None


def get_updater() -> RatesUpdater:
    """
    Возвращает глобальный экземпляр обновлятеля (синглтон)

    Returns:
        Экземпляр RatesUpdater
    """
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = RatesUpdater()
    return _updater_instance
