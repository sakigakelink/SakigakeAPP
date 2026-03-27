#!/bin/bash
# SakigakeAPP デプロイスクリプト
# add → commit → push → リモート pull を一括実行

set -e

# コミットメッセージを引数から取得
if [ -z "$1" ]; then
  echo "使い方: bash deploy.sh \"変更内容のメモ\""
  echo "例:     bash deploy.sh \"シフトのバグ修正\""
  exit 1
fi

echo "=== SakigakeAPP デプロイ ==="

# 1. 変更ファイルを全て add
echo "[1/4] 変更ファイルを追加..."
git add -A

# 2. コミット（変更がない場合はスキップ）
if git diff --cached --quiet; then
  echo "[2/4] 変更なし — コミットをスキップ"
  echo "=== デプロイ完了（変更なし） ==="
  exit 0
fi

echo "[2/4] コミット..."
git commit -m "$1"

# 3. GitHub に push
echo "[3/4] GitHub に push..."
git push origin master

# 4. リモートで pull
echo "[4/4] リモート(mining-base)で pull..."
ssh mining-base "powershell -Command \"cd 'C:\\Users\\Mining-Base\\SakigakeAPP'; git pull origin master\""

echo "=== デプロイ完了 ==="
