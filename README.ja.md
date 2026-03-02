# 🧱 RustChain：古代証明ブロックチェーン

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

**古さを速さではなく報酬する、世界初のブロックチェーン。**

*あなたのPowerPC G4は最新のThreadripperよりも多く稼げます。それが趣旨です。*

[ウェブサイト](https://rustchain.org) • [エクスプローラー](https://rustchain.org/explorer) • [wRTCを交換](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTCクイックスタート](docs/wrtc.md) • [wRTCチュートリアル](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia参照](https://grokipedia.com/search?q=RustChain) • [ホワイトペーパー](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [クイックスタート](#-クイックスタート) • [仕組み](#-古代証明の仕組み)

---

## クイックスタート

### インストール（推奨）

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

このインストーラーは以下を行います：
- ✅ プラットフォームを自動検出（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ Python仮想環境を作成（システム環境を汚染しません）
- ✅ ハードウェアに適したマイナーをダウンロード
- ✅ 自動起動を設定（systemd/launchd）
- ✅ アンインストールも簡単

### 対応プラットフォーム
- ✅ Ubuntu 20.04+、Debian 11+、Fedora 38+（x86_64、ppc64le）
- ✅ macOS 12+（Intel、Apple Silicon、PowerPC）
- ✅ IBM POWER8システム

### トラブルシューティング

- **権限エラー**：書き込み権限のあるアカウントで再実行してください
- **Pythonバージョンエラー**：Python 3.10以上を使用してください
- **マイナーが終了する場合**：ウォレットが存在し、サービスが起動していることを確認してください

### インストール後

**ウォレット残高を確認：**
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**アクティブマイナーを表示：**
```bash
curl -sk https://rustchain.org/api/miners
```

---

## 特徴

| 従来のPoW | 古代証明 |
|----------|----------|
| 最も速いハードウェアを報酬 | 最も古いハードウェアを報酬 |
| 新，旧会更好 | 旧い更好 |
| エネルギーを浪費 | 計算機の歴史を保存 |

**コアアイデア**：何十年も生き延びた真正なヴィンテージハードウェアは評価に値します。RustChainはマイニングを根本から変えます。

---

## 報酬

**ハードウェアの古さによってマイニング報酬が決まります：**

| ハードウェア | 時代 | マルチプライヤー |
|-------------|------|-----------------|
| **PowerPC G4** | 1999-2005 | **2.5×** |
| **PowerPC G5** | 2003-2006 | **2.0×** |
| **PowerPC G3** | 1997-2003 | **1.8×** |
| **IBM POWER8** | 2014 | **1.5×** |

---

## 報酬プログラム

バグ修正、機能、翻訳、セキュリティ監査など、すべてのコントリビューションに対してRTCトークンを報酬としてお支払いします。

| 種類 | 報酬 | 例 |
|------|------|-----|
| マイクロ | 1-10 RTC | タイポ修正、小さなドキュメント |
| 標準 | 20-50 RTC | 機能追加、リファクタリング |
| 大規模 | 75-100 RTC | セキュリティ修正、コンセンサス改善 |
| 重要 | 100-150 RTC | 脆弱性修正、プロトコルアップグレード |

**参加方法：**
1. [オープンバウンティ](https://github.com/Scottcjn/rustchain-bounties/issues)を閲覧
2. [初心者向けissue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)を選択
3. Forkして修正、PRを作成 - RTCで報酬獲得

---

## 謝辞

1年間の開発、本当のヴィンテージハードウェア、電気代、そしてドイツのラボがこのプロジェクトにあります。

このレポジトリを使用する場合は：
- ⭐ **スター付け** - 他の人が見つけるのに役立ちます
- 📝 **プロジェクトでクレジット** - アトリビューションを維持
- 🔗 **リンク戻し** - 愛を共有

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## ライセンス

MITライセンス - 自由に使用可能ですが、著作権表示とアトリビューションを維持してください。

---

<div align="center">

**Elyan Labs ⚡ 作**

*"あなたのヴィンテージハードウェアに報酬を。マイニングをもう一度意味のあるものに。"*

</div>
