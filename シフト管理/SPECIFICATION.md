# Sakigake Shift 仕様書

最終更新: 2026-03-12

---

## 1. システム概要

病院向けシフト自動生成システム。OR-Tools CP-SATソルバーを使用して、複雑な制約条件を満たすシフトを自動生成する。

**v2.0変更**: カスケード制約緩和（L2-L5）廃止。厳密解法（L1）のみ実行。

### 動作環境
| 項目 | 内容 |
|------|------|
| Python | 3.14+ |
| Webフレームワーク | Flask + flask-cors |
| 制約ソルバー | OR-Tools CP-SAT |
| ブラウザ | Chrome / Edge 推奨 |
| アクセスURL | http://localhost:5000/ |
| CORSポリシー | localhost限定 |

### 起動方法
```
start.bat（デスクトップショートカット）
または
python app.py
```

---

## 2. 勤務形態

### 2.1 シフト種別
| コード | 名称 | 説明 |
|--------|------|------|
| day | 日勤 | 通常日勤 |
| late | 遅出 | 遅番勤務 |
| night2 | 夜勤 | 二交代夜勤（16時間） |
| junnya | 準夜 | 三交代準夜勤 |
| shinya | 深夜 | 三交代深夜勤 |
| ake | 明け | 夜勤明け（night2翌日に自動配置） |
| off | 公休 | 休日 |
| paid | 有給 | 有給休暇 |
| refresh | リフ休 | リフレッシュ休暇 |

### 2.2 勤務区分とシフト割当
| 区分コード | フロントend区分名 | 対象シフト |
|-----------|-----------------|-----------|
| twoShift | 2kohtai | day, late, night2, ake, off, paid, refresh |
| threeShift | 3kohtai | day, late, junnya, shinya, off, paid, refresh |
| dayOnly | day_only | day, off, paid, refresh |
| nightOnly | night_only | night2, ake, off, paid, refresh（夜勤専従） |
| flexRequest | fixed | パターン固定（ソルバー対象外） |

### 2.3 病棟別制限
| 病棟 | 遅出 | 備考 |
|------|------|------|
| 1病棟（ichiboutou） | 不可（reqLate=0, maxLate=0） | solver.pyで強制 |
| 2病棟（nibyoutou） | 可（reqLate=1, maxLate=4） | |
| 3病棟（sanbyoutou） | 不可（reqLate=0, maxLate=0） | solver.pyで強制 |

---

## 3. 制約条件

### 3.1 ハード制約（緩和不可・必須）

全制約はL1（厳密）のみで解決。緩和なし。

| 制約 | 説明 |
|------|------|
| 1日1シフト | 各職員は1日に1つのシフトのみ |
| 月間公休日数 | 2月=8日、5月=10日、その他=9日（年・月から自動算出） |
| 7連勤禁止 | 最大6日連続勤務まで（7日目は必ずoff/paid/refresh） |
| night2→ake強制 | 二交代: night2の翌日は必ずake |
| ake→off強制 | 二交代: akeの翌日は必ずoff |
| junnya翌日制限 | 三交代: junyaの翌日はjunyaまたはoff |
| 3連続夜勤禁止 | 三交代: junnya/shinyaは最大2連続まで（3連続禁止）。shinya→shinyaの2連続は許可 |
| maxNight上限 | 職員ごとの月間夜勤上限（employees.jsonで設定） |
| 前月引き継ぎ | 前月末シフト状態を月初の制約に反映 |
| 希望休厳守 | off/refresh/paid の assign 希望は全レベルでハード制約（緩和不可） |

### 3.2 前月引き継ぎ詳細
前月確定データから以下を自動取得してソルバーに渡す:
- 前月最終日のシフト（night2 → 当月1日はakeを強制）
- 前月末の連続勤務日数
- 前月末の連続休み日数

> maxNight は月単位でリセットされる（毎月独立して0から計算）。

### 3.3 ソフト制約（ペナルティ）

