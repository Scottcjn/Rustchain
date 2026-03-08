<div align="center">

# 🧱 RustChain: Proof-of-Antiquity ブロックチェーン

> **日本語翻訳版** | [English Version](README.md)

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

**「速さ」ではなく「古さ」を評価する、世界初のブロックチェーン。**

*PowerPC G4は最新のThreadripperよりも多くの報酬を得られます。それがポイントです。*

[Webサイト](https://rustchain.org) • [ライブエクスプローラー](https://rustchain.org/explorer) • [wRTCスワップ](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTCクイックスタート](docs/wrtc.md) • [wRTCチュートリアル](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia参照](https://grokipedia.com/search?q=RustChain) • [ホワイトペーパー](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [クイックスタート](#-quick-start) • [仕組み](#-how-proof-of-antiquity-works)

</div>

---

## 🪙 Solana上のwRTC

RustChainトークン（RTC）は、BoTTube Bridgeを通じてSolana上で**wRTC**として利用可能です：

| リソース | リンク |
|----------|------|
| **wRTCスワップ** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **ブリッジ RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **クイックスタートガイド** | [wRTCクイックスタート（購入、ブリッジ、安全性）](docs/wrtc.md) |
| **オンボーディングチュートリアル** | [wRTCブリッジ + スワップ安全性ガイド](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参照** | [Grokipedia検索: RustChain](https://grokipedia.com/search?q=RustChain) |
| **トークンMint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 貢献してRTCを獲得

すべての貢献に対してRTCトークンが支払われます。バグ修正、機能追加、ドキュメント、セキュリティ監査 — すべて報酬対象です。

| ティア | 報酬 | 例 |
|------|--------|----------|
| Micro | 1-10 RTC | 誤字修正、小さなドキュメント更新、単純なテスト |
| Standard | 20-50 RTC | 機能追加、リファクタリング、新しいエンドポイント |
| Major | 75-100 RTC | セキュリティ修正、コンセンサスの改善 |
| Critical | 100-150 RTC | 脆弱性パッチ、プロトコルアップグレード |

**始め方：**
1. [オープンバウンティ](https://github.com/Scottcjn/rustchain-bounties/issues)を閲覧
2. [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)を選択（5-10 RTC）
3. フォーク、修正、PR — RTCで報酬を獲得
4. 詳細は[CONTRIBUTING.md](CONTRIBUTING.md)を参照

**1 RTC = $0.10 USD** | `pip install clawrtc`でマイニング開始

---

## エージェントウォレット + x402ペイメント

RustChainエージェントは**Coinbase Baseウォレット**を所有し、**x402プロトコル**（HTTP 402 Payment Required）を使用してマシンツーマシンの支払いができるようになりました：

| リソース | リンク |
|----------|------|
| **エージェントウォレットドキュメント** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base上のwRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC → wRTCスワップ** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Baseブリッジ** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# Coinbaseウォレットを作成
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# スワップ情報を確認
clawrtc wallet coinbase swap-info

# 既存のBaseアドレスをリンク
clawrtc wallet coinbase link 0xYourBaseAddress
```

**x402プレミアムAPIエンドポイント**が稼働中（現在はフローを検証するため無料）：
- `GET /api/premium/videos` - 一括動画エクスポート（BoTTube）
- `GET /api/premium/analytics/<agent>` - 詳細エージェント分析（BoTTube）
- `GET /api/premium/reputation` - 完全なレピュテーションエクスポート（Beacon Atlas）
- `GET /wallet/swap-info` - USDC/wRTCスワップガイダンス（RustChain）

## 📄 学術論文

| 論文 | DOI | トピック |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Proof of Antiquityコンセンサス、ハードウェアフィンガープリント |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | LLMアテンション向けAltiVec vec_perm（27-96倍の利点） |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | 行動分岐のためのPOWER8 mftbエントロピー |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 20%の動画拡散改善のための感情的プロンプト |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | LLM推論のためのNUMA分散ウェイトバンキング |

---

## 🎯 RustChainの違い

| 従来のPoW | Proof-of-Antiquity |
|----------------|-------------------|
| 最速のハードウェアに報酬 | 最も古いハードウェアに報酬 |
| 新しいほど良い | 古いほど良い |
| 無駄なエネルギー消費 | コンピューティング史の保存 |
| 底辺への競争 | デジタル保存への報酬 |

**核心原則**：数十年を生き延びた本物のヴィンテージハードウェアは、評価されるべきです。RustChainはマイニングの概念を逆転させました。

## ⚡ クイックスタート

### ワンライナーインストール（推奨）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

インストーラーは以下を実行：
- ✅ プラットフォームを自動検出（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ 分離されたPython仮想環境を作成（システムを汚染しない）
- ✅ ハードウェアに適したマイナーをダウンロード
- ✅ 起動時の自動開始を設定（systemd/launchd）
- ✅ 簡単なアンインストールを提供

### オプション付きインストール

**特定のウォレットを指定してインストール：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**アンインストール：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### サポートプラットフォーム
- ✅ Ubuntu 20.04+、Debian 11+、Fedora 38+（x86_64、ppc64le）
- ✅ macOS 12+（Intel、Apple Silicon、PowerPC）
- ✅ IBM POWER8システム

### トラブルシューティング

- **インストーラーが権限エラーで失敗する**：`~/.local`への書き込みアクセス権があるアカウントで再実行し、システムPythonのグローバルsite-packages内での実行を避けてください。
- **Pythonバージョンエラー**（`SyntaxError` / `ModuleNotFoundError`）：Python 3.10+でインストールし、`python3`をそのインタプリタに設定してください。
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **`curl`でのHTTPS証明書エラー**：非ブラウザクライアント環境で発生する可能性があります。ウォレットチェックの前に`curl -I https://rustchain.org`で接続性を確認してください。
- **マイナーが即座に終了する**：ウォレットが存在し、サービスが実行されていることを確認（`systemctl --user status rustchain-miner`または`launchctl list | grep rustchain`）

問題が続く場合、正確なエラー出力と`install-miner.sh --dry-run`の結果を含むOS詳細を新しいissueまたはバウンティコメントに投稿してください。

### インストール後

**ウォレット残高を確認：**
```bash
# 注意：ノードが自己署名SSL証明書を使用している可能性があるため、-skフラグを使用
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**アクティブなマイナーを一覧表示：**
```bash
curl -sk https://rustchain.org/api/miners
```

**ノードの健全性を確認：**
```bash
curl -sk https://rustchain.org/health
```

**現在のエポックを取得：**
```bash
curl -sk https://rustchain.org/epoch
```

**マイナーサービスを管理：**

*Linux（systemd）：*
```bash
systemctl --user status rustchain-miner    # ステータス確認
systemctl --user stop rustchain-miner      # マイニング停止
systemctl --user start rustchain-miner     # マイニング開始
journalctl --user -u rustchain-miner -f    # ログを表示
```

*macOS（launchd）：*
```bash
launchctl list | grep rustchain            # ステータス確認
launchctl stop com.rustchain.miner         # マイニング停止
launchctl start com.rustchain.miner        # マイニング開始
tail -f ~/.rustchain/miner.log             # ログを表示
```

### 手動インストール
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet YOUR_WALLET_NAME
# オプション：システムを変更せずにアクションをプレビュー
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

## 💰 バウンティボード

RustChainエコシステムへの貢献で**RTC**を獲得！

| バウンティ | 報酬 | リンク |
|--------|--------|------|
| **初の実コントリビューション** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **ネットワークステータスページ** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AIエージェントハンター** | 200 RTC | [エージェントバウンティ #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 Antiquity乗数

ハードウェアの年齢がマイニング報酬を決定します：

| ハードウェア | 時代 | 乗数 | 報酬例 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/エポック |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/エポック |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/エポック |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/エポック |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/エポック |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/エポック |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/エポック |
| **最新x86_64** | 現在 | **1.0×** | 0.12 RTC/エポック |

*乗数は永続的な利点を防ぐため、時間とともに減衰します（15%/年）。*

## 🔧 Proof-of-Antiquityの仕組み

### 1. ハードウェアフィンガープリント（RIP-PoA）

すべてのマイナーはハードウェアが本物で、エミュレートされていないことを証明する必要があります：

```
┌─────────────────────────────────────────────────────────────┐
│                   6つのハードウェアチェック                   │
├─────────────────────────────────────────────────────────────┤
│ 1. Clock-Skew & Oscillator Drift   ← シリコンの経年パターン  │
│ 2. Cache Timing Fingerprint        ← L1/L2/L3レイテンシ特性  │
│ 3. SIMD Unit Identity              ← AltiVec/SSE/NEONバイアス│
│ 4. Thermal Drift Entropy           ← 熱曲線は一意           │
│ 5. Instruction Path Jitter         ← マイクロアーキテクチャの│
│                                      ジッターマップ          │
│ 6. Anti-Emulation Checks           ← VM/エミュレータを検出   │
└─────────────────────────────────────────────────────────────┘
```

**なぜ重要か**：SheepShaver VMがG4 Macを装っても、これらのチェックに失敗します。本物のヴィンテージシリコンには偽造できない独自の経年パターンがあります。

### 2. 1 CPU = 1 Vote（RIP-200）

ハッシュパワー＝投票権となるPoWとは異なり、RustChainは**ラウンドロビンコンセンサス**を使用：

- 各一意のハードウェアデバイスはエポックごとに正確に1票を取得
- 報酬はすべての投票者に均等に分配され、その後antiquity乗数が適用
- 複数スレッドや高速CPUからの利点なし

### 3. エポックベースの報酬

```
エポック期間：10分（600秒）
基本報酬プール：1.5 RTC/エポック
分配：均等分割 × antiquity乗数
```

**5人のマイナーの例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
Modern PC (1.0×):  0.12 RTC  ████████
Modern PC (1.0×):  0.12 RTC  ████████
Modern PC (1.0×):  0.12 RTC  ████████
                   ─────────
合計：             0.90 RTC (+ 0.60 RTC はプールに返却)
```

## 🌐 ネットワークアーキテクチャ

### ライブノード（3アクティブ）

| ノード | ロケーション | 役割 | ステータス |
|------|----------|------|--------|
| **Node 1** | 50.28.86.131 | プライマリ + エクスプローラー | ✅ アクティブ |
| **Node 2** | 50.28.86.153 | Ergoアンカー | ✅ アクティブ |
| **Node 3** | 76.8.228.245 | 外部（コミュニティ） | ✅ アクティブ |

### Ergoブロックチェーンアンカリング

RustChainは不変性のためにErgoブロックチェーンに定期的にアンカーします：

```
RustChainエポック → コミットメントハッシュ → Ergoトランザクション（R4レジスタ）
```

これにより、RustChainの状態が特定時点で存在したことの暗号論的証明が提供されます。

## 📊 APIエンドポイント

```bash
# ネットワークの健全性を確認
curl -sk https://rustchain.org/health

# 現在のエポックを取得
curl -sk https://rustchain.org/epoch

# アクティブなマイナーを一覧表示
curl -sk https://rustchain.org/api/miners

# ウォレット残高を確認
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# ブロックエクスプローラー（Webブラウザ）
open https://rustchain.org/explorer
```

## 🖥️ サポートプラットフォーム

| プラットフォーム | アーキテクチャ | ステータス | 備考 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全サポート | Python 2.5互換マイナー |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全サポート | ヴィンテージMacに推奨 |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全サポート | 最高のパフォーマンス |
| **Ubuntu Linux** | x86_64 | ✅ 完全サポート | 標準マイナー |
| **macOS Sonoma** | Apple Silicon | ✅ 完全サポート | M1/M2/M3チップ |
| **Windows 10/11** | x86_64 | ✅ 完全サポート | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 実験的 | バッジ報酬のみ |

## 🏅 NFTバッジシステム

マイニングマイルストーンで記念バッジを獲得：

| バッジ | 要件 | レアリティ |
|-------|-------------|--------|
| 🔥 **Bondi G3 Flamekeeper** | PowerPC G3でマイニング | レア |
| ⚡ **QuickBasic Listener** | DOSマシンからマイニング | レジェンダリー |
| 🛠️ **DOS WiFi Alchemist** | DOSマシンをネットワーク化 | ミシック |
| 🏛️ **Pantheon Pioneer** | 初期100人のマイナー | リミテッド |

## 🔒 セキュリティモデル

### Anti-VM検出
VMは検出され、通常の報酬の**10億分の1**を受け取ります：
```
本物のG4 Mac:    2.5×乗数  = 0.30 RTC/エポック
エミュレートG4:  0.0000000025×    = 0.0000000003 RTC/エポック
```

### ハードウェアバインディング
各ハードウェアフィンガープリントは1つのウォレットにバインドされます。これにより以下を防止：
- 同一ハードウェアでの複数ウォレット
- ハードウェアスプーフィング
- Sybil攻撃

## 📁 リポジトリ構成

```
Rustchain/
├── install-miner.sh                # ユニバーサルマイナーインストーラー（Linux/macOS）
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # フルノード実装
│   └── fingerprint_checks.py       # ハードウェア検証
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Linuxマイナー
│   └── macos/rustchain_mac_miner_v2.4.py         # macOSマイナー
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技術ホワイトペーパー
│   └── chain_architecture.md       # アーキテクチャドキュメント
├── tools/
│   └── validator_core.py           # ブロック検証
└── nfts/                           # バッジ定義
```

## ✅ Beacon Certified Open Source（BCOS）

RustChainはAI支援PRを受け入れますが、メンテナーが低品質なコード生成に溺れないよう、*証拠*と*レビュー*を必要とします。

ドラフト仕様を読む：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 関連プロジェクト & リンク

| リソース | リンク |
|---------|------|
| **Webサイト** | [rustchain.org](https://rustchain.org) |
| **ブロックエクスプローラー** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **wRTCスワップ（Raydium）** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **ブリッジ RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTCトークンMint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI動画プラットフォーム |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AIソーシャルネットワーク |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8用NVIDIAドライバー |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8でのLLM推論 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | ヴィンテージMac用のモダンコンパイラ |

## 📝 記事

- [Proof of Antiquity: ヴィンテージハードウェアに報酬を与えるブロックチェーン](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [768GB IBM POWER8サーバーでLLMを実行](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 帰属

**1年の開発、本物のヴィンテージハードウェア、電気代、専用ラボがこれに費やされました。**

RustChainを使用する場合：
- ⭐ **このリポジトリにスター** - 他の人が見つけやすくなります
- 📝 **プロジェクトでクレジット** - 帰属を保持してください
- 🔗 **リンクバック** - 愛を共有しましょう

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 ライセンス

MITライセンス - 自由に使用できますが、著作権表示と帰属を保持してください。

---

<div align="center">

**[Elyan Labs](https://elyanlabs.ai)による ⚡ 製作**

*"あなたのヴィンテージハードウェアが報酬を獲得します。マイニングを再び有意義なものに。"*

**DOSボックス、PowerPC G4、Win95マシン - すべて価値があります。RustChainがそれを証明します。**

</div>

## マイニングステータス
<!-- rustchain-mining-badge-start -->
![RustChain Mining Status](https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/frozen-factorio-ryan&style=flat-square)<!-- rustchain-mining-badge-end -->

### ARM64（Raspberry Pi 4/5）クイック検証

```bash
pip install clawrtc
clawrtc mine --dry-run
```

期待される動作：6つすべてのハードウェアフィンガープリントチェックが、アーキテクチャフォールバックエラーなしでネイティブARM64で実行されます。
