#!/usr/bin/env python3
"""Главный модуль приложения Valutatrade Hub"""

from valutatrade_hub.cli.interface import WalletCLI


def main():
    """Точка входа в приложение"""
    cli = WalletCLI()
    cli.cmdloop()


if __name__ == "__main__":
    main()