| 制約 | ペナルティ | 説明 |
|------|-----------|------|
| 人員不足 | 500点/人 | 必要人数未達 |
| 日深パターン | 25点/回 | day/late→shinya翌日（三交代専用。インターバル約7時間） |
| 夜勤間隔2日 | 30点/回 | 夜勤の間隔が2日以下 |
| 夜勤間隔3日 | 10点/回 | 夜勤の間隔が3日 |
| 深夜後非休 | 5〜20点/回 | 深夜翌日が休みでない |
| 散発夜勤 | 15点/回 | 深夜→休→深夜パターン |
| 5連勤 | 150点/件 | 5日連続勤務 |
| 6連勤 | 300点/件 | 6日連続勤務 |
| 夜勤偏り | 段階ペナルティ | 職員間夜勤回数の差 |
| 週末偏り | 30点/差 | 週末勤務回数の偏り |
| 遅出偏り | 20点/差 | 遅出回数の偏り |

### 3.4 ボーナス（ペナルティ減算）

三交代職員のみ対象。リフレッシュ取得日数に応じて −3〜−15点で変動。

| ボーナスパターン | 加算点 | 説明 |
|----------------|--------|------|
| shinya→休→junnya | −3〜−15点 | 深夜後に休んでから準夜（体内リズムに沿った逆回転） |
| shinya→junnya→休 | −3〜−15点 | 深夜→準夜と段階的にシフトダウン |

---

## 4. 人員配置要件

### 4.1 デフォルト設定（shared/ward_settings.json）
| 病棟 | reqDayWeekday | reqDayHoliday | reqJunnya | reqShinya | reqLate | maxLate |
|------|--------------|--------------|----------|----------|---------|---------|
| 1病棟 | 7 | 5 | 2 | 2 | 0 | 0 |
| 2病棟 | 7 | 5 | 2 | 2 | 1 | 4 |
| 3病棟 | 7 | 5 | 3 | 2 | 0 | 0 |

### 4.2 曜日調整
平日: reqDayWeekday、土日祝: reqDayHoliday を適用。

### 4.3 minNight自動計算
月間の夜勤必要総数 ÷ 対象職員数から最小夜勤回数を自動算出。職員のmaxNight上限も考慮。

---

## 5. ソルバー

### 5.1 ソルバー実行方式
3つのseed（7, 31, 97）で各15秒、計最大45秒。最良obj（最小値）を採用。
OPTIMALが出た時点で残りの試行はスキップ。

### 5.2 解法戦略（v2.0）
カスケード廃止。厳密解法（attempt_level=1）のみ実行。

```
厳密解法で実行 → optimal/feasible → 結果返却
                → infeasible/unknown → エラーメッセージ返却（緩和なし）
```

解が見つからない場合のメッセージ:
```
失敗: 解が見つかりません。職員数・公休日数・必要人数の設定を確認してください。[{debug_info}]
```

### 5.3 SSEストリーミング
`/solve-stream` エンドポイントはServer-Sent Events形式で進捗を送信:

| イベントtype | 説明 |
|-------------|------|
| attempt | 解法開始通知（厳密解法で開始） |
| log | ソルバーログメッセージ |
| result | 完了・結果データ |
| error | エラー通知 |

---

## 6. API仕様

### 6.1 シフト生成
```
POST /solve-stream
Content-Type: application/json
Response: text/event-stream (SSE)
```

リクエスト:
```json
{
  "year": 2026,
  "month": 3,
  "staff": [...],
  "wishes": [...],
  "config": {
    "ward": "2",
    "reqDayWeekday": 7,
    "reqDayHoliday": 5,
    "reqJunnya": 3,
    "reqShinya": 3,
    "monthlyOff": 9
  },
  "prevMonthData": {...},
  "fixedShifts": {...}
}
```

### 6.2 シフトデータ管理
```
GET  /api/shift/{ward}/{year}/{month}   シフト取得
POST /api/shift/save-draft              下書き保存
POST /api/shift/select-draft            下書き選択
POST /api/shift/delete-draft            下書き削除
POST /api/shift/confirm                 シフト確定
GET  /api/shift/prev-month              前月データ取得
GET  /api/shift/confirmed-month         確定済みデータ取得
```

