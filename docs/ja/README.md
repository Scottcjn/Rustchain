# RustChain（日本語ガイド）

> 注意: この文書は RustChain の導入・運用向け日本語版ガイドです。詳細仕様は英語版 `README.md` と `docs/` 以下を優先してください。

## RustChain とは

RustChain は、軽量ノード運用・PoA/検証フロー・ツール群を含むオープンなチェーン運用プロジェクトです。  
このリポジトリには以下が含まれます。

- ノード/マイナー起動スクリプト
- 監視・可視化ダッシュボード
- API/プロトコル文書
- テスト・検証ツール

## クイックスタート

### 1) 前提条件

- Linux / macOS（Windows は WSL 推奨）
- Python 3.10+
- Git

### 2) リポジトリを取得

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

### 3) 依存関係をインストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

必要に応じて追加依存も導入します。

```bash
pip install -r requirements-node.txt
```

### 4) 最小動作確認

```bash
python tests/run_tests.py
```

または個別テスト:

```bash
pytest -q tests/test_api.py
```

## 主要ドキュメント

- `README.md` — 英語の総合ガイド（最新版）
- `INSTALL.md` — インストール手順
- `docs/API.md` — API リファレンス
- `docs/PROTOCOL.md` / `docs/PROTOCOL_v1.1.md` — プロトコル仕様
- `docs/WALLET_USER_GUIDE.md` — ウォレット利用ガイド
- `docs/FAQ_TROUBLESHOOTING.md` — よくある問題と対処

## マイナー/ノード運用メモ

- 長時間運用ではログローテーションを有効化
- systemd / supervisor などで自動再起動を設定
- バージョン更新時は `CHANGELOG` と `docs/` の仕様差分を確認

## セキュリティ注意事項

- 秘密鍵・シードをリポジトリへコミットしない
- `.env` に機密値を保存し、共有時はマスクする
- 外部公開ノードはファイアウォールとレート制限を設定

## 貢献方法

1. Fork を作成
2. ブランチを切って修正
3. テストを通す
4. PR を送る

例:

```bash
git checkout -b feat/docs-ja-translation
git add docs/ja/README.md
git commit -m "docs: add Japanese quickstart guide"
git push origin feat/docs-ja-translation
```

## 免責

この日本語版はコミュニティ翻訳です。実装挙動・最終仕様は英語版文書を基準にしてください。
