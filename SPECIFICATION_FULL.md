# SakigakeAPP 仕様書・開発手順書

## 1. プロジェクト概要

| 項目 | 内容 |
|------|------|
| 名称 | SakigakeAPP |
| 用途 | 精神科病院の業務支援アプリケーション群 |
| 対象業務 | シフト管理、給与分析、損益計算、診療報酬分析 |
| 技術基盤 | Python 3.14.3 + Flask（バックエンド）、Vanilla JS（フロントエンド） |
| データ管理 | JSON ファイルベース（DB不使用） |
| リポジトリ | `git@github.com:sakigakelink/SakigakeAPP.git`（master） |
| ローカル | `C:\Users\sakigake\SakigakeAPP\` |
| 本番サーバー | `C:\Users\Mining-Base\SakigakeAPP\`（mining-base SSH経由） |

### 統合ポータル対象モジュール

| モジュール | Blueprint | 説明 |
|------------|-----------|------|
| シフト管理 | /api/shift/* | OR-Tools CP-SAT ソルバーによる自動シフト生成 |
| 給与分析 | /api/salary/* | TKC PX2 PDF解析・可視化 |
| 損益計算 | /api/pnl/* | TKC月次合算試算表の損益分析 |
| 診療報酬 | /api/medical/* | 入院・薬剤レポート生成 |
| 勤怠変換 | iframe配信 | シフト管理サブメニュー内 |

### 独立ツール（統合対象外）

| ツール | 技術 | 配置 |
|--------|------|------|
| 処方入力 | React 19 + TypeScript + Vite | 独立ツール/処方/ |
| 書類チェック | JSON定義（将来AI連携） | 独立ツール/書類/ |
| 残業管理 | HTML単体ツール | 独立ツール/残業管理.html |

---

## 2. システム構成図

```
[ブラウザ] ──HTTP──> [統合ポータル app.py :5000]
                          |
                +---------+----------+---------+-----------+
                v         v          v         v           v
          [シフト管理]  [給与分析]  [損益計算]  [診療報酬]  [共通マスタAPI]
          Blueprint     Blueprint   Blueprint   Blueprint   /api/master/*
          /api/shift/*  /api/salary/* /api/pnl/* /api/medical/*
                |
          [OR-Tools CP-SAT ソルバー]
```

---

## 3. フォルダ構成

```
SakigakeAPP/
├── app.py                 <- 統合ポータル（Flask、port 5000）
├── portal.vbs             <- メイン起動（非表示+ブラウザ自動オープン）
├── deploy.sh              <- デプロイ（add->commit->push->remote pull）
├── CLAUDE.md              <- Claude Code 設定（自動読込）
├── SPECIFICATION_FULL.md  <- 本仕様書
├── .gitignore
│
├── shared/                <- 組織共有マスタ
│   └── employees.json     職員マスタ（55名+）
│
├── portal/                <- ポータルUI
│   ├── templates/
│   │   ├── base.html          基本レイアウト（サイドバー+SVGアイコン）
│   │   ├── dashboard.html     ダッシュボード（4カード）
│   │   ├── iframe_wrapper.html iframe配信
│   │   ├── reports.html       診療報酬ビューア
│   │   └── 勤怠変換.html      勤怠変換ツール
│   └── static/
│       ├── css/design-system.css  統一デザインシステム
│       ├── css/portal.css         ポータル固有スタイル
│       └── js/portal.js
│
├── シフト/                <- シフト管理（中核モジュール）
│   ├── solver.py          CP-SAT ソルバー
│   ├── routes.py          REST API 全27エンドポイント
│   ├── app.py             スタンドアロン起動用
│   ├── validation.py      入力バリデーション
│   ├── shift_quality.py   品質評価
│   ├── solver_subprocess.py  サブプロセス分離
│   ├── generate_pdf.py    PDF出力
│   ├── import_kinmuhyo.py 勤務表取込
│   ├── yoshiki9.py        様式9変換
│   ├── utils.py           祝日判定
│   ├── engines/           病棟別エンジン
│   │   ├── base.py        基底クラス WardEngine
│   │   ├── ichiboutou/    1病棟(config.json + solver.py)
│   │   ├── nibyoutou/     2病棟
│   │   └── sanbyoutou/    3病棟
│   ├── shared/            共有データ
│   ├── shifts/            月別シフトデータ
│   ├── backup/            自動バックアップ
│   ├── templates/index.html SPA
│   ├── static/js/         フロントエンド13モジュール
│   ├── static/css/        style.css（ダークテーマ）
│   └── test_*.py          テスト8ファイル
│
├── 給与/                  <- 給与分析
│   ├── app.py             Flask + pdfplumber
│   ├── dept_codes.json    部課コード
│   ├── import_sheets.py   シート取込
│   ├── templates/index.html
│   └── data/              月次PDFフォルダ
│
├── 損益/                  <- 損益計算
│   ├── app.py             Flask + pdfplumber + pandas
│   ├── templates/index.html
│   ├── data/              PDF + TXT元データ
│   └── output/            生成レポート
│
├── 診療/                  <- 診療報酬分析
│   ├── inpatient_report.py    入院レポート生成
│   ├── pharmacy_report.py     薬剤レポート生成
│   ├── extract_drug_list.py   薬剤リスト抽出
│   ├── inpatient-report.bat   入院レポート実行
│   ├── pharmacy-report.bat    薬剤レポート実行
│   ├── scripts/               月別抽出スクリプト
│   └── 1月/, 2月/             月次データ＋HTMLサマリー出力
│
└── 独立ツール/            <- 統合対象外
    ├── 処方/              React 19 + TypeScript SPA
    │   └── start.bat      処方ツール起動（localhost:5173）
    ├── 書類/              精神保健法書類チェック基準JSON
    └── 残業管理.html      残業管理ツール
```

---

## 4. 各モジュール詳細仕様

### 4.1 統合ポータル（app.py + portal/）

| 項目 | 内容 |
|------|------|
| ポート | 5000 |
| フレームワーク | Flask + Blueprint |
| 最大アップロード | 50MB |
| デザインシステム | design-system.css（統一ダークテーマ） |

**ルーティング:**

| パス | 機能 |
|------|------|
| `/` | ダッシュボード（カード型メニュー） |
| `/<page>` | iframe_wrapper（shift, salary, pnl, data） |
| `/reports` | 診療報酬ビューア（月別HTMLサマリー閲覧） |
| `/legacy/shift/` | シフトUI配信 |
| `/legacy/salary/` | 給与UI配信 |
| `/legacy/pnl/` | 損益UI配信 |
| `/legacy/data/kintai` | 勤怠変換ツール配信 |
| `/api/reports/months` | 診療報酬 利用可能月一覧 |
| `/api/reports/<月>/<ファイル名>` | 診療報酬 HTMLサマリー配信 |
| `/api/master/employees` | 職員マスタJSON |
| `/api/master/dept-codes` | 部課コードJSON |

---

### 4.2 シフト管理（シフト/）

**概要**: OR-Tools CP-SAT ソルバーによる自動シフト生成。3病棟対応。

**対象病棟:**
| 病棟 | コード | 分類 |
|------|--------|------|
| 1病棟 | ichiboutou | 精神療養 |
| 2病棟 | nibyoutou | 15:1 |
| 3病棟 | sanbyoutou | 15:1 |

**シフト種別:**
| コード | 名称 | 説明 |
|--------|------|------|
| day | 日勤 | 通常日勤 |
| late | 遅番 | 遅出日勤 |
| night2 | 夜勤(2交代) | 16時間夜勤 |
| junnya | 準夜 | 準夜勤(3交代) |
| shinya | 深夜 | 深夜勤(3交代) |
| off | 公休 | 休日 |
| paid | 有給 | 有給休暇 |
| ake | 明け | 夜勤明け休 |
| refresh | リフレッシュ | リフレッシュ休暇 |

**勤務体系 (workType):**
| タイプ | 対象シフト |
|--------|------------|
| 2kohtai | day/late + night2/ake |
| 3kohtai | day + junnya + shinya |
| day_only | 日勤のみ |
| night_only | 夜勤のみ |
| fixed | 固定配置（ソルバー対象外） |
| flexRequest | 手動入力のみ |

**ハード制約（絶対緩和禁止）:**
1. **夜勤帯人数**: reqJunnya / reqShinya を毎日厳守
2. **初期配置**: assign / avoid 全てハード制約。前月末制約も同様
3. **公休日数**: monthlyOff を厳守
4. **有給**: 指定日へのハード配置

**ソフト制約（目的関数で最適化）:**
夜勤公平性、連続勤務制限、夜勤間隔、深夜→休み優先、準夜/深夜の分散、希望シフト反映度、日勤人数

**API エンドポイント（全27本）:**

| カテゴリ | メソッド | パス | 機能 |
|----------|----------|------|------|
| ソルバー | POST | /solve | 同期シフト生成 |
| | POST | /solve-stream | ストリーミング生成 |
| シフト | GET | /\<ward>/\<year>/\<month> | シフト読込 |
| | POST | /save-draft | 下書き保存 |
| | POST | /select-draft | 下書き選択 |
| | POST | /confirm | シフト確定 |
| | POST | /modify | セル手動変更 |
| | POST | /delete-draft | 下書き削除 |
| | GET | /prev-month | 前月データ |
| | GET | /confirmed-month | 確定データ |
| 職員 | GET | /staff/\<ward> | 病棟別職員 |
| | POST | /staff/migrate | データ移行 |
| | POST | /staff/transfer | 病棟間異動 |
| | GET | /employees/all | 全職員マスタ |
| バックアップ | POST | /backup | 保存 |
| | GET | /backup/load | 読込 |
| | GET | /backup/list | 一覧 |
| エクスポート | POST | /export_json | JSON出力 |
| | POST | /export_pdf | PDF出力 |
| 設定 | GET/POST | /settings/ward | 病棟設定 |
| その他 | GET | /wards | 病棟一覧 |
| | GET | /holidays | 祝日一覧 |
| | POST | /carry-over | 月跨ぎ計算 |
| | GET | /health | ヘルスチェック |

**テストスイート:**

| ファイル | テスト数 | 内容 |
|----------|----------|------|
| test_validation.py | 101 | 入力バリデーション |
| test_shift_quality.py | 36 | 品質評価メトリクス |
| test_solver_boundary.py | 14 | ソルバー境界条件・診断 |
| test_regression.py | 全病棟 | 回帰テスト（数分） |

---

### 4.3 給与分析（給与/）

| 項目 | 内容 |
|------|------|
| 目的 | TKC PX2 一人別給与統計表 PDF解析・可視化 |
| 依存 | flask, flask-cors, pdfplumber |

**機能:** PDF解析、フォルダ一括解析、月次トレンド、職員カテゴリ別集計、部課コード部門マッピング

---

### 4.4 損益計算（損益/）

| 項目 | 内容 |
|------|------|
| 目的 | TKC月次合算試算表の解析・損益計算 |
| 依存 | flask, pdfplumber, pandas, openpyxl |

**機能:** PDF/TXT解析、収入・費用項目分析、退職金計算、日当たり収益計算、手動入力対応

---

### 4.5 診療報酬分析（診療/）

| 項目 | 内容 |
|------|------|
| 目的 | 入院・薬剤の月次レポート生成 |
| 現状 | バッチ処理（bat起動、Excel出力） |

**入院レポート:** 病棟別入院収益分析、専門サービス算定分析、基準月比較、Excel出力
**薬剤レポート:** 薬効分類別処方分析、前月比較、4シートExcel出力

---

## 5. 起動方法

| ファイル | 動作 |
|------|------|
| `portal.vbs` | メイン起動（非表示+ブラウザ自動オープン http://localhost:5000/） |
| `独立ツール/処方/start.bat` | 処方ツール（localhost:5173） |
| `診療/inpatient-report.bat` | 入院レポート生成 |
| `診療/pharmacy-report.bat` | 薬剤レポート生成 |

デバッグ起動: `C:\Python314\python.exe app.py`（コンソール表示）

---

## 6. デプロイ・開発フロー

### デプロイ

```bash
bash deploy.sh "変更内容のメモ"
# [1] git add -A
# [2] git commit -m "メッセージ"
# [3] git push origin master
# [4] ssh mining-base -> git pull origin master
```

### テスト実行

```bash
cd シフト
python -m pytest test_validation.py        # 101テスト
python -m pytest test_shift_quality.py     # 36テスト
python -m pytest test_solver_boundary.py   # 14テスト
python -m pytest test_regression.py        # 全病棟回帰（数分）
```

### Claude Code での指示の出し方

**コード修正:**
```
SakigakeAPP の〇〇を修正してください。
テスト実行 -> コミット -> プッシュ -> リモート反映 まで行ってください。
```

**動作確認:**
```
mining-base でシフトのテストを実行してください。
```

**トラブル時:**
```
コンフリクトを解消してください。
失敗したテストの内容を教えてください。修正してからやり直してください。
```

---

## 7. 環境情報

| 項目 | 値 |
|---|---|
| Python | `C:\Python314\python.exe` (3.14.3) |
| ローカルPC | Windows 11 |
| 本番サーバー | mining-base (SSH / MCP `mcp__mining-base__exec`) |
| リポジトリ | GitHub sakigakelink/SakigakeAPP (master) |
| デザインシステム | design-system.css（統一ダークテーマ、Inter + Noto Sans JP） |

### 依存パッケージ

**Python:**
flask, flask-cors, ortools, pdfplumber, pandas, openpyxl, reportlab, pytest

**Node.js（処方ツール）:**
react 19, typescript 5.9, vite

---

## 8. リモートサーバー（mining-base）

| 項目 | 内容 |
|------|------|
| OS | Windows Server（PowerShell） |
| パス | `C:\Users\Mining-Base\SakigakeAPP\` |
| アクセス | SSH経由（MCP `mcp__mining-base__exec`） |
| コマンド文字数制限 | 約1,000文字 |
| 注意 | 日本語パスはPowerShell + UTF-8エンコーディング必要 |
| ルール | リモートで直接編集しない。必ずローカル編集 -> git経由で反映 |
