"""
Singleton для управления настройками приложения
"""
import os
from typing import Any, Dict

import toml


class SettingsLoader:
    """
    Singleton для загрузки и управления настройками приложения

    Реализация через __new__ как наиболее простой и читаемый способ
    для базового синглтона в Python.
    """

    _instance = None
    _settings: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsLoader, cls).__new__(cls)
            cls._instance._load_settings()
        return cls._instance

    def _load_settings(self):
        """Загружает настройки из pyproject.toml и переменных окружения"""
        # Базовые настройки по умолчанию
        default_settings = {
            "data_directory": "data",
            "rates_ttl_seconds": 300,  # 5 минут
            "default_base_currency": "USD",
            "log_level": "INFO",
            "log_file": "logs/valutatrade.log",
            "max_log_size_mb": 10,
            "backup_count": 5,
            # Новые настройки для парсер-сервиса
            "parser_update_interval": 5,
            "exchangerate_api_key": "your_exchangerate_api_key_here",
            "coingecko_api_key": "",
        }

        # Пытаемся загрузить из pyproject.toml
        try:
            if os.path.exists("pyproject.toml"):
                with open("pyproject.toml", "r") as f:
                    pyproject_data = toml.load(f)

                # Извлекаем настройки из секции [tool.valutatrade]
                tool_settings = pyproject_data.get("tool", {}).get("valutatrade", {})
                default_settings.update(tool_settings)
        except Exception as e:
            print(f"Warning: Could not load settings from pyproject.toml: {e}")

        # Переопределяем настройки переменными окружения
        env_mappings = {
            "DATA_DIR": "data_directory",
            "RATES_TTL": "rates_ttl_seconds",
            "DEFAULT_CURRENCY": "default_base_currency",
            "LOG_LEVEL": "log_level",
            "LOG_FILE": "log_file",
            # Новые переменные для парсер-сервиса
            "PARSER_UPDATE_INTERVAL": "parser_update_interval",
            "EXCHANGERATE_API_KEY": "exchangerate_api_key",
            "COINGECKO_API_KEY": "coingecko_api_key",
        }

        for env_var, setting_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                # Преобразуем типы данных
                if setting_key in ["rates_ttl_seconds", "parser_update_interval"]:
                    default_settings[setting_key] = int(env_value)
                else:
                    default_settings[setting_key] = env_value

        self._settings = default_settings

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение настройки

        Args:
            key: Ключ настройки
            default: Значение по умолчанию если ключ не найден

        Returns:
            Значение настройки
        """
        return self._settings.get(key, default)

    def reload(self):
        """Перезагружает настройки"""
        self._load_settings()

    def get_data_path(self, filename: str) -> str:
        """Возвращает полный путь к файлу в директории данных"""
        data_dir = self.get("data_directory", "data")
        return os.path.join(data_dir, filename)

    def __getitem__(self, key: str) -> Any:
        """Позволяет использовать settings['key'] синтаксис"""
        return self._settings[key]

    def __contains__(self, key: str) -> bool:
        """Проверяет наличие ключа"""
        return key in self._settings


# Глобальный экземпляр синглтона
settings = SettingsLoader()
