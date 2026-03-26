"""shift_quality.py のユニットテスト"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from shift_quality import (
    calculate_personal_score,
    calculate_gini,
    calculate_cv,
    evaluate_gini_grade,
    evaluate_shift_quality,
    format_quality,
)


# === calculate_gini ===
class TestCalculateGini:
    def test_equal_values(self):
        """全員同じ値 → ジニ係数 = 0"""
        assert calculate_gini([5, 5, 5, 5]) == 0.0

    def test_unequal_values(self):
        """ばらつきあり → 正の値"""
        g = calculate_gini([1, 1, 1, 10])
        assert 0 < g < 1

    def test_extreme_inequality(self):
        """極端な不平等 → 高い値"""
        g = calculate_gini([0, 0, 0, 100])
        assert g > 0.5

    def test_empty(self):
        assert calculate_gini([]) == 0.0

    def test_single(self):
        assert calculate_gini([5]) == 0.0

    def test_all_zero(self):
        assert calculate_gini([0, 0, 0]) == 0.0

    def test_two_values(self):
        g = calculate_gini([0, 10])
        assert g > 0


# === calculate_cv ===
class TestCalculateCV:
    def test_equal_values(self):
        assert calculate_cv([5, 5, 5]) == 0.0

    def test_varied_values(self):
        cv = calculate_cv([1, 2, 3, 4, 5])
        assert cv > 0

    def test_empty(self):
        assert calculate_cv([]) == 0.0

    def test_single(self):
        assert calculate_cv([5]) == 0.0

    def test_all_zero(self):
        assert calculate_cv([0, 0, 0]) == 0.0


# === evaluate_gini_grade ===
class TestEvaluateGiniGrade:
    def test_excellent(self):
        assert evaluate_gini_grade(0.05) == "優秀"

    def test_good(self):
        assert evaluate_gini_grade(0.15) == "良好"

    def test_normal(self):
        assert evaluate_gini_grade(0.25) == "普通"

    def test_needs_improvement(self):
        assert evaluate_gini_grade(0.35) == "要改善"

    def test_boundary_01(self):
        assert evaluate_gini_grade(0.1) == "良好"

    def test_boundary_02(self):
        assert evaluate_gini_grade(0.2) == "普通"

    def test_boundary_03(self):
        assert evaluate_gini_grade(0.3) == "要改善"

    def test_zero(self):
        assert evaluate_gini_grade(0.0) == "優秀"


# === calculate_personal_score ===
class TestCalculatePersonalScore:
    def test_zero_penalties(self):
        assert calculate_personal_score({}) == 0

    def test_with_penalties(self):
        p = {"consec_5": 2, "night_interval_close": 1}
        assert calculate_personal_score(p) == 3

    def test_good_rotation_excluded(self):
        """good_rotationはスコアに含まれない"""
        p = {"good_rotation": 5}
        assert calculate_personal_score(p) == 0

    def test_all_penalties(self):
        p = {k: 1 for k in [
            "consec_5", "consec_6", "night_interval_close",
            "shinya_no_rest", "scattered_night", "junnya_off_shinya",
            "day_to_shinya", "kibou_night", "junnya_shinya_balance",
        ]}
        assert calculate_personal_score(p) == 9


# === evaluate_shift_quality (統合テスト) ===
def _make_staff(sid, name, wt="2kohtai"):
    return {"id": sid, "name": name, "workType": wt}


def _make_shifts(staff_id, shift_list):
    """shift_list[0] = day1"""
    return {f"{staff_id}-{d+1}": s for d, s in enumerate(shift_list) if s}


class TestEvaluateShiftQuality:
    def test_empty_result(self):
        result = {"shifts": {}, "optimization_score": {}}
        data = {"year": 2026, "month": 3, "staff": [], "config": {}, "wishes": []}
        q = evaluate_shift_quality(result, data)
        assert q["night_gini"] == 0
        assert q["per_staff"] == []

    def test_basic_2kohtai(self):
        """二交代1名: 5連勤を検出"""
        shifts = _make_shifts("a", [
            "day", "day", "day", "day", "day",  # 5連勤
            "off", "off",
        ] + ["day"] * 24)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["consec_5"] >= 1
        assert len(q["per_staff"]) == 1

    def test_fixed_staff_excluded(self):
        """固定シフト職員はper_staffから除外"""
        result = {"shifts": {}, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "fixed")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert len(q["per_staff"]) == 0

    def test_night_interval_close_2kohtai(self):
        """二交代: 夜勤間隔2日 → night_interval_close"""
        # day1=night2, day2=ake, day3=off, day4=night2 → 間隔=3(day1→day4)
        shifts = _make_shifts("a", [
            "night2", "ake", "off", "night2", "ake", "off",
        ] + ["day"] * 25)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["night_interval_close"] >= 1

    def test_3kohtai_shinya_no_rest(self):
        """三交代: 深夜→日勤 = shinya_no_rest"""
        shifts = _make_shifts("a", [
            "shinya", "day",
        ] + ["off"] * 29)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "3kohtai")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["shinya_no_rest"] >= 1

    def test_3kohtai_scattered_night(self):
        """三交代: 深夜→休→深夜 = scattered_night"""
        shifts = _make_shifts("a", [
            "shinya", "off", "shinya",
        ] + ["off"] * 28)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "3kohtai")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["scattered_night"] >= 1

    def test_3kohtai_day_to_shinya(self):
        """三交代: 日勤→深夜 = day_to_shinya"""
        shifts = _make_shifts("a", [
            "day", "shinya",
        ] + ["off"] * 29)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "3kohtai")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["day_to_shinya"] >= 1

    def test_3kohtai_good_rotation(self):
        """三交代: 深夜→休→準夜 = good_rotation"""
        shifts = _make_shifts("a", [
            "shinya", "off", "junnya",
        ] + ["off"] * 28)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "3kohtai")],
            "config": {}, "wishes": [],
        }
        q = evaluate_shift_quality(result, data)
        assert q["good_rotation"] >= 1

    def test_month_boundary_consec5(self):
        """月またぎ5連勤: 前月3連勤 + 当月2勤務 = 5連勤"""
        shifts = _make_shifts("a", [
            "day", "day", "off",
        ] + ["day"] * 28)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中")],
            "config": {}, "wishes": [],
            "prevMonthData": {"a": {"lastDay": "day", "secondLastDay": "day", "consecutiveWork": 3}},
        }
        q = evaluate_shift_quality(result, data)
        assert q["consec_5"] >= 1

    def test_month_boundary_scattered_night_3k(self):
        """月またぎ散発夜勤: 前月末shinya→当月1日rest→2日shinya"""
        shifts = _make_shifts("a", [
            "off", "shinya",
        ] + ["off"] * 29)
        result = {"shifts": shifts, "optimization_score": {}}
        data = {
            "year": 2026, "month": 3,
            "staff": [_make_staff("a", "田中", "3kohtai")],
            "config": {}, "wishes": [],
            "prevMonthData": {"a": {"lastDay": "shinya", "secondLastDay": "off", "consecutiveWork": 1}},
        }
        q = evaluate_shift_quality(result, data)
        assert q["scattered_night"] >= 1


# === format_quality ===
class TestFormatQuality:
    def test_basic_format(self):
        q = {
            "night_gini": 0.05, "night_grade": "優秀", "night_range": 1,
            "weekend_gini": 0.10, "weekend_grade": "良好", "weekend_range": 2,
            "late_gini": 0.0, "late_range": 0,
            "consec_max": 4, "consec_avg": 3.5,
            "objective_value": 1500.0, "night_diff": 1,
            "consec_5": 0, "consec_6": 0, "night_interval_close": 1,
            "shinya_no_rest": 0, "scattered_night": 0, "junnya_off_shinya": 0,
            "day_to_shinya": 0, "kibou_night": 0, "junnya_shinya_balance": 0,
            "good_rotation": 2,
            "per_staff": [{"name": "田中", "score": 1}],
        }
        text = format_quality(q)
        assert "優秀" in text
        assert "obj=1500" in text
        assert "内訳:" in text

    def test_no_objective(self):
        q = {
            "night_gini": 0.0, "night_grade": "優秀", "night_range": 0,
            "weekend_gini": 0.0, "weekend_grade": "優秀", "weekend_range": 0,
            "late_gini": 0.0, "late_range": 0,
            "consec_max": 0, "consec_avg": 0,
            "objective_value": None, "night_diff": None,
            "consec_5": 0, "consec_6": 0, "night_interval_close": 0,
            "shinya_no_rest": 0, "scattered_night": 0, "junnya_off_shinya": 0,
            "day_to_shinya": 0, "kibou_night": 0, "junnya_shinya_balance": 0,
            "good_rotation": 0,
            "per_staff": [],
        }
        text = format_quality(q)
        assert "obj=" not in text
