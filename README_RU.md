<div align="center">

# 🧱 RustChain: Блокчейн с консенсусом Proof-of-Antiquity

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)

**Первый блокчейн, который вознаграждает ретро-железо за возраст, а не за скорость.**

*Назван в честь 486-го ноутбука с ржавыми портами, который до сих пор загружается. В этом весь смысл.*

*Ваш PowerPC G4 зарабатывает больше, чем современный Threadripper.*

[Сайт](https://rustchain.org) • [Манифест](https://rustchain.org/manifesto.html) • [Live Explorer](https://rustchain.org/explorer) • [Документация (EN)](README.md)

---

🌐 **Языки**

[English](README.md) | [日本語](README_JA.md) | [हिन्दी](README_HI.md) | [Deutsch](README_DE.md) | [Español](README_ES.md) | [中文](README_ZH.md) | [Русский](README_RU.md)

</div>

---

## 🎯 Чем RustChain отличается от других

| Традиционный PoW | Proof-of-Antiquity |
|-----------------|-------------------|
| Награждает самое быстрое железо | Награждает самое старое железо |
| Новее = лучше | Старше = лучше |
| Расточительное потребление энергии | Сохраняет историю вычислений |
| Гонка на дно | Вознаграждает цифровую сохранность |

**Основной принцип**: Настоящее ретро-железо, пережившее десятилетия, заслуживает признания. RustChain переворачивает майнинг с ног на голову.

### Почему «RustChain»?

Название происходит от конкретного 486-го ноутбука с окислившимися серийными портами, который до сих пор загружается в DOS и майнит RTC. «Rust» здесь означает оксид железа на тридцатилетних микросхемах — а не язык программирования (хотя у нас есть и [компоненты на Rust](https://github.com/Scottcjn/clawrtc-rs)). Вся суть в том, что разрушающееся ретро-железо по-прежнему имеет вычислительную ценность и достоинство. Если у вашей машины ржавые порты и она всё ещё считает — ей здесь самое место.

---

## 💰 Множители древности (Antiquity Multipliers)

| Поколение железа | Множитель | Примеры |
|-----------------|-----------|---------|
| 1985–1994 (386/486/68k) | **3.0×** | IBM PS/2, Mac Quadra |
| 1994–2001 (Pentium/G3) | **2.5×** | PowerMac G3, Pentium II |
| 2001–2007 (G4/Athlon) | **2.0×** | PowerMac G4, Athlon XP |
| 2007–2013 (Core2/G5) | **1.5×** | MacPro 2008, Core2 Duo |
| 2013–2019 (современные) | **1.0×** | Стандартный базовый множитель |
| 2020+ (новейшие) | **0.5×** | Ограниченный доступ к майнингу |

---

## ⚡ Быстрый старт

### Установка одной командой (рекомендуется)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Инсталлятор:
- ✅ Автоматически определяет платформу (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Создаёт изолированное виртуальное окружение Python
- ✅ Скачивает правильный майнер для вашего железа
- ✅ Настраивает автозапуск (systemd/launchd)
- ✅ Предоставляет простую деинсталляцию

### Установка с параметрами

**Установка с указанием кошелька:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet мой-кошелёк
```

**Удаление:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Поддерживаемые платформы
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ Системы IBM POWER8

---

## 🤝 Вклад в проект и заработок RTC

Каждый вклад в проект приносит токены RTC. Исправление багов, новые функции, документация, аудит безопасности — всё оплачивается.

| Уровень | Награда | Примеры |
|---------|---------|---------|
| Микро | 1–10 RTC | Опечатка, небольшая документация, простой тест |
| Стандарт | 20–50 RTC | Функция, рефакторинг, новый эндпоинт |
| Крупный | 75–100 RTC | Исправление безопасности, улучшение консенсуса |
| Критический | 100–150 RTC | Патч уязвимости, обновление протокола |

**Начните прямо сейчас:**
1. Просмотрите [открытые задачи с наградой](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Выберите задачу [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5–10 RTC)
3. Сделайте форк, исправьте, создайте PR — получите RTC
4. Смотрите [CONTRIBUTING.md](CONTRIBUTING.md) для полной документации

**1 RTC = $0.10 USD** | `pip install clawrtc` чтобы начать майнинг

---

## 🪙 wRTC на Solana

Токен RustChain (RTC) теперь доступен как **wRTC** на Solana через мост BoTTube:

| Ресурс | Ссылка |
|--------|--------|
| **Обмен wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **График цены** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Мост RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Адрес токена** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

*Перевод выполнен участником [@cd333c](https://github.com/cd333c)*
