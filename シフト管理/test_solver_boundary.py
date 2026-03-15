"""solver.py の境界テスト: infeasible診断、月またぎ、エッジケース"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from solver import ShiftSolver


def _make_staff(sid, name, wt="2kohtai", max_night=5):
    return {"id": sid, "name": name, "workType": wt, "maxNight": max_night}


def _base_data(staff, **kwargs):
    """テスト用の最小データ構造"""
    d = {
        "year": 2026, "month": 3,
        "staff": staff,
        "config": {
            "ward": "2",
            "reqDayWeekday": 7, "reqDayHoliday": 5,
            "reqJunnya": 2, "reqShinya": 2,
            "reqLate": 1, "monthlyOff": 9,
        },
        "wishes": [],
        "prevMonthData": {},
    }
    d.update(kwargs)
    return d


# === _diagnose_infeasible() 単体テスト ===
class TestDiagnoseInfeasible:
    def test_no_issues(self):
        """十分な人数 → 診断ヒントなし"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(15)]
        solver = ShiftSolver(_base_data(staff))
        hints = solver._diagnose_infeasible()
        assert len(hints) == 0

    def test_staff_shortage(self):
        """極端に少ない人数 → 人員不足検出"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(3)]
        solver = ShiftSolver(_base_data(staff))
        hints = solver._diagnose_infeasible()
        # 3人で日勤7+遅出1+夜勤4=12人必要なので不足
        assert any("人員不足" in h or "出勤可能" in h for h in hints)

    def test_wish_off_concentration(self):
        """特定日に希望休が集中 → 人員不足日を検出"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(12)]
        # 10人が5日に休み希望
        wishes = [
            {"staffId": f"s{i}", "type": "assign", "shift": "off", "days": [5]}
            for i in range(10)
        ]
        solver = ShiftSolver(_base_data(staff, wishes=wishes))
        hints = solver._diagnose_infeasible()
        assert any("5日" in h for h in hints)

    def test_prev_month_night_concentration(self):
        """前月末に多数が夜勤 → 1日に強制休集中を検出"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(10)]
        prev = {f"s{i}": {"lastDay": "night2", "consecutiveWork": 1} for i in range(5)}
        solver = ShiftSolver(_base_data(staff, prevMonthData=prev))
        hints = solver._diagnose_infeasible()
        assert any("前月夜勤者" in h or "強制休" in h for h in hints)

    def test_consecutive_work_high(self):
        """前月から4連勤以上のスタッフが多い → 月初休み必須を検出"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(10)]
        prev = {f"s{i}": {"lastDay": "day", "consecutiveWork": 4} for i in range(4)}
        solver = ShiftSolver(_base_data(staff, prevMonthData=prev))
        hints = solver._diagnose_infeasible()
        assert any("4連勤" in h for h in hints)

    def test_night_tight_day(self):
        """夜勤可能人数が必要枠と同数 → 夜勤余裕ゼロを検出"""
        # 夜勤可能=6人, 必要夜勤=4枠。10日に2人が休み → 夜勤可能4人 ≤ 4枠
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(6)]
        staff.append(_make_staff("d1", "日勤A", "day_only"))
        staff.append(_make_staff("d2", "日勤B", "day_only"))
        wishes = [
            {"staffId": "s0", "type": "assign", "shift": "off", "days": [10]},
            {"staffId": "s1", "type": "assign", "shift": "off", "days": [10]},
        ]
        solver = ShiftSolver(_base_data(staff, wishes=wishes))
        hints = solver._diagnose_infeasible()
        assert any("夜勤" in h and "10日" in h for h in hints)


# === ソルバー事前チェック テスト ===
class TestSolverPreChecks:
    def test_night_supply_shortage(self):
        """夜勤供給不足 → infeasible + 明確なメッセージ"""
        staff = [_make_staff("s0", "職員0", max_night=1)]
        result = ShiftSolver(_base_data(staff)).solve()
        assert result["status"] == "infeasible"
        assert "夜勤供給不足" in result.get("message", "")

    def test_off_wish_exceeded(self):
        """off希望が公休上限を超過 → infeasible"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(16)]
        wishes = [
            {"staffId": "s0", "type": "assign", "shift": "off",
             "days": list(range(1, 12))}  # 11日のoff希望 > monthlyOff=9
        ]
        result = ShiftSolver(_base_data(staff, wishes=wishes)).solve()
        assert result["status"] == "infeasible"
        assert "off希望" in result.get("message", "")

    def test_worktype_incompatible_wish(self):
        """日勤のみに夜勤希望 → infeasible"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(16)]
        staff.append(_make_staff("d1", "日勤A", "day_only"))
        wishes = [
            {"staffId": "d1", "type": "assign", "shift": "night2", "days": [5]}
        ]
        result = ShiftSolver(_base_data(staff, wishes=wishes)).solve()
        assert result["status"] == "infeasible"
        assert "不可" in result.get("message", "") or "不正" in result.get("message", "")

    def test_prev_month_conflict(self):
        """前月night2なのに1日にday希望 → infeasible"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(16)]
        wishes = [
            {"staffId": "s0", "type": "assign", "shift": "day", "days": [1]}
        ]
        prev = {"s0": {"lastDay": "night2", "consecutiveWork": 1}}
        result = ShiftSolver(_base_data(staff, wishes=wishes, prevMonthData=prev)).solve()
        assert result["status"] == "infeasible"
        assert "前月引継ぎ" in result.get("message", "")

    def test_same_day_conflict(self):
        """同日にoff + day希望 → infeasible"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(16)]
        wishes = [
            {"staffId": "s0", "type": "assign", "shift": "off", "days": [5]},
            {"staffId": "s0", "type": "assign", "shift": "day", "days": [5]},
        ]
        result = ShiftSolver(_base_data(staff, wishes=wishes)).solve()
        assert result["status"] == "infeasible"
        assert "重複" in result.get("message", "")


# === エッジケース ===
class TestSolverEdgeCases:
    def test_empty_staff(self):
        """職員0人 → エラーにならないこと"""
        data = _base_data([])
        solver = ShiftSolver(data)
        hints = solver._diagnose_infeasible()
        # 空でもクラッシュしない
        assert isinstance(hints, list)

    def test_february_28(self):
        """2月28日（非閏年）"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(12)]
        data = _base_data(staff)
        data["year"] = 2025  # 非閏年
        data["month"] = 2
        solver = ShiftSolver(data)
        assert solver.num_days == 28
        hints = solver._diagnose_infeasible()
        assert isinstance(hints, list)

    def test_february_29_leap(self):
        """2月29日（閏年）"""
        staff = [_make_staff(f"s{i}", f"職員{i}") for i in range(12)]
        data = _base_data(staff)
        data["year"] = 2028  # 閏年
        data["month"] = 2
        solver = ShiftSolver(data)
        assert solver.num_days == 29
