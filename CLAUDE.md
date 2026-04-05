# SakigakeAPP - プロジェクト設定

## 概要
Sakigake Hospital管理業務支援。損益計算、診療報酬分析、給与分析、シフト管理。

## 環境
- Python: `C:\Python314\python.exe`（ローカル・リモート共通）
- リモート: `C:\Users\Mining-Base\SakigakeAPP\`（mining-base SSH経由）
- デバッグ起動: `C:\Python314\python.exe portal\app.py`

## 開発フロー
- デプロイ: `bash deploy.sh "変更内容"`（add → commit → push → リモート pull を一括実行）

## ポータル構成 (portal/)
- `portal/app.py` が統合エントリーポイント（Flask + pywebview を単一プロセスで実行）
- Flaskはバックグラウンドスレッド、pywebviewはメインスレッドで起動
- 各モジュールのビジネスロジックは `*_logic.py` に分離し、ポータルから直接import
  - 給与: `salary_logic.py`、損益: `pnl_logic.py`
- シフト・給与・損益はiframe経由で配信（`/legacy/shift/` 等）
- 診療はAPI経由で配信（`/api/reports/months` 等）
- シフトは `register_routes(app, ..., portal_mode=True)` で app に直接登録
  - `portal_mode=True` 時、`/`・`/api/shutdown`・`/api/restart` はスキップ


## リモートサーバー (mining-base)
- MCP経由でアクセス: `mcp__mining-base__exec` ツールを使用
- Windows Server、PowerShellを使用
- コマンドの文字数制限あり（約1000文字）
- 日本語パスを扱う場合は PowerShell + UTF-8 エンコーディング設定が必要

## 注意事項
- シフトは通常ディレクトリ（サブモジュールではない）
- コード変更後は必ずテストを実行して確認すること
- リモートへの反映は `git pull` のみ（リモートで直接編集しない）
