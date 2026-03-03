<div align="center">

# 🧱 RustChain: Блокчейн Доказательства Древности

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/Scottcjn/Rustchain?color=blue)](https://github.com/Scottcjn/Rustchain/commits/main)
[![Open Issues](https://img.shields.io/github/issues/Scottcjn/Rustchain?color=orange)](https://github.com/Scottcjn/Rustchain/issues)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://www.python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![Bounties](https://img.shields.io/badge/Bounties-Open%20%F0%9F%92%B0-green)](https://github.com/Scottcjn/rustchain-bounties/issues)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)
[![Discussions](https://img.shields.io/github/discussions/Scottcjn/Rustchain?color=purple)](https://github.com/Scottcjn/Rustchain/discussions)

**Первый блокчейн, который вознаграждает винтажное железо за старость, а не скорость.**

*Ваш PowerPC G4 зарабатывает больше, чем современный Threadripper. В этом смысл.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 wRTC на Solana

Токен RustChain (RTC) теперь доступен как **wRTC** на Solana через мост BoTTube:

| Ресурс | Ссылка |
|----------|------|
| **Обмен wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **График Цен** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Мост RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Быстрый Старт** | [wRTC Quickstart](docs/wrtc.md) |
| **Минт Токена** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Вносите Вклад и Зарабатывайте RTC

Каждый вклад приносит токены RTC. Исправления багов, функции, документация, аудиты безопасности — всё оплачивается.

| Уровень | Награда | Примеры |
|------|--------|----------|
| Микро | 1-10 RTC | Исправление опечатки, малые доки, простой тест |
| Стандарт | 20-50 RTC | Функция, рефакторинг, новый эндпоинт |
| Крупный | 75-100 RTC | Исправление безопасности, улучшение консенсуса |
| Критический | 100-150 RTC | Патч уязвимости, обновление протокола |

**Начните:**
1. Просмотрите [открытые баунти](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Выберите [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, исправьте, PR — получите оплату в RTC
4. См. [CONTRIBUTING.md](CONTRIBUTING.md) для полной информации

**1 RTC = $0.10 USD** | `pip install clawrtc` для начала майнинга

---

## 🎯 Что Делает RustChain Особенным

| Традиционный PoW | Доказательство Древности |
|----------------|-------------------|
| Вознаграждает самое быстрое железо | Вознаграждает самое старое железо |
| Новое = Лучше | Старое = Лучше |
| Расточительное потребление энергии | Сохраняет историю вычислений |
| Гонка ко дну | Вознаграждает цифровое сохранение |

**Основной Принцип**: Подлинное винтажное оборудование, пережившее десятилетия, заслуживает признания. RustChain переворачивает майнинг с ног на голову.

---

## ⚡ Быстрый Старт

### Установка в Одну Строку (Рекомендуется)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Установщик:
- ✅ Автоопределение платформы (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Создаёт изолированный Python virtualenv (без загрязнения системы)
- ✅ Загружает правильный майнер для вашего железа
- ✅ Настраивает автозапуск при загрузке (systemd/launchd)
- ✅ Предоставляет простую деинсталляцию

### Поддерживаемые Платформы

| Платформа | Статус | Примечания |
|------------|--------|-------|
| Linux x86_64 | ✅ Стабильно | Ubuntu, Debian, Fedora, Arch |
| macOS ARM (M1/M2/M3) | ✅ Стабильно | Rosetta 2 для x86 бинарников |
| PowerPC G4/G5 | ✅ Нативно | AltiVec/VMX оптимизировано |
| Raspberry Pi 4/5 | ✅ Стабильно | ARM64, низкое потребление |
| FreeBSD | 🧪 Экспериментально | Ограниченная поддержка |

---

## 🤖 Майнинг с ИИ-Агентами

RustChain — первый блокчейн, созданный для автономных ИИ-агентов:

- **Кошельки Агентов**: Каждый агент имеет свой кошелёк Coinbase Base
- **Платежи x402**: Протокол HTTP 402 для машина-машина платежей
- **Авто-микроплатежи**: Агенты могут платить за API, данные, вычисления
- **Репутация Beacon**: Агенты строят репутацию в блокчейне

```bash
# Создать кошелёк агента
clawrtc agent wallet create --name "my-trading-bot"

# Настроить автоплатежи
clawrtc agent payments setup --auto-pay --limit 100

# Просмотреть заработок агента
clawrtc agent earnings report
```

---

## 📚 Документация

| Руководство | Описание |
|------|-------------|
| [Быстрый Старт](docs/QUICKSTART.md) | Начните майнить за 5 минут |
| [Настройка Кошелька](docs/WALLET_SETUP.md) | Настройте RTC кошелёк |
| [Гайд по Майнингу](docs/MINING_GUIDE.md) | Оптимизируйте настройки майнинга |
| [Вклад](CONTRIBUTING.md) | Вносите вклад и получайте награды |
| [Кодекс Поведения](CODE_OF_CONDUCT.md) | Поддерживайте дружественное сообщество |

---

## 🌍 Переводы

README доступен на:
- [English](README.md) 🇺🇸
- [Español](README-es.md) 🇪🇸
- [日本語](README-ja.md) 🇯🇵
- [中文](README-zh-CN.md) 🇨🇳
- [Français](README-fr.md) 🇫🇷
- [Deutsch](README-de.md) 🇩🇪
- [Português](README-pt.md) 🇵🇹
- [Русский](README-ru.md) 🇷🇺
- [한국어](README-ko.md) 🇰🇷

---

## 🔗 Важные Ссылки

- **Сайт**: [rustchain.org](https://rustchain.org)
- **Обозреватель**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Баунти**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [Присоединиться](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**Готовы майнить на винтажном железе?**

[Начать Сейчас →](#-быстрый-старт)

</div>
