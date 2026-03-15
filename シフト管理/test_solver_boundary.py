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


# === 1病棟 職種別制約テスト ===
def _make_staff_typed(sid, name, wt="2kohtai", staff_type="nurse", max_night=5):
    """typeフィールド付きの職員データ"""
    return {"id": sid, "name": name, "workType": wt, "type": staff_type,
            "maxNight": max_night}


def _ward1_data(staff, **kwargs):
    """1病棟用のテストデータ"""
    d = {
        "year": 2026, "month": 4,  # 4月: 1日=水曜
        "staff": staff,
        "config": {
            "ward": "1",
            "reqDayWeekday": 7, "reqDayHoliday": 5,
            "reqJunnya": 2, "reqShinya": 2,
            "reqLate": 0, "maxLate": 0, "monthlyOff": 9,
        },
        "wishes": [],
        "prevMonthData": {},
    }
    d.update(kwargs)
    return d


class TestWard1QualifiedStaffConstraints:
    """1病棟の有資格者最低人数・nurse最低1名・nurseaide夜勤上限テスト"""

    def _build_ward1_staff(self):
        """1病棟テスト用: nurse 10名 + junkango 3名 + nurseaide 5名 = 18名"""
        staff = []
        for i in range(10):
            staff.append(_make_staff_typed(f"n{i}", f"看護師{i}", "2kohtai", "nurse", 4))
        for i in range(3):
            staff.append(_make_staff_typed(f"j{i}", f"准看{i}", "3kohtai", "junkango", 5))
        for i in range(5):
            staff.append(_make_staff_typed(f"a{i}", f"助手{i}", "3kohtai", "nurseaide", 5))
        return staff

    def test_ward1_qualified_minimum_enforced(self):
        """1病棟: 有資格者(nurse+junkango)日勤最低人数が守られること"""
        from datetime import date as dt
        staff = self._build_ward1_staff()
        data = _ward1_data(staff)
        result = ShiftSolver(data).solve()
        assert result["status"].lower() in ("optimal", "feasible"), f"解なし: {result.get('message')}"

        shifts = result["shifts"]  # フラット形式: {"staffId-day": "shift"}
        num_days = 30  # 2026年4月
        WD_MIN = {1: 3, 2: 4, 4: 4, 5: 3}  # 火=3, 水=4, 金=4, 土=3
        HOLIDAY_MIN = 2

        qualified_ids = {s["id"] for s in staff if s["type"] in ("nurse", "junkango")}
        for d in range(1, num_days + 1):
            d_obj = dt(2026, 4, d)
            weekday = d_obj.weekday()
            is_sun = weekday == 6
            if is_sun:
                min_q = HOLIDAY_MIN
            elif weekday in WD_MIN:
                min_q = WD_MIN[weekday]
            else:
                continue  # 月木は制限なし
            q_day_count = sum(1 for sid in qualified_ids
                              if shifts.get(f"{sid}-{d}") == "day")
            assert q_day_count >= min_q, \
                f"4/{d}({['月','火','水','木','金','土','日'][weekday]}): 有資格者日勤{q_day_count}名 < 最低{min_q}名"

    def test_ward1_nurse_minimum_all_bands(self):
        """1病棟: 全時間帯でnurse最低1名"""
        staff = self._build_ward1_staff()
        data = _ward1_data(staff)
        result = ShiftSolver(data).solve()
        assert result["status"].lower() in ("optimal", "feasible"), f"解なし: {result.get('message')}"

        shifts = result["shifts"]  # フラット形式: {"staffId-day": "shift"}
        num_days = 30
        nurse_ids = {s["id"] for s in staff if s["type"] == "nurse"}

        for d in range(1, num_days + 1):
            # 日勤帯
            n_day = sum(1 for sid in nurse_ids if shifts.get(f"{sid}-{d}") == "day")
            assert n_day >= 1, f"4/{d}: 日勤帯にnurse {n_day}名（最低1名必要）"
            # 準夜帯 (junnya + night2)
            n_junnya = sum(1 for sid in nurse_ids
                          if shifts.get(f"{sid}-{d}") in ("junnya", "night2"))
            assert n_junnya >= 1, f"4/{d}: 準夜帯にnurse {n_junnya}名（最低1名必要）"
            # 深夜帯 (shinya + ake)
            n_shinya = sum(1 for sid in nurse_ids
                          if shifts.get(f"{sid}-{d}") in ("shinya", "ake"))
            assert n_shinya >= 1, f"4/{d}: 深夜帯にnurse {n_shinya}名（最低1名必要）"

    def test_ward1_nurseaide_night_limit(self):
        """1病棟: nurseaideの夜勤が各帯1名以下"""
        staff = self._build_ward1_staff()
        data = _ward1_data(staff)
        result = ShiftSolver(data).solve()
        assert result["status"].lower() in ("optimal", "feasible"), f"解なし: {result.get('message')}"

        shifts = result["shifts"]  # フラット形式: {"staffId-day": "shift"}
        num_days = 30
        aide_ids = {s["id"] for s in staff if s["type"] == "nurseaide"}

        for d in range(1, num_days + 1):
            # 準夜帯
            na_junnya = sum(1 for sid in aide_ids
                           if shifts.get(f"{sid}-{d}") in ("junnya", "night2"))
            assert na_junnya <= 1, f"4/{d}: 準夜帯にnurseaide {na_junnya}名（最大1名）"
            # 深夜帯
            na_shinya = sum(1 for sid in aide_ids
                           if shifts.get(f"{sid}-{d}") in ("shinya", "ake"))
            assert na_shinya <= 1, f"4/{d}: 深夜帯にnurseaide {na_shinya}名（最大1名）"
