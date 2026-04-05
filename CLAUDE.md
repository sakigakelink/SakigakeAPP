# SakigakeAPP

Sakigake Hospital 管理業務支援システム。

## モジュール

| モジュール | ディレクトリ | ポート | 備考 |
|-----------|------------|--------|------|
| ポータル | `portal/` | 5000 | 全モジュールを単一Flaskプロセスに統合 |
| シフト | `シフト/` | 5000 | OR-Tools制約ソルバー。`engines/`に病棟別エンジン |
| 損益 | `損益/` | 5002 | TKC月次PDF解析 |
| 給与 | `給与/` | 5001 | 給与明細PDF解析 |
| 診療 | `診療/` | — | CLIバッチ。portalからsubprocess実行 |

## 環境

- Python: `C:\Python314\python.exe`
- 依存: `pip install flask flask-cors pywebview pdfplumber ortools`
- 起動: `python portal/app.py`
- テスト: `python -m pytest シフト/ 損益/ 給与/ -v`

## デプロイ・データ同期

- デプロイ: `bash .claude/deploy.sh "変更内容"`。実行前に確認を取ること
  - git add / commit / push / pull を個別に実行してはならない
- リモート: `C:\Users\Mining-Base\SakigakeAPP\`
  - MCP `mcp__mining-base__exec` 経由。PowerShell。コマンド長は約1000文字が上限
  - リモートへの反映は `git pull` のみ。直接編集しない
- 秘匿データは `shared/` に集約。git管理しない
  - 同期: `bash .claude/sync-data.sh pull` / `push`
  - PDFの追加・更新はリモートで行い `pull` でローカルに反映する

## コーディング規約

### JSON書き込みは一時ファイル経由で安全に行う

手順: 一時ファイルに書く → `fsync`でディスクに確定 → `os.replace`で本来のファイルと置き換える。直接`open()`で上書きするとクラッシュ時にファイルが壊れる。既存実装を再利用すること: `cache_utils.save_cache()`, `portal/app.py:_atomic_json_write()`, `シフト/routes.py:atomic_json_write()`。

### キャッシュはmtimeベース

`cache_utils.py`がソースファイルのmtimeマップを保持し差分検知する。独自のキャッシュ判定を作ると、古いデータを返したりPDFを毎回再解析する問題が起きる。PDF→JSON変換を伴うモジュールは全てこのパターンに従う。

### バリデーションエラーは ValidationError

`シフト/validation.py`の`ValidationError(message, field)`をルートハンドラで使う。独自の例外クラスを作るとフロントエンドのエラー表示が壊れる。

### フロントエンドはES Modules + vanilla JS

フレームワークは使わない。シフトモジュールは`static/js/`にモジュール分割済み。状態は`state.js`の`D`オブジェクトに集約し、`localStorage`即時保存 + 3秒デバウンスでサーバーバックアップ。

### ファイルエンコーディングはUTF-8

全モジュール共通。例外: `損益/pnl_logic.py`のみTKCテキストファイル読み込み時にCP932/Shift_JIS/EUC_JPへのフォールバックあり。他モジュールでは非UTF-8ファイルを渡すとクラッシュする。

## 踏みやすい地雷

### portal_mode

シフトモジュールはportal統合時に`portal_mode=True`で登録される。`/api/shutdown`, `/api/restart`, `/`が無効化される。これらのルートをポータル内で追加するとルート競合でエラーになる。

### shared/へのパス解決

全モジュールが`os.path.dirname(os.path.abspath(__file__))`から親を辿ってプロジェクトルートを得る。cwdには依存しない。`os.getcwd()`や相対パスで`shared/`を参照すると、実行場所によってファイルが見つからなくなる。

### importlibによるモジュール読み込み

`portal/app.py`は`給与/salary_logic.py`と`損益/pnl_logic.py`を`importlib.util.spec_from_file_location()`で読む。通常のimport文ではないため、モジュールのファイル名やパスを変更するとポータルが起動しなくなる。

### 従業員マスタは共有資源

`shared/employees.json`が唯一のマスタ。全モジュールが参照する。構造を変えると全モジュールに影響が波及する。シフトモジュールはリクエスト毎に読み直すため、キャッシュの心配は不要。

### 診療モジュールのsubprocess実行

`portal/app.py`が`pharmacy_report.py`と`inpatient_report.py`をsubprocess.runで呼ぶ。`cwd=shinryo_code_dir`設定済み。引数は月フォルダ名のみ。タイムアウト: 薬剤120秒、入院180秒。引数の形式を変えるとポータル側の呼び出しも修正が必要。

### PDF解析の列数変動

pdfplumberのテーブル抽出は列数が安定しない。`診療/pharmacy_report.py`は`len(row) >= 11`, `>= 10`, それ以外の3段階でフォールバックする。列数チェックなしで`row[N]`にアクセスするとIndexErrorでレポート生成が止まる。

## 開発フロー

**以下に該当する作業は、必ずプランを立ててから実装する。**

- 新しい機能の追加
- 既存機能の動作や計算結果を変える修正
- 2ファイル以上にまたがる変更
- APIエンドポイントの追加・変更・削除
- JSONフォーマットやデータ構造の変更
- `shared/employees.json`の構造変更。全モジュールに影響する
- 診療subprocessの引数・タイムアウト変更
- キャッシュの判定ロジック変更

**プラン不要の作業:** 表示テキストの修正、ログ追加、コメント修正、画面の見た目だけの調整、既存テストの修正

### プラン

コードを書く前に、以下を全て済ませる。

1. コードベースを調査する。影響するファイル、呼び出し元、既存の類似実装を特定する
2. 変更内容を以下の形式で書く
   - 何をするか: ユーザーから見た変化を1〜2文で
   - 変更ファイル: ファイル名と変更の要点を箇条書きで
   - テスト: 何を実行して何が通れば正しいか
3. 不明点は全てここで質問する。実装フェーズでの質問は禁止
4. ユーザーの承認を得る

### 実装

**承認後は完了報告まで止まらない。途中で質問しない、確認を取らない、判断を仰がない。**

1. プラン通りにコードを変更する
2. 変更ごとにテストを実行する。テストが通らなければその場で直す
3. 全変更後に `python -m pytest` で最終確認する
4. テストが全て通った状態で完了を報告する

プランの範囲内での軽微な調整は自己判断で行い、完了報告時に説明する。プランにないファイルの変更や、方針の転換が必要になった場合は止まってユーザーに相談する。

### 原則

- 不要なファイル・コードを増やさない。既存パターンを再利用する
- 括弧書きで補足しない。言いたいことは直接記述する
