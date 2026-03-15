"""シフト品質評価モジュール

ソルバーが生成したシフト表を多角的に評価する。
test_regression.py および routes.py から利用。
"""
import calendar
from datetime import date
from utils import HOLIDAYS

REST_SHIFTS = {"off", "paid", "refresh"}
NIGHT_SHIFTS = {"night2", "junnya", "shinya"}


def calculate_gini(values):
    """ジニ係数を計算（0=完全平等, 1=完全不平等）"""
    if not values or len(values) < 2:
        return 0.0
    values = sorted(values)
    n = len(values)
    total = sum(values)
    if total == 0:
        return 0.0
    gini_sum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values))
    return gini_sum / (n * total)


def calculate_cv(values):
    """変動係数 (CV) を計算（標準偏差/平均）"""
    if not values or len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5 / mean


def evaluate_gini_grade(g):
    """ジニ係数を4段階で評価"""
    if g < 0.1:
        return "優秀"
    elif g < 0.2:
        return "良好"
    elif g < 0.3:
        return "普通"
    return "要改善"


def evaluate_shift_quality(result, data):
    """ソルバー結果のシフト品質を評価する。

    Args:
        result: ShiftSolver.solve() の返却値
        data: ソルバーに渡した入力データ (year, month, staff, wishes, config)

    Returns:
        dict: 品質スコアカード
    """
    shifts = result.get("shifts", {})
    staff_list = data.get("staff", [])
    year = data["year"]
    month = data["month"]
    num_days = calendar.monthrange(year, month)[1]
    wishes = data.get("wishes", [])

    # --- 各職員のシフトリスト構築 ---
    night_counts = []
    weekend_counts = []
    late_counts = []
    consecutive_maxes = []

    for s in staff_list:
        sid = s["id"]
        wt = s.get("workType", "2kohtai")

        # 固定シフト職員は評価対象外
        if wt == "fixed":
            continue

        shift_list = [shifts.get(f"{sid}-{d}", "") for d in range(1, num_days + 1)]

        # 夜勤カウント（夜勤対象者のみ）
        if wt not in ("day_only", "fixed"):
            nc = sum(1 for sh in shift_list if sh in NIGHT_SHIFTS or sh == "ake")
            night_counts.append(nc)

        # 遅出カウント
        late_counts.append(sum(1 for sh in shift_list if sh == "late"))

        # 週末勤務カウント
        weekend_work = 0
        for d in range(1, num_days + 1):
            wd = date(year, month, d).weekday()
            is_weekend = wd >= 5 or (year, month, d) in HOLIDAYS
            sh = shifts.get(f"{sid}-{d}", "")
            if is_weekend and sh not in REST_SHIFTS:
                weekend_work += 1
        weekend_counts.append(weekend_work)

        # 連続勤務MAX
        max_consec = 0
        cur_consec = 0
        for sh in shift_list:
            if sh and sh not in REST_SHIFTS:
                cur_consec += 1
                max_consec = max(max_consec, cur_consec)
            else:
                cur_consec = 0
        consecutive_maxes.append(max_consec)

    # --- 公平性指標 ---
    night_gini = round(calculate_gini(night_counts), 4) if night_counts else 0
    weekend_gini = round(calculate_gini(weekend_counts), 4) if weekend_counts else 0
    late_gini = round(calculate_gini(late_counts), 4) if late_counts else 0

    # --- 連続勤務 ---
    consec_max = max(consecutive_maxes) if consecutive_maxes else 0
    consec_avg = round(sum(consecutive_maxes) / len(consecutive_maxes), 1) if consecutive_maxes else 0

    # --- 希望達成率 ---
    wish_total = 0
    wish_met = 0
    for w in wishes:
        sid = w.get("staffId")
        wtype = w.get("type")
        shift_val = w.get("shift")
        for day in w.get("days", []):
            wish_total += 1
            actual = shifts.get(f"{sid}-{day}", "")
            if wtype == "assign":
                if shift_val in ("off", "paid") and actual in REST_SHIFTS:
                    wish_met += 1
                elif actual == shift_val:
                    wish_met += 1
            elif wtype == "avoid":
                if actual != shift_val:
                    wish_met += 1
    wish_rate = round(wish_met / wish_total * 100, 1) if wish_total > 0 else None

    # --- ソルバースコア ---
    opt = result.get("optimization_score", {})

    return {
        "night_gini": night_gini,
        "night_grade": evaluate_gini_grade(night_gini),
        "night_range": (max(night_counts) - min(night_counts)) if night_counts else 0,
        "weekend_gini": weekend_gini,
        "weekend_grade": evaluate_gini_grade(weekend_gini),
        "late_gini": late_gini,
        "consec_max": consec_max,
        "consec_avg": consec_avg,
        "wish_total": wish_total,
        "wish_met": wish_met,
        "wish_rate": wish_rate,
        "objective_value": opt.get("objective_value"),
        "night_diff": opt.get("night_diff"),
    }


def format_quality(q):
    """品質スコアカードを1行の文字列にフォーマット"""
    parts = [
        f"夜勤公平={q['night_grade']}({q['night_gini']:.2f})",
        f"週末公平={q['weekend_grade']}({q['weekend_gini']:.2f})",
        f"連勤max={q['consec_max']}",
    ]
    if q["wish_rate"] is not None:
        parts.append(f"希望達成={q['wish_rate']:.0f}%")
    if q["objective_value"] is not None:
        parts.append(f"obj={q['objective_value']:.0f}")
    return " ".join(parts)
