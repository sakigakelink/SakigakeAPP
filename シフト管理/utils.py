"""
ユーティリティ関数 - 祝日関連
"""
import os
import json as pyjson
from datetime import date


def _load_holidays():
    """holidays.jsonから祝日データを読み込む"""
    holidays_path = os.path.join(os.path.dirname(__file__), "holidays.json")
    result = set()
    try:
        with open(holidays_path, "r", encoding="utf-8") as f:
            for ds in pyjson.load(f):
                parts = ds.split("-")
                result.add((int(parts[0]), int(parts[1]), int(parts[2])))
    except Exception:
        pass
    return result


HOLIDAYS = _load_holidays()


def is_holiday_or_weekend(year, month, day):
    """土日祝日かどうかを判定"""
    d = date(year, month, day)
    if d.weekday() >= 5:  # 土日
        return True
    if (year, month, day) in HOLIDAYS:
        return True
    return False
