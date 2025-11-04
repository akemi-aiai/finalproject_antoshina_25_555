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
        logger.info("🚀 Запуск обновления курсов валют...")

        if sources is None:
            sources = list(self.clients.keys())

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_processed": [],
            "rates_fetched": 0,
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
                logger.info(f"📡 Получение данных от {source}...")

                # Получаем курсы от API
                rates = self.clients[source].fetch_rates()

                # Создаем исторические записи
                for pair, rate in rates.items():
                    record = self._create_historical_record(pair, rate, source)
                    historical_records.append(record)
                    all_rates[pair] = {
                        "rate": rate,
                        "updated_at": record["timestamp"],
                        "source": source
                    }

                results["rates_fetched"] += len(rates)
                results["sources_processed"].append({
                    "source": source,
                    "rates_count": len(rates),
                    "status": "success"
                })

                logger.info(f"✅ {source}: получено {len(rates)} курсов")

            except ApiRequestError as e:
                error_msg = f"Ошибка получения данных от {source}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["sources_processed"].append({
                    "source": source,
                    "rates_count": 0,
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

                logger.info(f"💾 Сохранено {len(all_rates)} курсов в кеш")

            except Exception as e:
                error_msg = f"Ошибка сохранения данных: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["success"] = False

        # Формируем итоговое сообщение
        if results["success"]:
            logger.info(f"✅ Обновление завершено успешно. "
                       f"Обработано источников: {len(results['sources_processed'])}, "
                       f"Получено курсов: {results['rates_fetched']}")
        else:
            logger.warning(f"⚠️  Обновление завершено с ошибками. "
                          f"Успешных источников: {len([s for s in results['sources_processed'] if s['status'] == 'success'])}, "
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
        from_currency, to_currency = pair.split("_")

        record_id = f"{from_currency}_{to_currency}_{timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        return {
            "id": record_id,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": rate,
            "timestamp": timestamp.isoformat(),
            "source": source,
            "meta": {
                "raw_id": config.CRYPTO_ID_MAP.get(from_currency, from_currency),
                "request_ms": 0,  # Заполняется в API клиентах
                "status_code": 200,
                "etag": ""
            }
        }

    def get_update_status(self) -> Dict[str, Any]:
        """
        Возвращает статус последнего обновления

        Returns:
            Словарь со статусом
        """
        cache_data = self.storage.load_cache()
        history_data = self.storage.load_historical_data()

        return {
            "cache": {
                "last_refresh": cache_data.get("last_refresh"),
                "total_pairs": len(cache_data.get("pairs", {})),
                "is_fresh": self.storage.is_cache_fresh()
            },
            "history": {
                "total_records": len(history_data.get("history", {})),
                "last_update": history_data.get("metadata", {}).get("last_update")
            }
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
