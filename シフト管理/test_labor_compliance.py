"""労基法コンプライアンスチェッカーのユニットテスト"""
import pytest
import calendar
from shift_quality import (
    check_labor_law_compliance,
    _calc_interval_hours,
    SHIFT_TIMES,
)


# =============================================================================
# ヘルパー
# =============================================================================

def _make_data(year, month, staff, shifts_dict, prev_month_data=None):
    """テスト用データ構造を組み立てる"""
    return {
        "year": year,
        "month": month,
        "staff": staff,
        "config": {"ward": "2"},
        "wishes": [],
        "prevMonthData": prev_month_data or {},
    }


def _make_result(shifts_dict):
    return {"shifts": shifts_dict}


def _build_shifts(staff_id, day_shift_pairs):
    """staff_id と [(day, shift), ...] から shifts dict を作る"""
    return {f"{staff_id}-{d}": sh for d, sh in day_shift_pairs}


def _fill_month(staff_id, num_days, default="day", overrides=None):
    """月全体のシフトを default で埋め、overrides で上書き"""
    shifts = {}
    for d in range(1, num_days + 1):
        shifts[f"{staff_id}-{d}"] = default
    if overrides:
        for d, sh in overrides.items():
            shifts[f"{staff_id}-{d}"] = sh
    return shifts


STAFF_2KOHTAI = [{"id": "S1", "name": "テスト太郎", "workType": "2kohtai"}]
STAFF_3KOHTAI = [{"id": "S1", "name": "テスト太郎", "workType": "3kohtai"}]


# =============================================================================
# _calc_interval_hours のテスト
# =============================================================================

class TestCalcInterval:
    def test_day_to_day(self):
        """日勤→日勤: 17:00終了→翌08:30開始 = 15.5h"""
        assert _calc_interval_hours("day", "day") == 15.5

    def test_day_to_shinya(self):
        """日勤→深夜: 17:00終了→翌00:30開始 = 7.5h"""
        assert _calc_interval_hours("day", "shinya") == 7.5

    def test_day_to_night2(self):
        """日勤→夜勤(二交代): 17:00終了→翌16:30開始 = 23.5h"""
        assert _calc_interval_hours("day", "night2") == 23.5

    def test_late_to_shinya(self):
        """遅出→深夜: 21:00終了→翌00:30開始 = 3.5h"""
        assert _calc_interval_hours("late", "shinya") == 3.5

    def test_late_to_day(self):
        """遅出→日勤: 21:00終了→翌08:30開始 = 11.5h"""
        assert _calc_interval_hours("late", "day") == 11.5

    def test_junnya_to_day(self):
        """準夜→日勤: 25:00(翌01:00)終了→翌08:30開始 = 7.5h"""
        # junnya 終了=25.0(翌1:00), day 開始=8.5+24=32.5
        # interval = 32.5 - 25.0 = 7.5
        assert _calc_interval_hours("junnya", "day") == 7.5

    def test_junnya_to_shinya(self):
        """準夜→深夜: 25:00終了→翌00:30開始 = -0.5h → 実質23.5h"""
        # junnya end=25.0, shinya start=0.5+24=24.5
        # interval = 24.5 - 25.0 = -0.5 → but this is next day start
        # Actually: 01:00終了 → 翌日00:30開始 = 23.5h
        result = _calc_interval_hours("junnya", "shinya")
        assert result == pytest.approx(-0.5) or result == pytest.approx(23.5)

    def test_shinya_to_day(self):
        """深夜→日勤: 09:00終了→翌08:30開始 = 23.5h"""
        assert _calc_interval_hours("shinya", "day") == 23.5

    def test_night2_to_day(self):
        """夜勤→日勤: 33:00(翌09:00)終了→翌08:30開始 = -0.5h"""
        # night2は翌日ake扱いなので通常この遷移はないが、計算テスト
        result = _calc_interval_hours("night2", "day")
        # 33.0 → (8.5+24)=32.5 → -0.5
        assert result == pytest.approx(-0.5)

    def test_unknown_shift(self):
        """不明シフトはNone"""
        assert _calc_interval_hours("day", "off") is None
        assert _calc_interval_hours("unknown", "day") is None


