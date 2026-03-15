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
        data: ソルバーに渡した入力データ (year, month, staff, config, wishes)

    Returns:
        dict: 品質スコアカード（公平性指標 + objペナルティ内訳件数）
    """
    shifts = result.get("shifts", {})
    staff_list = data.get("staff", [])
    year = data["year"]
    month = data["month"]
    num_days = calendar.monthrange(year, month)[1]
    ward = data.get("config", {}).get("ward", "")
    wishes = data.get("wishes", [])

    # --- 希望休み日をスタッフ別に収集 ---
    wish_off_days = {}  # staff_id -> set of day numbers
    for w in wishes:
        sid = w.get("staffId", "")
        for e in w.get("entries", []):
            if e.get("shiftType") in REST_SHIFTS:
                wish_off_days.setdefault(sid, set()).add(e.get("day"))

    # --- 各職員のシフトリスト構築 + ペナルティ件数集計 ---
    night_counts = []
    weekend_counts = []
    late_counts = []
    consecutive_maxes = []

    # ペナルティ内訳カウンタ
    consec_5_count = 0
    consec_6_count = 0
    night_interval_close_count = 0
    shinya_no_rest_count = 0
    scattered_night_count = 0
    junnya_off_shinya_count = 0
    day_to_shinya_count = 0
    kibou_night_count = 0
    junnya_shinya_balance_total = 0
    good_rotation_count = 0

    for s in staff_list:
        sid = s["id"]
        wt = s.get("workType", "2kohtai")

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
            if is_weekend and sh and sh not in REST_SHIFTS:
                weekend_work += 1
        weekend_counts.append(weekend_work)

        # 連続勤務: 5連勤/6連勤件数 + MAX
        max_consec = 0
        cur_consec = 0
        for sh in shift_list:
            if sh and sh not in REST_SHIFTS:
                cur_consec += 1
                max_consec = max(max_consec, cur_consec)
            else:
                cur_consec = 0
        consecutive_maxes.append(max_consec)

        # 5連勤/6連勤を窓で検出
        for d in range(num_days - 4):
            if all(shift_list[d+i] and shift_list[d+i] not in REST_SHIFTS for i in range(5)):
                consec_5_count += 1
        for d in range(num_days - 5):
            if all(shift_list[d+i] and shift_list[d+i] not in REST_SHIFTS for i in range(6)):
                consec_6_count += 1

        # --- 三交代専用ペナルティ ---
        if wt == "3kohtai":
            for d in range(num_days - 1):
                # 深夜後に休みなし（翌日が休みでも深夜でもない）
                if shift_list[d] == "shinya":
                    next_sh = shift_list[d + 1]
                    if next_sh not in REST_SHIFTS and next_sh != "shinya":
                        shinya_no_rest_count += 1

            # 散発夜勤: 深夜→休→深夜
            for d in range(num_days - 2):
                if (shift_list[d] == "shinya"
                        and shift_list[d + 1] in REST_SHIFTS
                        and shift_list[d + 2] == "shinya"):
                    scattered_night_count += 1

            # 準夜→休→深夜
            for d in range(num_days - 2):
                if (shift_list[d] == "junnya"
                        and shift_list[d + 1] in REST_SHIFTS
                        and shift_list[d + 2] == "shinya"):
                    junnya_off_shinya_count += 1

            # 日勤帯→翌深夜
            for d in range(num_days - 1):
                if shift_list[d] in ("day", "late") and shift_list[d + 1] == "shinya":
                    day_to_shinya_count += 1

        # --- 夜勤間隔（2交代/3交代共通） ---
        if wt not in ("day_only", "fixed"):
            night_days = [d for d in range(num_days) if shift_list[d] in NIGHT_SHIFTS]
            for i in range(1, len(night_days)):
                gap = night_days[i] - night_days[i - 1]
                if 2 <= gap <= 3:  # 間隔2-3日 = 近接
                    night_interval_close_count += 1

        # --- 希望休前後の夜勤 ---
        staff_off_days = wish_off_days.get(sid, set())
        for off_day in staff_off_days:
            d_idx = off_day - 1  # 0-indexed
            # 希望休の前日が準夜
            if d_idx > 0 and shift_list[d_idx - 1] == "junnya":
                kibou_night_count += 1
            # 希望休の翌日が深夜
            if d_idx < num_days - 1 and shift_list[d_idx + 1] == "shinya":
                kibou_night_count += 1

        # --- 準夜深夜バランス（三交代、junnya_only/shinya_only除外） ---
        if wt == "3kohtai":
            restriction = s.get("nightRestriction", None)
            if restriction not in ("junnya_only", "shinya_only"):
                junnya_cnt = sum(1 for sh in shift_list if sh == "junnya")
                shinya_cnt = sum(1 for sh in shift_list if sh == "shinya")
                junnya_shinya_balance_total += abs(junnya_cnt - shinya_cnt)

        # --- 好ローテーション（三交代: 深夜→休→準夜, 深夜→準夜→休） ---
        if wt == "3kohtai":
            for d in range(num_days - 2):
                if (shift_list[d] == "shinya"
                        and shift_list[d + 1] in REST_SHIFTS
                        and shift_list[d + 2] == "junnya"):
                    good_rotation_count += 1
                if (shift_list[d] == "shinya"
                        and shift_list[d + 1] == "junnya"
                        and shift_list[d + 2] in REST_SHIFTS):
                    good_rotation_count += 1

    # --- 公平性指標 ---
    night_gini = round(calculate_gini(night_counts), 4) if night_counts else 0
    weekend_gini = round(calculate_gini(weekend_counts), 4) if weekend_counts else 0
    late_gini = round(calculate_gini(late_counts), 4) if late_counts else 0

    # --- レンジ ---
    night_range = (max(night_counts) - min(night_counts)) if night_counts else 0
    weekend_range = (max(weekend_counts) - min(weekend_counts)) if weekend_counts else 0
    late_range = (max(late_counts) - min(late_counts)) if late_counts else 0

    # --- 連続勤務 ---
    consec_max = max(consecutive_maxes) if consecutive_maxes else 0
    consec_avg = round(sum(consecutive_maxes) / len(consecutive_maxes), 1) if consecutive_maxes else 0

    # --- ソルバースコア ---
    opt = result.get("optimization_score", {})

    return {
        # 公平性指標
        "night_gini": night_gini,
        "night_grade": evaluate_gini_grade(night_gini),
        "night_range": night_range,
        "weekend_gini": weekend_gini,
        "weekend_grade": evaluate_gini_grade(weekend_gini),
        "weekend_range": weekend_range,
        "late_gini": late_gini,
        "late_range": late_range,
        "consec_max": consec_max,
        "consec_avg": consec_avg,
        # obj
        "objective_value": opt.get("objective_value"),
        "night_diff": opt.get("night_diff"),
        # ペナルティ内訳（件数）
        "consec_5": consec_5_count,
        "consec_6": consec_6_count,
        "night_interval_close": night_interval_close_count,
        "shinya_no_rest": shinya_no_rest_count,
        "scattered_night": scattered_night_count,
        "junnya_off_shinya": junnya_off_shinya_count,
        "day_to_shinya": day_to_shinya_count,
        "kibou_night": kibou_night_count,
        "junnya_shinya_balance": junnya_shinya_balance_total,
        "good_rotation": good_rotation_count,
    }


def format_quality(q):
    """品質スコアカードを文字列にフォーマット（2行）"""
    line1_parts = [
        f"夜勤公平={q['night_grade']}({q['night_gini']:.2f})",
        f"週末公平={q['weekend_grade']}({q['weekend_gini']:.2f})",
        f"連勤max={q['consec_max']}",
    ]
    if q["objective_value"] is not None:
        line1_parts.append(f"obj={q['objective_value']:.0f}")

    line2_parts = [
        f"夜勤差={q['night_range']}",
        f"5連勤={q['consec_5']}",
        f"6連勤={q['consec_6']}",
        f"週末差={q['weekend_range']}",
        f"夜勤近接={q['night_interval_close']}",
        f"深夜後無休={q['shinya_no_rest']}",
        f"散発夜勤={q['scattered_night']}",
        f"準深切替={q['junnya_off_shinya']}",
        f"日深転換={q['day_to_shinya']}",
        f"希望前後夜勤={q['kibou_night']}",
        f"準深バランス={q['junnya_shinya_balance']}",
        f"好ローテ={q['good_rotation']}",
    ]
    if q.get("late_range", 0) > 0:
        line2_parts.append(f"遅出差={q['late_range']}")

    return " ".join(line1_parts) + "\n    内訳: " + " ".join(line2_parts)