### 6.3 実績管理
```
POST /api/shift/actual                  実績保存
POST /api/shift/finalize                実績確定（finalized状態へ）
```

### 6.4 職員管理
```
GET  /api/employees/all                 全職員取得
POST /api/staff/migrate                 職員データ移行（LocalStorage→サーバー）
```

### 6.5 病棟設定
```
GET  /api/ward-settings                 病棟設定取得
POST /api/ward-settings                 病棟設定更新
```

### 6.6 様式9
```
POST /api/yoshiki9/generate             様式9 Excel生成
GET  /api/yoshiki9/download/{filename}  Excel ダウンロード
```

### 6.7 バックアップ・システム
```
POST /api/backup                        バックアップ保存
GET  /api/backup/load                   バックアップ読込
POST /api/migrate/localstorage          LocalStorageデータ一括移行
GET  /health                            ヘルスチェック
POST /api/shutdown                      サーバー終了（localhost限定）
```

---

## 7. データ構造

### 7.1 職員データ（shared/employees.json）
```json
{
  "id": "10340440",
  "name": "田中　花子",
  "ward": "2",
  "shiftCategory": "twoShift",
  "type": "nurse",
  "maxNight": 4
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 職員ID（一意） |
| name | string | 氏名（全角スペース可） |
| ward | string | 所属病棟 "1"/"2"/"3" |
| shiftCategory | string | twoShift / threeShift / dayOnly / nightOnly / flexRequest |
| type | string | nurse / junkango / nurseaide |
| maxNight | number | 月間夜勤上限回数 |

### 7.2 希望データ
```json
{
  "staffId": "10340440",
  "type": "assign",
  "shift": "off",
  "days": [5, 12, 19]
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| staffId | string | 職員ID |
| type | string | assign（指定） / avoid（回避） |
| shift | string | シフト種別コード |
| days | number[] | 対象日リスト（1始まり） |

### 7.3 シフトファイル（shifts/{ward}/{year}-{month:02d}.json）
```json
{
  "year": 2026,
  "month": 3,
  "ward": "nibyoutou",
  "status": "confirmed",
  "selectedDraft": "確定版",
  "confirmedAt": "2026-03-01T10:00:00",
  "drafts": {
    "確定版": {
      "shifts": { "10340440": { "1": "day", "2": "night2", "3": "ake" } },
      "score": 85,
      "createdAt": "2026-03-01T09:30:00"
    }
  },
  "confirmed": {
    "shifts": { "10340440": { "1": "day", "2": "night2", "3": "ake" } },
    "dayHours": { "10340440-5": 3.0 }
  },
  "changeHistory": []
}
```

### 7.4 状態遷移
```
draft → confirmed → actual → finalized
```

| 状態 | 説明 |
|------|------|
| draft | 下書き（複数保持可能） |
| confirmed | 確定済みシフト |
| actual | 実績入力済み |
| finalized | 実績確定（様式9出力可） |

---

## 8. ファイル構成

```
シフト管理/
├── app.py                  # Flask初期化・起動
├── routes.py               # 全APIルート（2100行超）
├── solver.py               # CP-SATソルバー本体
├── validation.py           # 入力バリデーション
├── utils.py                # ユーティリティ（祝日・日付計算等）
├── yoshiki9.py             # 様式9 Excel生成（3200行）
├── import_kinmuhyo.py      # 看護勤務表Excel→JSON変換スクリプト
├── holidays.json           # 祝日データ
├── start.bat               # 起動バッチ
├── create_shortcut.vbs     # ショートカット作成スクリプト
├── SPECIFICATION.md        # 本仕様書
├── templates/
│   └── index.html          # メインUI（シングルページ）
├── static/
│   ├── css/style.css       # スタイルシート
│   └── js/app.js           # フロントエンドJS
├── shared/
│   ├── employees.json      # 職員マスタ
│   └── ward_settings.json  # 病棟別設定
├── shifts/                 # シフトデータ（月別JSON）
│   ├── ichiboutou/
│   ├── nibyoutou/
│   └── sanbyoutou/
├── backup/                 # 自動バックアップ
└── engines/                # 病棟別エンジン設定
    ├── base.py             # WardEngine基底クラス
    ├── ichiboutou/config.json
    ├── nibyoutou/config.json
    └── sanbyoutou/config.json
```

---

## 9. 自動機能

### 9.1 自動保存
シフト生成完了時に自動的にサーバーへ下書き保存。
命名規則: `自動_MMDD_HHMM`

### 9.2 自動バックアップ
シフト確定・更新操作時にbackup/フォルダへ自動バックアップ。

### 9.3 前月引き継ぎ
確定済み前月データから以下を取得してソルバーに渡す:
- 前月最終日シフト（night2 → 当月1日はake強制）
- 月末の連続勤務日数・連続休み日数

> maxNight は月単位でリセットされる（毎月独立して0から計算）。

---

## 10. 評価スコア

### スコア計算（0〜100点）
| カテゴリ | 配点 | 評価内容 |
|---------|------|---------|
| 夜勤負荷 | 25点 | 夜勤回数の偏り・間隔 |
| 連勤 | 20点 | 連続勤務日数 |
| リズム | 20点 | シフトパターンの規則性 |
| 週末 | 15点 | 週末勤務の公平性 |
| 希望反映 | 20点 | 希望の反映率 |

### 星評価
| スコア | 評価 |
|--------|------|
| 90〜100 | ★★★★★ |
| 80〜89 | ★★★★☆ |
| 70〜79 | ★★★☆☆ |
| 60〜69 | ★★☆☆☆ |
| 0〜59 | ★☆☆☆☆ |

---

## 11. セキュリティ

| 項目 | 内容 |
|------|------|
| CORS | localhost限定（flask-cors） |
| /api/shutdown | localhost IPのみ許可 |
| 入力バリデーション | 全APIエンドポイントで実施（validation.py） |
| 数値範囲チェック | year: 2020-2100、month: 1-12、ward: "1"/"2"/"3" |
| 文字列長制限 | staffName: 最大100文字 |
| XSS対策 | Flaskテンプレート自動エスケープ |
| パストラバーサル対策 | wardID・年月のホワイトリスト検証 |

---

## 12. ユーティリティスクリプト

### 12.1 看護勤務表取込（import_kinmuhyo.py）

看護勤務表Excel（.xlsx）からシフトアプリJSONを生成するCLIスクリプト。

```bash
python import_kinmuhyo.py --year 2026 --month 3
python import_kinmuhyo.py --year 2026 --month 3 --xlsx 看護勤務表3月.xlsx
python import_kinmuhyo.py --year 2026 --month 3 --staff-hours "10340440:3.0,99999999:5.0"
```

| 引数 | 必須 | 説明 |
|------|------|------|
| --year | ○ | 対象年（例: 2026） |
| --month | ○ | 対象月（例: 3） |
| --xlsx | − | Excelファイルパス（省略時: 看護勤務表{month}月.xlsx） |
| --staff-hours | − | スタッフ別dayHours（例: "ID:時間,ID:時間"） |

Excelシフト略称マッピング:
| Excel略称 | アプリコード | dayHours |
|----------|------------|---------|
| 日 | day | − |
| 夜 | night2 | − |
| 明 | ake | − |
| 休 | off | − |
| 深 | shinya | − |
| 準 | junnya | − |
| リ | refresh | − |
| 遅２ | late | − |
| AM | day | 3.0時間 |
| I | day | 7.0時間 |
| E | day | 5.0時間 |
| 12 | day | 3.0時間 |
| 15 | day | 6.0時間 |
| 病 | off | − |

出力先: `shifts/{ward}/{year}-{month:02d}.json`（status: "confirmed"）

---

## 13. 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-02-04 | v1.0 | 初版作成 |
| 2026-03-12 | v2.0 | カスケード制約緩和（L2-L5）廃止・厳密解法のみに変更 / 1病棟の遅出設定修正（reqLate=0, maxLate=0） / import_kinmuhyo.pyのハードコード除去（argparse対応） / /api/migrate/localstorageバリデーション追加 / Ollama LLM連携機能削除（未実装・未使用のため） / SPECIFICATION.md全面改訂 |