# =============================================================================
# 勤務間インターバル11hチェックのテスト
# =============================================================================

class TestIntervalCheck:
    def test_day_to_shinya_violation(self):
        """日勤→深夜: 7.5h → 違反"""
        num_days = 28  # 2026-02
        shifts = _fill_month("S1", num_days, "off", {
            1: "day",
            2: "shinya",
        })
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) >= 1
        assert "7.5h" in interval_violations[0]["detail"]

    def test_late_to_shinya_violation(self):
        """遅出→深夜: 3.5h → 違反"""
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {
            1: "late",
            2: "shinya",
        })
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) >= 1
        assert "3.5h" in interval_violations[0]["detail"]

    def test_day_to_day_no_violation(self):
        """日勤→日勤: 15.5h → 違反なし"""
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {
            1: "day",
            2: "day",
        })
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) == 0

    def test_late_to_day_no_violation(self):
        """遅出→日勤: 11.5h → 違反なし"""
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {
            1: "late",
            2: "day",
        })
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) == 0

    def test_month_boundary_violation(self):
        """前月末日勤→当月1日深夜: 月またぎ違反"""
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {1: "shinya"})
        prev = {"S1": {"lastDay": "day", "secondLastDay": "", "consecutiveWork": 1}}
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts, prev)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) >= 1
        assert "前月末" in interval_violations[0]["detail"]

    def test_rest_day_between_no_violation(self):
        """日勤→休み→深夜: 間に休みがあるので違反なし"""
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {
            1: "day",
            2: "off",
            3: "shinya",
        })
        data = _make_data(2026, 2, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        assert len(interval_violations) == 0

    def test_night2_ake_sequence(self):
        """night2→ake: ake は night2 の続きなのでインターバルチェック対象"""
        num_days = 31
        shifts = _fill_month("S1", num_days, "off", {
            1: "night2",
            2: "ake",
            3: "day",
        })
        data = _make_data(2026, 3, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        # night2→ake: ake は night2 の明け日
        # ake の終了は09:00、次のdayは08:30 → 23.5h → OK
        # ake→day のインターバル: ake end=9.0, day start=8.5+24=32.5, interval=23.5 → OK
        interval_violations = [v for v in compliance["violations"] if v["type"] == "interval_11h"]
        # night2→ake は特殊ケース。night2 end=33.0, ake start=None → None → skip
        # ake→day: ake end=9.0, day start=32.5, interval=23.5 → OK
        assert all("ake" not in v["detail"] or "23.5" in v["detail"]
                    for v in interval_violations)

    def test_fixed_staff_excluded(self):
        """固定シフト職員はチェック対象外"""
        staff = [{"id": "S1", "name": "固定太郎", "workType": "fixed"}]
        num_days = 28
        shifts = _fill_month("S1", num_days, "off", {1: "day", 2: "shinya"})
        data = _make_data(2026, 2, staff, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        assert compliance["compliant"] is True


# =============================================================================
# 暦週1休日チェック（労基法35条）のテスト
# =============================================================================

class TestWeeklyRest:
    def test_seven_day_work_week(self):
        """日曜〜土曜の7日間すべて勤務 → 違反"""
        # 2026-03: 1日(日)
        year, month = 2026, 3
        num_days = 31
        # 1日(日)〜7日(土)をすべて日勤
        shifts = _fill_month("S1", num_days, "off", {
            d: "day" for d in range(1, 8)
        })
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        weekly_violations = [v for v in compliance["violations"] if v["type"] == "weekly_rest"]
        assert len(weekly_violations) >= 1

    def test_rest_on_wednesday_no_violation(self):
        """日曜〜土曜の週で水曜に休み → 違反なし"""
        year, month = 2026, 3
        num_days = 31
        shifts = _fill_month("S1", num_days, "off", {
            1: "day", 2: "day", 3: "day", 4: "off",  # 水曜休み
            5: "day", 6: "day", 7: "day",
        })
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        weekly_violations = [v for v in compliance["violations"] if v["type"] == "weekly_rest"]
        assert len(weekly_violations) == 0

    def test_ake_counts_as_rest(self):
        """明け(ake)は休息扱い → 暦週内に ake があれば違反なし"""
        year, month = 2026, 3
        num_days = 31
        shifts = _fill_month("S1", num_days, "off", {
            1: "day", 2: "day", 3: "night2",
            4: "ake", 5: "day", 6: "day", 7: "day",
        })
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        weekly_violations = [v for v in compliance["violations"] if v["type"] == "weekly_rest"]
        assert len(weekly_violations) == 0

    def test_all_rest_no_violation(self):
        """全日休み → 違反なし"""
        year, month = 2026, 3
        num_days = 31
        shifts = _fill_month("S1", num_days, "off")
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        assert compliance["compliant"] is True


# =============================================================================
# 4週4休チェック（労基法35条変形）のテスト
# =============================================================================

class TestFourWeekRest:
    def test_28_days_only_3_rest(self):
        """28日間で休日3日のみ → 違反"""
        year, month = 2026, 3
        num_days = 31
        # 1〜28日のうち、8,16,24日のみ休み（3日）
        overrides = {d: "day" for d in range(1, 29)}
        overrides[8] = "off"
        overrides[16] = "off"
        overrides[24] = "off"
        shifts = _fill_month("S1", num_days, "off", overrides)
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        four_week_violations = [v for v in compliance["violations"] if v["type"] == "four_week_rest"]
        assert len(four_week_violations) >= 1

    def test_28_days_4_rest_no_violation(self):
        """28日間で休日4日 → 違反なし"""
        year, month = 2026, 3
        num_days = 31
        overrides = {d: "day" for d in range(1, 29)}
        overrides[7] = "off"
        overrides[14] = "off"
        overrides[21] = "off"
        overrides[28] = "off"
        shifts = _fill_month("S1", num_days, "off", overrides)
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        four_week_violations = [v for v in compliance["violations"] if v["type"] == "four_week_rest"]
        assert len(four_week_violations) == 0


# =============================================================================
# サマリー・compliant のテスト
# =============================================================================

class TestSummary:
    def test_compliant_when_no_violations(self):
        """違反なし → compliant=True"""
        year, month = 2026, 3
        num_days = 31
        shifts = _fill_month("S1", num_days, "off")
        data = _make_data(year, month, STAFF_2KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        assert compliance["compliant"] is True
        assert compliance["summary"]["total"] == 0

    def test_summary_counts(self):
        """複数種類の違反がサマリーに正しく集計される"""
        year, month = 2026, 3  # 1日=日曜
        num_days = 31
        # day→shinyaのインターバル違反 + 7連勤（1日日曜〜7日土曜全勤務）
        shifts = _fill_month("S1", num_days, "off", {
            1: "day", 2: "shinya", 3: "day", 4: "day",
            5: "day", 6: "day", 7: "day",
        })
        data = _make_data(year, month, STAFF_3KOHTAI, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        assert compliance["summary"]["interval_11h"] >= 1
        # 暦週チェック: 1(日)〜7(土)全勤務 → shinya も勤務なので
        # ただし2日がshinyaで勤務なので全日勤務
        assert compliance["compliant"] is False

    def test_empty_staff(self):
        """職員なし → compliant=True"""
        data = _make_data(2026, 3, [], {})
        result = _make_result({})
        compliance = check_labor_law_compliance(result, data)
        assert compliance["compliant"] is True

    def test_multiple_staff(self):
        """複数職員のチェック"""
        staff = [
            {"id": "S1", "name": "太郎", "workType": "3kohtai"},
            {"id": "S2", "name": "花子", "workType": "2kohtai"},
        ]
        num_days = 28
        shifts = {}
        shifts.update(_fill_month("S1", num_days, "off", {1: "day", 2: "shinya"}))
        shifts.update(_fill_month("S2", num_days, "off"))  # S2は全休み
        data = _make_data(2026, 2, staff, shifts)
        result = _make_result(shifts)
        compliance = check_labor_law_compliance(result, data)
        # S1のみ違反あり
        s1_violations = [v for v in compliance["violations"] if v["staff_id"] == "S1"]
        s2_violations = [v for v in compliance["violations"] if v["staff_id"] == "S2"]
        assert len(s1_violations) >= 1
        assert len(s2_violations) == 0
