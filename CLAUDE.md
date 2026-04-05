# SakigakeAPP - プロジェクト設定

## 概要
Sakigake Hospital管理業務支援。損益計算、診療報酬分析、給与分析、シフト管理。

## 環境
- Python: `C:\Python314\python.exe`（ローカル・リモート共通）
- リモート: `C:\Users\Mining-Base\SakigakeAPP\`（MCP `mcp__mining-base__exec`、PowerShell、コマンド約1000文字制限）
- デプロイ: `bash .claude/deploy.sh "変更内容"`

## 注意事項
- アプリ変更時は必ずプランを立て、承認を得てから実装する
- プラン承認後は途中確認せず完遂すること（段階的テストは行う）
- デプロイは必ず deploy.sh を使う（個別 git 操作禁止）。実行前に確認を取ること
- コード変更後は必ずテストを実行して確認すること
- 不要なファイル・コードを増やさない（既存パターンを再利用）
- リモートへの反映は `git pull` のみ（リモートで直接編集しない）
- シフトは通常ディレクトリ（サブモジュールではない）
- 秘匿データ（`shared/employees.json`, `給与/data/`の給与CSV/JSON）はgit管理しない。デプロイ時はローカル・リモートにのみ保存
