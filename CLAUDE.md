# SakigakeAPP - プロジェクト設定

## 概要
病院業務支援アプリケーション群。シフト管理、給与分析、損益計算、診療報酬分析など。

## リポジトリ構成
- GitHub: git@github.com:sakigakelink/SakigakeAPP.git
- ブランチ: master
- ローカル: C:\Users\sakigake\SakigakeAPP\
- 本番サーバー（リモート）: C:\Users\Mining-Base\SakigakeAPP\（mining-base SSH経由）

## Python環境
- パス: `C:\Python314\python.exe`（ローカル・リモート共通）
- バージョン: Python 3.14.3
- 依存パッケージ: flask, flask-cors, ortools, pdfplumber, reportlab, openpyxl, pywebview, pythonnet, pytest

## 起動方法
- `SakigakeAPP.lnk` ダブルクリック → Flaskサーバー起動 + pywebviewウィンドウ表示
- デバッグ: `C:\Python314\python.exe portal\app.py`（コンソール表示）

## 開発フロー
1. ローカルでコード編集
2. デプロイ: `bash deploy.sh "変更内容"`（add → commit → push → リモート pull を一括実行）

## ポータル構成 (portal/)
- `portal/app.py` が統合エントリーポイント（Flask + pywebview を単一プロセスで実行）
- Flaskはバックグラウンドスレッド、pywebviewはメインスレッドで起動
- 各モジュール（シフト・給与・損益）はiframe経由で配信（`/legacy/shift/` 等）
- シフトのルートは Blueprint ではなく `register_routes(app, ..., portal_mode=True)` で app に直接登録
  - `portal_mode=True` 時、`/`・`/api/shutdown`・`/api/restart` はポータル側と衝突するためスキップ
- 給与・損益は `importlib.util.exec_module` で読み込み、プロキシルートで API を中継
- `SakigakeAPP.lnk` は環境固有（パスが異なる）のため git 管理外


## リモートサーバー (mining-base)
- MCP経由でアクセス: `mcp__mining-base__exec` ツールを使用
- Windows Server、PowerShellを使用
- コマンドの文字数制限あり（約1000文字）
- 日本語パスを扱う場合は PowerShell + UTF-8 エンコーディング設定が必要

## 注意事項
- シフトは通常ディレクトリ（サブモジュールではない）
- コード変更後は必ずテストを実行して確認すること
- リモートへの反映は `git pull` のみ（リモートで直接編集しない）
