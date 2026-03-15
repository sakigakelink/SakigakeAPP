# SakigakeAPP - プロジェクト設定

## 概要
病院業務支援アプリケーション群。シフト管理、人件費、損益計算、診療報酬分析など。

## リポジトリ構成
- GitHub: git@github.com:sakigakelink/SakigakeAPP.git
- ブランチ: master
- ローカル: C:\Users\sakigake\SakigakeAPP\
- 本番サーバー（リモート）: C:\Users\Mining-Base\SakigakeAPP\（mining-base SSH経由）

## 開発フロー
1. ローカルでコード編集
2. `git add` → `git commit` → `git push origin master`
3. リモート（mining-base）で `git pull` → 本番反映

## シフト管理 (シフト管理/)
- Python + Flask Webアプリ
- OR-Tools CP-SAT ソルバーによるシフト自動生成
- solver.py が中核ファイル（約1600行）
- 依存パッケージ: `pip install -r シフト管理/requirements.txt`
- テスト: `cd シフト管理 && python -m pytest test_validation.py`（101テスト）
- テスト: `cd シフト管理 && python -m pytest test_shift_quality.py`（36テスト: 品質評価）
- テスト: `cd シフト管理 && python -m pytest test_solver_boundary.py`（14テスト: ソルバー境界・診断）
- テスト: `cd シフト管理 && python -m pytest test_regression.py`（全病棟の回帰テスト、実行に数分かかる）
- テストはローカル・リモートどちらでも実行可能

## リモートサーバー (mining-base)
- MCP経由でアクセス: `mcp__mining-base__exec` ツールを使用
- Windows Server、PowerShellを使用
- コマンドの文字数制限あり（約1000文字）
- 日本語パスを扱う場合は PowerShell + UTF-8 エンコーディング設定が必要

## 注意事項
- シフト管理は通常ディレクトリ（サブモジュールではない）
- solver.py の forbidden_map パターン: 禁止シフトは変数作成時に共有 _false BoolVar にマッピング済み。workType別の `== 0` 制約は不要
- コード変更後は必ずテストを実行して確認すること
- リモートへの反映は `git pull` のみ（リモートで直接編集しない）
