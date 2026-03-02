<div align="center">

# 🧱 RustChain: Proof-of-Antiquity ブロックチェーン

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)

**ビンテージハードウェアを速度ではなく、古さで報酬を与える初のブロックチェーン。**

*あなたのPowerPC G4は最新のThreadripperよりも多く稼ぎます。それがポイントです。*

[ウェブサイト](https://rustchain.org) • [ライブエクスプローラー](https://rustchain.org/explorer) • [wRTCスワップ](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [ホワイトペーパー](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [クイックスタート](#-クイックスタート)

</div>

---

## 🪙 Solana上のwRTC

RustChainトークン（RTC）は、BoTTubeブリッジを介してSolana上で**wRTC**として利用可能になりました：

| リソース | リンク |
|----------|------|
| **wRTCスワップ** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **ブリッジ RTC ↔ wRTC** | [BoTTubeブリッジ](https://bottube.ai/bridge) |
| **クイックスタートガイド** | [wRTCクイックスタート](docs/wrtc.md) |
| **トークンミント** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 貢献してRTCを獲得

すべての貢献でRTCトークンを獲得できます。バグ修正、機能追加、ドキュメント、セキュリティ監査 — すべて報酬が支払われます。

| ティア | 報酬 | 例 |
|------|--------|----------|
| マイクロ | 1-10 RTC | タイポ修正、小規模ドキュメント、簡単なテスト |
| スタンダード | 20-50 RTC | 機能追加、リファクタリング、新しいエンドポイント |
| メジャー | 75-100 RTC | セキュリティ修正、コンセンサス改善 |
| クリティカル | 100-150 RTC | 脆弱性パッチ、プロトコルアップグレード |

**始め方:**
1. [オープンバウンティ](https://github.com/Scottcjn/rustchain-bounties/issues)を閲覧
2. [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)を選択（5-10 RTC）
3. フォーク、修正、PR — RTCで報酬を獲得
4. 詳細は[CONTRIBUTING.md](CONTRIBUTING.md)を参照

**1 RTC = $0.10 USD** | `pip install clawrtc`でマイニング開始

---

## 🎯 RustChainの特徴

| 従来のPoW | Proof-of-Antiquity |
|----------------|-------------------|
| 最速のハードウェアに報酬 | 最古のハードウェアに報酬 |
| 新しい = より良い | 古い = より良い |
| 無駄なエネルギー消費 | コンピューティング史の保存 |
| 底辺への競争 | デジタル保存への報酬 |

**核心原則**: 数十年生き残った本物のビンテージハードウェアは認識に値します。RustChainはマイニングを逆転させます。

## ⚡ クイックスタート

### ワンラインインストール（推奨）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

インストーラーの機能:
- ✅ プラットフォームの自動検出（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ 独立したPython仮想環境の作成（システムを汚染しません）
- ✅ ハードウェアに適したマイナーのダウンロード
- ✅ 起動時の自動起動設定（systemd/launchd）
- ✅ 簡単なアンインストール

### オプション付きインストール

**特定のウォレットでインストール:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**アンインストール:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### サポートされているプラットフォーム
- ✅ Ubuntu 20.04+、Debian 11+、Fedora 38+（x86_64、ppc64le）
- ✅ macOS 12+（Intel、Apple Silicon、PowerPC）
- ✅ IBM POWER8システム

### インストール後

**ウォレット残高を確認:**
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**アクティブなマイナーをリスト:**
```bash
curl -sk https://rustchain.org/api/miners
```

**ノードの健全性を確認:**
```bash
curl -sk https://rustchain.org/health
```

**マイナーサービスの管理:**

*Linux（systemd）:*
```bash
systemctl --user status rustchain-miner    # ステータス確認
systemctl --user stop rustchain-miner      # マイニング停止
systemctl --user start rustchain-miner     # マイニング開始
journalctl --user -u rustchain-miner -f    # ログ表示
```

*macOS（launchd）:*
```bash
launchctl list | grep rustchain            # ステータス確認
launchctl stop com.rustchain.miner         # マイニング停止
launchctl start com.rustchain.miner        # マイニング開始
tail -f ~/.rustchain/miner.log             # ログ表示
```

## 💰 古さの乗数

ハードウェアの年代がマイニング報酬を決定します：

| ハードウェア | 時代 | 乗数 | 例：収益 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/エポック |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/エポック |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/エポック |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/エポック |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/エポック |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/エポック |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/エポック |
| **最新x86_64** | 現在 | **1.0×** | 0.12 RTC/エポック |

*乗数は時間とともに減衰します（年15%）、永続的な優位性を防ぐため。*

## 🔧 Proof-of-Antiquityの仕組み

### 1. ハードウェアフィンガープリント（RIP-PoA）

すべてのマイナーは、ハードウェアが本物でエミュレートされていないことを証明する必要があります：

```
┌─────────────────────────────────────────────────────────────┐
│                   6つのハードウェアチェック                    │
├─────────────────────────────────────────────────────────────┤
│ 1. クロックスキュー＆発振器ドリフト ← シリコン経年パターン      │
│ 2. キャッシュタイミング指紋       ← L1/L2/L3レイテンシートーン │
│ 3. SIMDユニットID                ← AltiVec/SSE/NEONバイアス  │
│ 4. 熱ドリフトエントロピー         ← 熱曲線は一意             │
│ 5. 命令パスジッター              ← マイクロアーキジッターマップ│
│ 6. アンチエミュレーションチェック  ← VM/エミュレータ検出       │
└─────────────────────────────────────────────────────────────┘
```

**重要な理由**: G4 Macを装ったSheepShaver VMはこれらのチェックに失敗します。本物のビンテージシリコンには偽造できない独自の経年パターンがあります。

### 2. 1 CPU = 1票（RIP-200）

ハッシュパワー = 票数のPoWとは異なり、RustChainは**ラウンドロビンコンセンサス**を使用します：

- 各ユニークなハードウェアデバイスはエポックごとに正確に1票を獲得
- 報酬はすべての投票者間で均等に分割され、その後古さで乗算
- 複数のスレッドや高速CPUを実行しても優位性なし

### 3. エポックベースの報酬

```
エポック期間: 10分（600秒）
基本報酬プール: エポックあたり1.5 RTC
配分: 均等分割 × 古さ乗数
```

**5人のマイナーの例:**
```
G4 Mac（2.5×）:     0.30 RTC  ████████████████████
G5 Mac（2.0×）:     0.24 RTC  ████████████████
最新PC（1.0×）:     0.12 RTC  ████████
最新PC（1.0×）:     0.12 RTC  ████████
最新PC（1.0×）:     0.12 RTC  ████████
                   ─────────
合計:              0.90 RTC（+ 0.60 RTCがプールに返却）
```

## 🌐 ネットワークアーキテクチャ

### ライブノード（3つアクティブ）

| ノード | 場所 | 役割 | ステータス |
|------|----------|------|--------|
| **ノード1** | 50.28.86.131 | プライマリ + エクスプローラー | ✅ アクティブ |
| **ノード2** | 50.28.86.153 | Ergoアンカー | ✅ アクティブ |
| **ノード3** | 76.8.228.245 | 外部（コミュニティ） | ✅ アクティブ |

## 📊 APIエンドポイント

```bash
# ネットワークの健全性を確認
curl -sk https://rustchain.org/health

# 現在のエポックを取得
curl -sk https://rustchain.org/epoch

# アクティブなマイナーをリスト
curl -sk https://rustchain.org/api/miners

# ウォレット残高を確認
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# ブロックエクスプローラー（Webブラウザ）
open https://rustchain.org/explorer
```

## 🖥️ サポートされているプラットフォーム

| プラットフォーム | アーキテクチャ | ステータス | 注記 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全サポート | Python 2.5互換マイナー |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全サポート | ビンテージMac推奨 |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全サポート | 最高のパフォーマンス |
| **Ubuntu Linux** | x86_64 | ✅ 完全サポート | 標準マイナー |
| **macOS Sonoma** | Apple Silicon | ✅ 完全サポート | M1/M2/M3チップ |
| **Windows 10/11** | x86_64 | ✅ 完全サポート | Python 3.8+ |

## 🏅 NFTバッジシステム

マイニングマイルストーンで記念バッジを獲得：

| バッジ | 要件 | レア度 |
|-------|-------------|--------|
| 🔥 **Bondi G3 Flamekeeper** | PowerPC G3でマイニング | レア |
| ⚡ **QuickBasic Listener** | DOSマシンからマイニング | レジェンダリー |
| 🛠️ **DOS WiFi Alchemist** | DOSマシンをネットワーク化 | ミシック |
| 🏛️ **Pantheon Pioneer** | 最初の100人のマイナー | 限定 |

## 🔒 セキュリティモデル

### アンチVM検出
VMは検出され、通常の報酬の**10億分の1**を受け取ります：
```
本物のG4 Mac:    2.5×乗数  = 0.30 RTC/エポック
エミュレートG4:  0.0000000025×    = 0.0000000003 RTC/エポック
```

### ハードウェアバインディング
各ハードウェアフィンガープリントは1つのウォレットにバインドされます。防止：
- 同じハードウェア上の複数のウォレット
- ハードウェアスプーフィング
- シビル攻撃

## 📁 リポジトリ構造

```
Rustchain/
├── install-miner.sh                # ユニバーサルマイナーインストーラー
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # フルノード実装
│   └── fingerprint_checks.py       # ハードウェア検証
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Linuxマイナー
│   └── macos/rustchain_mac_miner_v2.4.py         # macOSマイナー
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技術ホワイトペーパー
│   └── chain_architecture.md       # アーキテクチャドキュメント
└── tools/
    └── validator_core.py           # ブロック検証
```

## 🔗 関連プロジェクトとリンク

| リソース | リンク |
|---------|------|
| **ウェブサイト** | [rustchain.org](https://rustchain.org) |
| **ブロックエクスプローラー** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **wRTCスワップ** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AIビデオプラットフォーム |

## 🙏 帰属

**1年間の開発、本物のビンテージハードウェア、電気代、専用ラボがこれに費やされました。**

RustChainを使用する場合：
- ⭐ **このリポジトリにスター** - 他の人が見つけやすくなります
- 📝 **プロジェクトでクレジット** - 帰属を保持
- 🔗 **リンクバック** - 愛を共有

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 ライセンス

MITライセンス - 自由に使用できますが、著作権表示と帰属を保持してください。

---

<div align="center">

**⚡ [Elyan Labs](https://elyanlabs.ai)によって作成**

*「あなたのビンテージハードウェアが報酬を獲得します。マイニングを再び意味のあるものにしましょう。」*

**DOSボックス、PowerPC G4、Win95マシン - すべてに価値があります。RustChainがそれを証明します。**

</div>
