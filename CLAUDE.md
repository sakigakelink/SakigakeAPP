# SakigakeAPP

Sakigake Hospital 管理業務支援システム。損益計算・診療報酬分析・給与分析・シフト管理の4機能を統合ポータルで提供する。

## 環境

- Python: `C:\Python314\python.exe`
  - ローカル・リモートとも同一パス
- リモートサーバー: `C:\Users\Mining-Base\SakigakeAPP\`
  - MCP `mcp__mining-base__exec` 経由で操作する
  - シェルは PowerShell
  - コマンド長は約1000文字が上限
- デプロイ: `bash .claude/deploy.sh "変更内容"`
  - 実行前にユーザーの確認を取ること
  - git add / commit / push / pull を個別に実行してはならない

## 開発フロー

1. アプリ変更時は必ずプランを立て、承認を得てから実装する
2. プランは入念に作成する。コードベース調査を徹底し、曖昧な点を残さない
3. 承認後は途中確認せず最後までやり遂げる。段階的テストは行う
4. コード変更後は必ずテストを実行する
5. 不要なファイル・コードを増やさない。既存パターンを再利用する

## リモート運用

- リモートへの反映は `git pull` のみ。リモート上で直接編集しない
- 秘匿データの同期は専用スクリプトを使う
  - リモート→ローカル: `bash .claude/sync-data.sh pull`
  - ローカル→リモート: `bash .claude/sync-data.sh push`
- PDF の更新・追加はリモートで行い、`sync-data.sh pull` でローカルに反映する

## 秘匿データ

`shared/` ディレクトリに集約。git管理しない。同期は `bash .claude/sync-data.sh pull|push` で行う。

```
shared/
  employees.json          — 職員マスタ
  bonus_contributions.json — 賞与データ
  給与/data/              — 給与キャッシュ
  給与/N月/               — 月別給与PDF
  損益/data/              — 試算表PDF・キャッシュ
  診療/N月/               — 診療帳票PDF・生成レポート
```

## ディレクトリ構成

- `portal/` — 統合ポータル。Flask + pywebview
- `シフト/` — シフト管理。通常ディレクトリとして管理する。サブモジュールではない
- `給与/` — 給与分析
- `損益/` — 損益計算
- `診療/` — 診療報酬分析
- `shared/` — 共通マスタデータ
