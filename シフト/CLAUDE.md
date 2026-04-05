# シフト管理

Python + Flask Webアプリ。OR-Tools CP-SAT ソルバーによるシフト自動生成。

## 中核ファイル

- `solver.py` — ソルバー本体。約1600行

## 依存パッケージ

```
pip install -r シフト/requirements.txt
```

## テスト

ローカル・リモートどちらでも実行可能。

```bash
cd シフト
python -m pytest test_validation.py      # 101テスト: バリデーション
python -m pytest test_shift_quality.py   # 36テスト: 品質評価
python -m pytest test_solver_boundary.py # 14テスト: ソルバー境界・診断
python -m pytest test_regression.py      # 全病棟の回帰テスト。実行に数分かかる
```

## シフトデータの永続化

- フロントエンドは localStorage に `sakigakeData` キーでデータを保存する
- 変更のたびに `/api/backup` へ自動同期する。3秒のデバウンスあり
- localStorage が空の場合、サーバーバックアップから自動復元する
  - pywebview は Chrome と別ストレージを使うため、初回起動時に発動する

## ソルバー制約仕様

以下の制約は**ハード制約**である。いかなる理由があってもソフト制約化・緩和してはならない。

### 1. 夜勤帯人数

`reqJunnya`, `reqShinya` で指定された人数を毎日厳守する。`== adjusted_req` でなければならない。1名の不足も許容しない。

### 2. 初期配置

ユーザーが入力した全ての指定と除外はハード制約。前月末制約も同様。
- 指定: assign
- 除外: avoid
- 前月末制約: night2→ake→off、junnya翌日制限

初期配置を無視する解を生成してはならない。

### 3. 公休日数

`monthlyOff` で指定された公休数を厳守する。`== monthlyOff` でなければならない。

### 有給について

有給は初期配置に含まない。労基法上の権利行使であり、概念的に異なる。ただしハード制約として希望日のみに配置する。

### infeasible 時の対処

- 上記3制約の緩和は禁止
- 診断メッセージで原因を具体的に列挙し、ユーザーに設定変更を促す
- 日勤人数はソフト制約のまま可

## 実装上の注意

- `solver.py` の forbidden_map: 禁止シフトは変数作成時に共有 `_false` BoolVar にマッピング済み。workType別の `== 0` 制約は不要
