CLI-приложение для получения и анализа валютных и криптовалютных курсов.

---

## Идея проекта

Программа позволяет:
- получать актуальные курсы фиатных и криптовалют (через CoinGecko и ExchangeRate API);
- сохранять историю курсов;
- управлять виртуальным портфелем валют (покупка/продажа);
- работать в офлайн-режиме с кэшем (TTL).



## Установка

1. Установите зависимости:

make install  или   poetry install


2. Запуск проекта
make project



## Где хранить ключи
Ключи API берутся из:
.env
переменных окружения
или файла infra/settings.py
CoinGecko можно использовать без ключа.

4. asciinema

[![asciicast](https://asciinema.org/a/4gsBJZFC45Ie7tgc9vqUewc8c)](https://asciinema.org/a/4gsBJZFC45Ie7tgc9vqUewc8c)