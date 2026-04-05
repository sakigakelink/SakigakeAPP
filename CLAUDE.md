# SakigakeAPP

Sakigake Hospital 管理業務支援システム。

## 環境

- Python: `C:\Python314\python.exe`
- 依存パッケージ: `pip install flask flask-cors pywebview pdfplumber ortools`
- 起動: `python portal/app.py`
- リモート: `C:\Users\Mining-Base\SakigakeAPP\`
  - MCP `mcp__mining-base__exec` 経由。PowerShell。コマンド長は約1000文字が上限
  - リモートへの反映は `git pull` のみ。直接編集しない
- デプロイ: `bash .claude/deploy.sh "変更内容"`。実行前に確認を取ること
  - git add / commit / push / pull を個別に実行してはならない
- 秘匿データは `shared/` に集約。git管理しない
  - 同期: `bash .claude/sync-data.sh pull` / `push`
  - PDFの追加・更新はリモートで行い `pull` でローカルに反映する

## 開発フロー

### プラン

アプリ変更時は必ずプランを立てる。

1. コードベースを調査し、影響範囲・既存パターン・再利用可能な実装を把握する
2. 具体的な変更手順を設計する。対象ファイル、変更内容、テスト方針を明記する
3. 曖昧な点があればプラン段階で質問して解消する。実装中に質問しない
4. プランをユーザーに提示し、承認を得る

### 実装

承認後は途中確認せず最後までやり遂げる。

1. プランに従ってコードを変更する
2. 各ステップでテストを実行し、変更が正しいことを確認する
3. 全ての変更が完了したら最終テストを実行する
4. 問題がなければ完了を報告する。問題があれば自力で解決する

### 原則

- 不要なファイル・コードを増やさない。既存パターンを再利用する
- 括弧書きで補足しない。言いたいことは直接記述する
- テストは必ず実行する。テストなしでの完了報告は禁止
