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
2. デプロイ: `bash deploy.sh "変更内容のメモ"`（add → commit → push → リモート pull を一括実行）

## ポータル構成 (portal/)
- `portal/app.py` が統合エントリーポイント（Flask + pywebview を単一プロセスで実行）
- Flaskはバックグラウンドスレッド、pywebviewはメインスレッドで起動
- 各モジュール（シフト・給与・損益）はiframe経由で配信（`/legacy/shift/` 等）
- シフトのルートは Blueprint ではなく `register_routes(app, ..., portal_mode=True)` で app に直接登録
  - `portal_mode=True` 時、`/`・`/api/shutdown`・`/api/restart` はポータル側と衝突するためスキップ
- 給与・損益は `importlib.util.exec_module` で読み込み、プロキシルートで API を中継
- `SakigakeAPP.lnk` は環境固有（パスが異なる）のため git 管理外

## シフトデータの永続化
- フロントエンドは localStorage（`sakigakeData`）にデータ保存
- 変更のたびにサーバーバックアップ（`/api/backup`）へ自動同期（3秒デバウンス）
- localStorage が空の場合、サーバーバックアップから自動復元（pywebview は Chrome と別ストレージのため初回起動時に発動）

## シフト管理 (シフト/)
- Python + Flask Webアプリ
- OR-Tools CP-SAT ソルバーによるシフト自動生成
- solver.py が中核ファイル（約1600行）
- 依存パッケージ: `pip install -r シフト/requirements.txt`
- テスト: `cd シフト && python -m pytest test_validation.py`（101テスト）
- テスト: `cd シフト && python -m pytest test_shift_quality.py`（36テスト: 品質評価）
- テスト: `cd シフト && python -m pytest test_solver_boundary.py`（14テスト: ソルバー境界・診断）
- テスト: `cd シフト && python -m pytest test_regression.py`（全病棟の回帰テスト、実行に数分かかる）
- テストはローカル・リモートどちらでも実行可能

## リモートサーバー (mining-base)
- MCP経由でアクセス: `mcp__mining-base__exec` ツールを使用
- Windows Server、PowerShellを使用
- コマンドの文字数制限あり（約1000文字）
- 日本語パスを扱う場合は PowerShell + UTF-8 エンコーディング設定が必要

## ソルバー制約仕様（絶対遵守）

以下の制約は **ハード制約であり、いかなる理由があってもソフト制約化・緩和してはならない**:

1. **夜勤帯人数（準夜・深夜）**: `reqJunnya`, `reqShinya` で指定された人数を毎日厳守（`== adjusted_req`）。1名たりとも不足を許容しない
2. **初期配置（希望シフト + 前月末制約）**: ユーザーが入力した全ての指定（assign）・除外（avoid）はハード制約。前月末制約（night2→ake→off、junnya翌日制限）も同様。初期配置を無視する解を生成してはならない
3. **公休日数**: `monthlyOff` で指定された公休数を厳守（`== monthlyOff`）

> **有給（paid）は初期配置に含まない**。労基法上の権利行使であり概念的に異なる。ただしハード制約（希望日のみ配置）であることに変わりはない。

infeasible になった場合の対処:
- 上記制約の緩和は **禁止**
- 代わりに: 診断メッセージで原因を具体的に列挙し、ユーザーに設定変更を促す
- 日勤人数はソフト制約のまま可

## 注意事項
- シフトは通常ディレクトリ（サブモジュールではない）
- solver.py の forbidden_map パターン: 禁止シフトは変数作成時に共有 _false BoolVar にマッピング済み。workType別の `== 0` 制約は不要
- コード変更後は必ずテストを実行して確認すること
- リモートへの反映は `git pull` のみ（リモートで直接編集しない）
