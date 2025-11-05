#!/usr/bin/env python3
"""Главный модуль приложения Valutatrade Hub"""

import os
import sys

from valutatrade_hub.cli.interface import WalletCLI
from valutatrade_hub.infra.settings import settings
from valutatrade_hub.logging_config import logger

# Добавляем текущую директорию в путь Python
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Точка входа в приложение"""
    try:
        # Инициализация системы
        logger.info("Запуск приложения Valutatrade Hub")

        # Выводим информацию о настройках
        print("Valutatrade Hub v0.1.0")
        print(f"Директория данных: {settings.get('data_directory', 'data')}")
        print(f"Уровень логирования: {settings.get('log_level', 'INFO')}")
        print("-" * 50)

        # Запуск CLI
        cli = WalletCLI()
        cli.cmdloop()

    except KeyboardInterrupt:
        print("\n\nПриложение завершено пользователем")
        logger.info("Приложение завершено по запросу пользователя")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}", exc_info=True)
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("Завершение работы приложения")


if __name__ == "__main__":
    main()
