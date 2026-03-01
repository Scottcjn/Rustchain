<div align="center">

# 🧱 RustChain：Proof-of-Antiquity ブロックチェーン

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

**古ければ古いほど報われる、初のブロックチェーン。**

*あなたの PowerPC G4 は、最新の Threadripper よりも多くの報酬を得ます。それが狙いです。*

[ウェブサイト](https://rustchain.org) • [ライブエクスプローラー](https://rustchain.org/explorer) • [wRTC スワップ](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC クイックスタート](docs/wrtc.md) • [wRTC チュートリアル](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia リファレンス](https://grokipedia.com/search?q=RustChain) • [ホワイトペーパー](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [クイックスタート](#-quick-start) • [仕組み](#-how-proof-of-antiquity-works)

</div>

---

## 🪙 Solana 上の wRTC

RustChain トークン（RTC）は、BoTTube ブリッジを介して Solana 上で **wRTC** として利用可能です：

| リソース | リンク |
|----------|------|
| **wRTC スワップ** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC ブリッジ** | [BoTTube ブリッジ](https://bottube.ai/bridge) |
| **クイックスタートガイド** | [wRTC クイックスタート（購入、ブリッジ、安全性）](docs/wrtc.md) |
| **オンボーディングチュートリアル** | [wRTC ブリッジ + スワップ安全性ガイド](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部リファレンス** | [Grokipedia 検索：RustChain](https://grokipedia.com/search?q=RustChain) |
| **トークンミント** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 貢献して RTC を獲得

あらゆる貢献が RTC トークンの報酬になります。バグ修正、機能実装、ドキュメント、セキュリティ監査 — すべて有料です。

| ティア | 報酬 | 例 |
|------|--------|----------|
| マイクロ | 1-10 RTC | タイポ修正、小さなドキュメント、シンプルなテスト |
| スタンダード | 20-50 RTC | 機能実装、リファクタリング、新しいエンドポイント |
| メジャー | 75-100 RTC | セキュリティ修正、コンセンサスの改善 |
| クリティカル | 100-150 RTC | 脆弱性パッチ、プロトコルアップグレード |

**始め方：**
1. [オープンバウンティ](https://github.com/Scottcjn/rustchain-bounties/issues) を閲覧
2. [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) を選択（5-10 RTC）
3. フォーク、修正、PR — RTC で報酬を受け取る
4. 詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照

**1 RTC = $0.10 USD** | `pip install clawrtc` でマイニング開始

---

## エージェントウォレット + x402 支払い

RustChain エージェントは **Coinbase Base ウォレット**を所有し、**x402 プロトコル**（HTTP 402 Payment Required）を使用して機械間支払いを行うことができます：

| リソース | リンク |
|----------|------|
| **エージェントウォレットドキュメント** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base 上の wRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC を wRTC にスワップ** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Base ブリッジ** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# Coinbase ウォレットを作成
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# スワップ情報を確認
clawrtc wallet coinbase swap-info

# 既存の Base アドレスをリンク
clawrtc wallet coinbase link 0xYourBaseAddress
```

**x402 プレミアム API エンドポイント**が稼働中（現在はフロー実証中につき無料）：
- `GET /api/premium/videos` - バルクビデオエクスポート（BoTTube）
- `GET /api/premium/analytics/<agent>` - 詳細エージェント分析（BoTTube）
- `GET /api/premium/reputation` - 完全な評判エクスポート（Beacon Atlas）
- `GET /wallet/swap-info` - USDC/wRTC スワップガイダンス（RustChain）

## 📄 学術論文

| 論文 | DOI | トピック |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Proof of Antiquity コンセンサス、ハードウェアフィンガープリント |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | LLM 注意機構のための AltiVec vec_perm（27-96 倍の優位性） |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | 行動的分岐のための POWER8 mftb エントロピー |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 動画拡散 20% 向上のための感情的プロンプティング |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | LLM 推論のための NUMA 分散ウェイトバンキング |

---

## 🎯 RustChain の違い

| 従来の PoW | Proof-of-Antiquity |
|----------------|-------------------|
| 最速のハードウェアに報酬 | 最古のハードウェアに報酬 |
| 新しいほど良い | 古いほど良い |
| エネルギーの浪費 | コンピューティング史の保存 |
| 底辺への競争 | デジタル保存への報酬 |

**コア原則**: 何十年も生き延びた本物のヴィンテージハードウェアは認識に値します。RustChain はマイニングを逆転させます。

## ⚡ クイックスタート

### ワンラインインストール（推奨）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

インストーラーの機能：
- ✅ プラットフォーム自動検出（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ 分離された Python 仮想環境を作成（システム汚染なし）
- ✅ ハードウェアに適切なマイナーをダウンロード
- ✅ 起動時の自動開始を設定（systemd/launchd）
- ✅ 簡単なアンインストールを提供

### オプション付きインストール

**特定のウォレットでインストール：**
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
- ✅ IBM POWER8 システム

### トラブルシューティング

- **インストーラーが権限エラーで失敗**: `~/.local` への書き込み権限を持つアカウントで再実行し、システム Python のグローバルサイトパッケージ内での実行を避けてください。
- **Python バージョンエラー**（`SyntaxError` / `ModuleNotFoundError`）: Python 3.10+ でインストールし、`python3` をそのインタープリターに設定してください。
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **`curl` での HTTPS 証明書エラー**: ブラウザ以外のクライアント環境で発生する可能性があります。ウォレットチェック前に `curl -I https://rustchain.org` で接続を確認してください。
- **マイナーが即座に終了**: ウォレットが存在し、サービスが実行されていることを確認してください（`systemctl --user status rustchain-miner` または `launchctl list | grep rustchain`）

問題が解決しない場合は、正確なエラー出力と `install-miner.sh --dry-run` の結果を添えて、新しい issue またはバウンティコメントにログと OS 詳細を含めてください。

### インストール後

**ウォレット残高を確認：**
```bash
# 注意：ノードが自己署名 SSL 証明書を使用する可能性があるため、-sk フラグを使用
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**アクティブなマイナーを一覧表示：**
```bash
curl -sk https://rustchain.org/api/miners
```

**ノードヘルスを確認：**
```bash
curl -sk https://rustchain.org/health
```

**現在のエポックを取得：**
```bash
curl -sk https://rustchain.org/epoch
```

**マイナーサービスを管理：**

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

### マニュアルインストール
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet YOUR_WALLET_NAME
# オプション：システムを変更せずにアクションをプレビュー
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

## 💰 バウンティボード

RustChain エコシステムへの貢献で **RTC** を獲得！

| バウンティ | 報酬 | リンク |
|--------|--------|------|
| **初の真の貢献** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **ネットワークステータスページ** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AI エージェントハンター** | 200 RTC | [エージェントバウンティ #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 古さによる倍率

ハードウェアの年代がマイニング報酬を決定します：

| ハードウェア | 時代 | 倍率 | 報酬例 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/エポック |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/エポック |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/エポック |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/エポック |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/エポック |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/エポック |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/エポック |
| **最新の x86_64** | 現在 | **1.0×** | 0.12 RTC/エポック |

*倍率は永続的な優位性を防ぐために時間とともに減衰します（年間 15%）。*

## 🔧 Proof-of-Antiquity の仕組み

### 1. ハードウェアフィンガープリント（RIP-PoA）

すべてのマイナーは、ハードウェアが本物でエミュレートされていないことを証明する必要があります：

```
┌─────────────────────────────────────────────────────────────┐
│                   6 つのハードウェアチェック                         │
├─────────────────────────────────────────────────────────────┤
│ 1. クロックスキューと発振器ドリフト   ← シリコンの経年パターン  │
│ 2. キャッシュタイミングフィンガープリント        ← L1/L2/L3 レイテンシトーン  │
│ 3. SIMD ユニット ID              ← AltiVec/SSE/NEON バイアス  │
│ 4. 熱ドリフトエントロピー           ← 熱曲線は固有  │
│ 5. 命令パスジッター         ← マイクロアーキテクチャジッターマップ   │
│ 6. 非エミュレーションチェック           ← VM/エミュレーター検出   │
└─────────────────────────────────────────────────────────────┘
```

**重要な理由**: G4 Mac のふりをする SheepShaver VM は、これらのチェックに失敗します。本物のヴィンテージシリコンには、偽造できない固有の経年パターンがあります。

### 2. 1 CPU = 1 票（RIP-200）

ハッシュパワー = 票の PoW とは異なり、RustChain は **ラウンドロビンコンセンサス** を使用します：

- 各固有のハードウェアデバイスは、エポックごとに正確に 1 票を得ます
- 報酬はすべての投票者で均等に分割され、その後古さによって乗算されます
- 複数のスレッドや高速 CPU を実行しても優位性はありません

### 3. エポックベースの報酬

```
エポック期間：10 分（600 秒）
基本報酬プール：エポックあたり 1.5 RTC
分配：均等分割 × 古さ倍率
```

**5 つのマイナーの例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
最新の PC (1.0×):  0.12 RTC  ████████
最新の PC (1.0×):  0.12 RTC  ████████
最新の PC (1.0×):  0.12 RTC  ████████
                   ─────────
合計：             0.90 RTC（+ 0.60 RTC がプールに戻る）
```

## 🌐 ネットワークアーキテクチャ

### ライブノード（3 つがアクティブ）

| ノード | 場所 | 役割 | ステータス |
|------|----------|------|--------|
| **ノード 1** | 50.28.86.131 | プライマリ + エクスプローラー | ✅ アクティブ |
| **ノード 2** | 50.28.86.153 | Ergo アンカー | ✅ アクティブ |
| **ノード 3** | 76.8.228.245 | 外部（コミュニティ） | ✅ アクティブ |

### Ergo ブロックチェーンアンカリング

RustChain は定期的に Ergo ブロックチェーンにアンカーし、不変性を提供します：

```
RustChain エポック → コミットメントハッシュ → Ergo トランザクション（R4 レジスター）
```

これにより、RustChain の状態が特定の時間に存在したことの暗号的証明が提供されます。

## 📊 API エンドポイント

```bash
# ネットワークヘルスを確認
curl -sk https://rustchain.org/health

# 現在のエポックを取得
curl -sk https://rustchain.org/epoch

# アクティブなマイナーを一覧表示
curl -sk https://rustchain.org/api/miners

# ウォレット残高を確認
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# ブロックエクスプローラー（ウェブブラウザ）
open https://rustchain.org/explorer
```

## 🖥️ サポートプラットフォーム

| プラットフォーム | アーキテクチャ | ステータス | 備考 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全サポート | Python 2.5 対応マイナー |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全サポート | ヴィンテージ Mac に推奨 |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全サポート | 最高のパフォーマンス |
| **Ubuntu Linux** | x86_64 | ✅ 完全サポート | スタンダードマイナー |
| **macOS Sonoma** | Apple Silicon | ✅ 完全サポート | M1/M2/M3 チップ |
| **Windows 10/11** | x86_64 | ✅ 完全サポート | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 実験的 | バッジ報酬のみ |

## 🏅 NFT バッジシステム

マイニングの節目で記念バッジを獲得：

| バッジ | 要件 | レアリティ |
|-------|-------------|--------|
| 🔥 **Bondi G3 Flamekeeper** | PowerPC G3 でマイニング | レア |
| ⚡ **QuickBasic Listener** | DOS マシンでマイニング | レジェンダリー |
| 🛠️ **DOS WiFi Alchemist** | DOS マシンをネットワーク接続 | ミシック |
| 🏛️ **Pantheon Pioneer** | 最初の 100 人のマイナー | 限定 |

## 🔒 セキュリティモデル

### 非 VM 検出
VM は検出され、通常報酬の **10 億分の 1** を受け取ります：
```
本物の G4 Mac:    2.5× 倍率  = 0.30 RTC/エポック
エミュレートされた G4:    0.0000000025×    = 0.0000000003 RTC/エポック
```

### ハードウェアバインディング
各ハードウェアフィンガープリントは 1 つのウォレットにバインドされます。以下を防止：
- 同じハードウェアでの複数のウォレット
- ハードウェアの偽装
- シビル攻撃

## 📁 リポジトリ構造

```
Rustchain/
├── install-miner.sh                # ユニバーサルマイナーインストーラー（Linux/macOS）
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # フルノード実装
│   └── fingerprint_checks.py       # ハードウェア検証
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Linux マイナー
│   └── macos/rustchain_mac_miner_v2.4.py         # macOS マイナー
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技術ホワイトペーパー
│   └── chain_architecture.md       # アーキテクチャドキュメント
├── tools/
│   └── validator_core.py           # ブロック検証
└── nfts/                           # バッジ定義
```

## ✅ Beacon Certified Open Source（BCOS）

RustChain は AI 支援 PR を受け入れますが、メンテナーが低品質なコード生成に溺れないように、*証拠* と *レビュー* を要求します。

ドラフト仕様を参照：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 関連プロジェクトとリンク

| リソース | リンク |
|---------|------|
| **ウェブサイト** | [rustchain.org](https://rustchain.org) |
| **ブロックエクスプローラー** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **wRTC スワップ（Raydium）** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **価格チャート** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC ブリッジ** | [BoTTube ブリッジ](https://bottube.ai/bridge) |
| **wRTC トークンミント** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI ビデオプラットフォーム |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI ソーシャルネットワーク |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8 用 NVIDIA ドライバー |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上での LLM 推論 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | ヴィンテージ Mac 用最新コンパイラー |

## 📝 記事

- [Proof of Antiquity: ヴィンテージハードウェアに報酬を与えるブロックチェーン](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [768GB IBM POWER8 サーバーで LLM を実行している](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 帰属

**1 年間の開発、実物のヴィンテージハードウェア、電気代、そして専用ラボが投入されました。**

RustChain を使用する場合は：
- ⭐ **このリポジトリをスター** — 他の人が見つけるのに役立ちます
- 📝 **プロジェクトでクレジット** — 帰属を保持してください
- 🔗 **リンクバック** — 愛を共有してください

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 ライセンス

MIT ライセンス — 自由に使用できますが、著作権表示と帰属を保持してください。

---

<div align="center">

**[Elyan Labs](https://elyanlabs.ai) によって ⚡ で作成**

*"あなたのヴィンテージハードウェアは報酬を得ます。マイニングを意味あるものに。"*

**DOS ボックス、PowerPC G4、Win95 マシン — それらすべてに価値があります。RustChain がそれを証明します。**

</div>

## マイニングステータス
<!-- rustchain-mining-badge-start -->
![RustChain マイニングステータス](https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/frozen-factorio-ryan&style=flat-square)<!-- rustchain-mining-badge-end -->

### ARM64（Raspberry Pi 4/5）クイック検証

```bash
pip install clawrtc
clawrtc mine --dry-run
```

期待される結果：すべての 6 つのハードウェアフィンガープリントチェックが、アーキテクチャフォールバックエラーなしでネイティブ ARM64 で実行されます。
