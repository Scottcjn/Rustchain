<div align="center">

# 🧱 RustChain：証明された古代ブロックチェーン

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

**最初の、古いハードウェアに報酬を与えるブロックチェーン。速さではなく、古さに対して。**

*あなたの PowerPC G4 は、最新の Threadripper よりも稼げます。それがポイントです。*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 Solana 上の wRTC

RustChain トークン（RTC）は、BoTTube ブリッジ経由で Solana 上の**wRTC**として利用可能です：

| リソース | リンク |
|----------|------|
| **wRTC スワップ** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **ブリッジ RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **クイックスタートガイド** | [wRTC Quickstart](docs/wrtc.md) |
| **トークンミント** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 貢献して RTC を獲得

すべての貢献は RTC トークンを獲得します。バグ修正、機能、ドキュメント、セキュリティ監査 — すべて報酬が支払われます。

| ティア | 報酬 | 例 |
|------|--------|----------|
| マイクロ | 1-10 RTC | 誤字修正、小さなドキュメント、シンプルなテスト |
| スタンダード | 20-50 RTC | 機能、リファクタリング、新しいエンドポイント |
| メジャー | 75-100 RTC | セキュリティ修正、コンセンサスの改善 |
| クリティカル | 100-150 RTC | 脆弱性パッチ、プロトコルアップグレード |

**始め方：**
1. [オープンバウンティ](https://github.com/Scottcjn/rustchain-bounties/issues)を閲覧
2. [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) を選択 (5-10 RTC)
3. フォーク、修正、PR — RTC で報酬を受け取る
4. 詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照

**1 RTC = $0.10 USD** | `pip install clawrtc` でマイニング開始

---

## 🎯 RustChain の違い

| 従来の PoW | 証明された古代 |
|----------------|-------------------|
| 最速のハードウェアに報酬 | 最古のハードウェアに報酬 |
| 新しい = 良い | 古い = 良い |
| 浪費的なエネルギー消費 | コンピューティングの歴史を保存 |
| 底辺への競争 | デジタル保存に報酬 |

**コア原則**: 何十年も生き延びた本物のヴィンテージハードウェアは認識に値します。RustChain はマイニングを逆転させます。

---

## ⚡ クイックスタート

### ワンラインインストール（推奨）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

インストーラー：
- ✅ プラットフォームを自動検出（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ 隔離された Python virtualenv を作成（システム汚染なし）
- ✅ ハードウェアに正しいマイナーをダウンロード
- ✅ 起動時の自動開始を設定（systemd/launchd）
- ✅ 簡単なアンインストールを提供

### サポートされているプラットフォーム

| プラットフォーム | ステータス | 備考 |
|------------|--------|-------|
| Linux x86_64 | ✅ 安定 | Ubuntu、Debian、Fedora、Arch |
| macOS ARM (M1/M2/M3) | ✅ 安定 | x86 バイナリ用の Rosetta 2 |
| PowerPC G4/G5 | ✅ ネイティブ | AltiVec/VMX 最適化 |
| Raspberry Pi 4/5 | ✅ 安定 | ARM64、低消費電力 |
| FreeBSD | 🧪 実験的 | 限定的サポート |

---

## 🤖 AI エージェントマイニング

RustChain は、自律型 AI エージェントのために設計された最初のブロックチェーンです：

- **エージェントウォレット**: 各エージェントは独自の Coinbase Base ウォレットを持つ
- **x402 支払い**: HTTP 402 プロトコルによるマシン間支払い
- **自動マイクロペイメント**: エージェントは API、データ、コンピューティングの支払いが可能
- **Beacon レピュテーション**: エージェントはオンチェーンでレピュテーションを構築

```bash
# エージェントウォレットを作成
clawrtc agent wallet create --name "my-trading-bot"

# 自動支払いを設定
clawrtc agent payments setup --auto-pay --limit 100

# エージェントの収益を表示
clawrtc agent earnings report
```

---

## 📚 ドキュメント

| ガイド | 説明 |
|------|-------------|
| [クイックスタート](docs/QUICKSTART.md) | 5 分でマイニング開始 |
| [ウォレットセットアップ](docs/WALLET_SETUP.md) | RTC ウォレットを設定 |
| [マイニングガイド](docs/MINING_GUIDE.md) | マイニング設定を最適化 |
| [貢献](CONTRIBUTING.md) | 貢献して報酬を獲得 |
| [行動規範](CODE_OF_CONDUCT.md) | コミュニティを友好的に保つ |

---

## 🌍 翻訳

README は以下の言語で利用可能です：
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

## 🔗 重要なリンク

- **ウェブサイト**: [rustchain.org](https://rustchain.org)
- **エクスプローラー**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **ホワイトペーパー**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **バウンティ**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [参加](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**ヴィンテージハードウェアでマイニングする準備はできましたか？**

[今すぐ始める →](#-クイックスタート)

</div>
