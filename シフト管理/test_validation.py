"""validation.py のユニットテスト"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from validation import (
    ValidationError,
    validate_year, validate_month, validate_day,
    validate_ward, validate_shift, validate_staff_id, validate_staff_name,
    validate_shift_category, validate_staff_type, validate_max_night,
    validate_ward_settings,
    validate_staff_data, validate_wish, validate_solve_request,
    validate_locked_shifts, validate_draft_name, validate_actual_change,
)


# === validate_year ===
class TestValidateYear:
    def test_valid(self):
        assert validate_year(2026) == 2026

    def test_too_low(self):
        with pytest.raises(ValidationError):
            validate_year(2019)

    def test_too_high(self):
        with pytest.raises(ValidationError):
            validate_year(2101)

    def test_non_int(self):
        with pytest.raises(ValidationError):
            validate_year("2026")


# === validate_month ===
class TestValidateMonth:
    def test_valid(self):
        assert validate_month(1) == 1
        assert validate_month(12) == 12

    def test_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_month(0)
        with pytest.raises(ValidationError):
            validate_month(13)


# === validate_day ===
class TestValidateDay:
    def test_valid(self):
        assert validate_day(28, 2026, 2) == 28

    def test_feb_29_non_leap(self):
        with pytest.raises(ValidationError):
            validate_day(29, 2026, 2)

    def test_feb_29_leap(self):
        assert validate_day(29, 2028, 2) == 29


# === validate_ward ===
class TestValidateWard:
    def test_valid_codes(self):
        assert validate_ward("1") == "1"
        assert validate_ward("ichiboutou") == "ichiboutou"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_ward("4")

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_ward("")


# === validate_shift ===
class TestValidateShift:
    def test_valid(self):
        assert validate_shift("day") == "day"
        assert validate_shift("night2") == "night2"

    def test_empty_allowed(self):
        assert validate_shift("") == ""
        assert validate_shift(None) == ""

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_shift("invalid")


# === validate_staff_id ===
class TestValidateStaffId:
    def test_valid(self):
        assert validate_staff_id("12345") == "12345"
        assert validate_staff_id("abc-123_X") == "abc-123_X"

    def test_special_chars(self):
        with pytest.raises(ValidationError):
            validate_staff_id("id;DROP TABLE")

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_staff_id("")


# === validate_staff_name ===
class TestValidateStaffName:
    def test_valid(self):
        assert validate_staff_name("田中 太郎") == "田中 太郎"

    def test_html_chars(self):
        with pytest.raises(ValidationError):
            validate_staff_name("<script>")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_staff_name("あ" * 101)


# === validate_shift_category ===
class TestValidateShiftCategory:
    def test_valid(self):
        assert validate_shift_category("twoShift") == "twoShift"
        assert validate_shift_category("flexRequest") == "flexRequest"

    def test_default(self):
        assert validate_shift_category("") == "twoShift"
        assert validate_shift_category(None) == "twoShift"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_shift_category("unknown")


# === validate_max_night ===
class TestValidateMaxNight:
    def test_valid(self):
        assert validate_max_night(5) == 5
        assert validate_max_night(0) == 0

    def test_default(self):
        assert validate_max_night(None) == 5

    def test_string_conversion(self):
        assert validate_max_night("3") == 3

    def test_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_max_night(-1)
        with pytest.raises(ValidationError):
            validate_max_night(32)


# === validate_ward_settings ===
class TestValidateWardSettings:
    def test_valid(self):
        settings = {"reqDayWeekday": 7, "reqDayHoliday": 5, "reqJunnya": 2, "reqShinya": 2}
        result = validate_ward_settings(settings)
        assert result["reqDayWeekday"] == 7

    def test_out_of_range(self):
        with pytest.raises(ValidationError, match="0〜20"):
            validate_ward_settings({"reqDayWeekday": -1})

    def test_too_high(self):
        with pytest.raises(ValidationError, match="0〜10"):
            validate_ward_settings({"reqJunnya": 15})

    def test_non_integer(self):
        with pytest.raises(ValidationError, match="整数"):
            validate_ward_settings({"reqShinya": "abc"})

    def test_string_integer(self):
        result = validate_ward_settings({"reqLate": "3"})
        assert result["reqLate"] == 3

    def test_not_dict(self):
        with pytest.raises(ValidationError):
            validate_ward_settings("invalid")

    def test_preserves_extra_fields(self):
        settings = {"reqDayWeekday": 7, "customField": "keep"}
        result = validate_ward_settings(settings)
        assert result["customField"] == "keep"


# === validate_solve_request config range checks ===
class TestSolveRequestConfigRange:
    def test_config_range_valid(self):
        data = {
            "year": 2026, "month": 3, "staff": [],
            "config": {"ward": "1", "reqDayWeekday": 7, "reqJunnya": 3}
        }
        result = validate_solve_request(data)
        assert result["config"]["reqDayWeekday"] == 7

    def test_config_range_invalid(self):
        data = {
            "year": 2026, "month": 3, "staff": [],
            "config": {"ward": "1", "reqDayWeekday": 25}
        }
        with pytest.raises(ValidationError, match="0〜20"):
            validate_solve_request(data)


# === validate_locked_shifts ===
class TestValidateLockedShifts:
    def test_flat_format(self):
        result = validate_locked_shifts({"123-1": "day", "123-2": "off"})
        assert result["123-1"] == "day"

    def test_nested_format(self):
        result = validate_locked_shifts({"123": {"1": "day", "2": "off"}})
        assert result["123"]["1"] == "day"

    def test_invalid_shift(self):
        with pytest.raises(ValidationError):
            validate_locked_shifts({"123-1": "invalid_shift"})


# === validate_draft_name ===
class TestValidateDraftName:
    def test_valid(self):
        assert validate_draft_name("草案1") == "草案1"

    def test_dangerous_chars(self):
        with pytest.raises(ValidationError):
            validate_draft_name("name<script>")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_draft_name("x" * 51)


# === validate_actual_change ===
class TestValidateActualChange:
    def test_valid(self):
        result = validate_actual_change({"staffId": "123", "day": 5, "to": "day", "reason": "変更"})
        assert result["staffId"] == "123"
        assert result["day"] == 5

    def test_day_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_actual_change({"staffId": "123", "day": 0, "to": "day"})

    def test_invalid_shift(self):
        with pytest.raises(ValidationError):
            validate_actual_change({"staffId": "123", "day": 1, "to": "invalid"})


# === validate_staff_data cross-field validation ===
class TestStaffDataCrossField:
    def test_day_only_with_max_night_corrected(self):
        """日勤のみ職員のmaxNightが0に補正されること"""
        staff = {"id": "s1", "name": "テスト", "shiftCategory": "dayOnly", "maxNight": 5}
        result = validate_staff_data(staff)
        assert result["maxNight"] == 0

    def test_day_only_work_type_with_max_night_corrected(self):
        """workType=day_only職員のmaxNightが0に補正されること"""
        staff = {"id": "s1", "name": "テスト", "workType": "day_only", "maxNight": 3}
        result = validate_staff_data(staff)
        assert result["maxNight"] == 0

    def test_two_shift_with_max_night_kept(self):
        """二交代職員のmaxNightは補正しないこと"""
        staff = {"id": "s1", "name": "テスト", "shiftCategory": "twoShift", "maxNight": 5}
        result = validate_staff_data(staff)
        assert result["maxNight"] == 5


# === validate_draft_name path traversal ===
class TestDraftNamePathTraversal:
    def test_dot_dot(self):
        with pytest.raises(ValidationError):
            validate_draft_name("..backup")

    def test_double_dot_in_middle(self):
        with pytest.raises(ValidationError):
            validate_draft_name("name..test")

    def test_starts_with_dot(self):
        with pytest.raises(ValidationError):
            validate_draft_name(".hidden")

    def test_starts_with_tilde(self):
        with pytest.raises(ValidationError):
            validate_draft_name("~root")

    def test_normal_name_with_dots_in_word(self):
        """ドットを含まない普通の名前はOK"""
        assert validate_draft_name("草案A-1") == "草案A-1"


# === validate_wish days filtering ===
class TestWishDaysFiltering:
    def test_valid_days_kept(self):
        wish = {"staffId": "s1", "type": "assign", "shift": "off", "days": [1, 15, 28]}
        result = validate_wish(wish)
        assert result["days"] == [1, 15, 28]

    def test_invalid_days_filtered(self):
        wish = {"staffId": "s1", "type": "assign", "shift": "off", "days": [0, 5, 32, "abc"]}
        result = validate_wish(wish)
        assert result["days"] == [5]

    def test_empty_days(self):
        wish = {"staffId": "s1", "type": "assign", "shift": "off", "days": []}
        result = validate_wish(wish)
        assert result["days"] == []


# === validate_solve_request comprehensive ===
class TestSolveRequestComprehensive:
    def test_monthly_off_valid(self):
        data = {
            "year": 2026, "month": 3, "staff": [],
            "config": {"ward": "1", "monthlyOff": 9}
        }
        result = validate_solve_request(data)
        assert result["config"]["monthlyOff"] == 9

    def test_monthly_off_out_of_range(self):
        data = {
            "year": 2026, "month": 3, "staff": [],
            "config": {"ward": "1", "monthlyOff": 5}
        }
        with pytest.raises(ValidationError, match="6-12"):
            validate_solve_request(data)

    def test_invalid_staff_skipped(self):
        data = {
            "year": 2026, "month": 3,
            "staff": [
                {"id": "s1", "name": "有効"},
                {"id": "", "name": ""},  # invalid
            ]
        }
        result = validate_solve_request(data)
        assert len(result["staff"]) == 1
        assert result["_skippedStaff"] == 1

    def test_locked_shifts_validated(self):
        data = {
            "year": 2026, "month": 3, "staff": [],
            "lockedShifts": {"s1-1": "day", "s1-2": "off"}
        }
        result = validate_solve_request(data)
        assert result["lockedShifts"]["s1-1"] == "day"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
