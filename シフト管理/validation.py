"""
Sakigake Shift - 入力バリデーションモジュール
"""
import re
import json
import logging
from datetime import date
import calendar

logger = logging.getLogger(__name__)


# 有効なシフトタイプ
VALID_SHIFTS = {"day", "late", "night2", "junnya", "shinya", "off", "paid", "ake", "refresh"}

# 有効な勤務区分（バックエンド形式）
VALID_SHIFT_CATEGORIES = {"twoShift", "threeShift", "dayOnly", "nightOnly", "flexRequest"}

# 有効な病棟ID
VALID_WARDS = {"ichiboutou", "nibyoutou", "sanbyoutou", "1", "2", "3"}

# 有効な職員タイプ
VALID_STAFF_TYPES = {"nurse", "junkango", "nurseaide"}



class ValidationError(Exception):
    """バリデーションエラー"""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)


def validate_year(year):
    """年のバリデーション"""
    if not isinstance(year, int):
        raise ValidationError("year は整数である必要があります", "year")
    if year < 2020 or year > 2100:
        raise ValidationError("year は 2020-2100 の範囲である必要があります", "year")
    return year


def validate_month(month):
    """月のバリデーション"""
    if not isinstance(month, int):
        raise ValidationError("month は整数である必要があります", "month")
    if month < 1 or month > 12:
        raise ValidationError("month は 1-12 の範囲である必要があります", "month")
    return month


def validate_day(day, year, month):
    """日のバリデーション"""
    if not isinstance(day, int):
        raise ValidationError("day は整数である必要があります", "day")
    num_days = calendar.monthrange(year, month)[1]
    if day < 1 or day > num_days:
        raise ValidationError(f"day は 1-{num_days} の範囲である必要があります", "day")
    return day


def validate_ward(ward):
    """病棟IDのバリデーション"""
    if not ward:
        raise ValidationError("ward は必須です", "ward")
    if str(ward) not in VALID_WARDS:
        raise ValidationError(f"無効な ward: {ward}", "ward")
    return str(ward)


def validate_shift(shift):
    """シフトタイプのバリデーション"""
    if not shift:
        return ""  # 空は許可（クリア用）
    if shift not in VALID_SHIFTS:
        raise ValidationError(f"無効な shift: {shift}", "shift")
    return shift


def validate_staff_id(staff_id):
    """職員IDのバリデーション"""
    if not staff_id:
        raise ValidationError("staffId は必須です", "staffId")
    # IDは文字列または数値
    staff_id_str = str(staff_id)
    # 特殊文字の排除（SQLインジェクション対策）
    if not re.match(r'^[a-zA-Z0-9_-]+$', staff_id_str):
        raise ValidationError("staffId に無効な文字が含まれています", "staffId")
    return staff_id_str


def validate_staff_name(name):
    """職員名のバリデーション"""
    if not name:
        raise ValidationError("name は必須です", "name")
    if len(name) > 100:
        raise ValidationError("name は100文字以下である必要があります", "name")
    # XSS対策: 危険な文字をエスケープ（ここではチェックのみ）
    if '<' in name or '>' in name or '&' in name:
        raise ValidationError("name に無効な文字が含まれています", "name")
    return name


def validate_shift_category(category):
    """勤務区分のバリデーション"""
    if not category:
        return "twoShift"  # デフォルト
    if category not in VALID_SHIFT_CATEGORIES:
        raise ValidationError(f"無効な shiftCategory: {category}", "shiftCategory")
    return category


def validate_staff_type(staff_type):
    """職員タイプのバリデーション"""
    if not staff_type:
        return "nurse"  # デフォルト
    if staff_type not in VALID_STAFF_TYPES:
        raise ValidationError(f"無効な type: {staff_type}", "type")
    return staff_type


def validate_max_night(max_night):
    """夜勤上限のバリデーション"""
    if max_night is None:
        return 5  # デフォルト
    if not isinstance(max_night, int):
        try:
            max_night = int(max_night)
        except (ValueError, TypeError):
            raise ValidationError("maxNight は整数である必要があります", "maxNight")
    if max_night < 0 or max_night > 31:
        raise ValidationError("maxNight は 0-31 の範囲である必要があります", "maxNight")
    return max_night



def validate_staff_data(staff):
    """職員データのバリデーション（元のデータを保持しつつバリデーション）"""
    if not isinstance(staff, dict):
        raise ValidationError("staff は辞書である必要があります", "staff")

    # 元のデータをコピー（すべてのフィールドを保持）
    validated = dict(staff)

    # 必須フィールドのバリデーション
    validated["id"] = validate_staff_id(staff.get("id"))
    validated["name"] = validate_staff_name(staff.get("name"))

    # オプションフィールドのバリデーション（存在する場合のみ）
    if "ward" in staff:
        validated["ward"] = validate_ward(staff["ward"])
    if "shiftCategory" in staff:
        validated["shiftCategory"] = validate_shift_category(staff["shiftCategory"])
    if "type" in staff:
        validated["type"] = validate_staff_type(staff["type"])
    if "maxNight" in staff:
        validated["maxNight"] = validate_max_night(staff["maxNight"])

    # クロスフィールドバリデーション
    shift_cat = validated.get("shiftCategory", staff.get("shiftCategory"))
    work_type = staff.get("workType")
    max_night = validated.get("maxNight", staff.get("maxNight"))
    if shift_cat in ("dayOnly",) or work_type == "day_only":
        if max_night is not None and max_night > 0:
            logger.warning("日勤のみ職員(%s)に夜勤上限 %s が設定されています（0に補正）",
                           validated.get("id", "?"), max_night)
            validated["maxNight"] = 0

    return validated


def validate_wish(wish):
    """希望データのバリデーション（元のデータを保持しつつバリデーション）"""
    if not isinstance(wish, dict):
        raise ValidationError("wish は辞書である必要があります", "wish")

    # 元のデータをコピー（すべてのフィールドを保持）
    validated = dict(wish)

    # 必須フィールドのバリデーション
    validated["staffId"] = validate_staff_id(wish.get("staffId"))

    # type
    wish_type = wish.get("type", "assign")
    if wish_type not in {"assign", "avoid"}:
        raise ValidationError(f"無効な wish type: {wish_type}", "type")
    validated["type"] = wish_type

    # shift
    if "shift" in wish:
        validated["shift"] = validate_shift(wish["shift"])

    # days
    days = wish.get("days", [])
    if not isinstance(days, list):
        raise ValidationError("days は配列である必要があります", "days")
    valid_days = [int(d) for d in days if isinstance(d, (int, float)) and 1 <= d <= 31]
    skipped = len(days) - len(valid_days)
    if skipped > 0:
        logger.warning("希望データ(staffId=%s): %d件の無効な日付をスキップしました",
                       validated.get("staffId", "?"), skipped)
    validated["days"] = valid_days

    return validated


def validate_solve_request(data):
    """ソルバーリクエストのバリデーション"""
    if not isinstance(data, dict):
        raise ValidationError("リクエストデータは辞書である必要があります")

    validated = {
        "year": validate_year(data.get("year")),
        "month": validate_month(data.get("month")),
    }

    # staff
    staff_list = data.get("staff", [])
    if not isinstance(staff_list, list):
        raise ValidationError("staff は配列である必要があります", "staff")
    validated["staff"] = []
    skipped_staff = 0
    for s in staff_list:
        try:
            validated["staff"].append(validate_staff_data(s))
        except ValidationError as e:
            skipped_staff += 1
            logger.warning("無効な職員データをスキップ: id=%s err=%s", s.get('id', '?'), e.message)
    if skipped_staff:
        validated["_skippedStaff"] = skipped_staff

    # wishes
    wishes = data.get("wishes", [])
    if isinstance(wishes, list):
        validated["wishes"] = []
        skipped_wishes = 0
        for w in wishes:
            try:
                validated["wishes"].append(validate_wish(w))
            except ValidationError as e:
                skipped_wishes += 1
                logger.warning("無効な希望データをスキップ: staffId=%s err=%s",
                               w.get('staffId', '?'), e.message)
        if skipped_wishes:
            validated["_skippedWishes"] = skipped_wishes

    # config（元のデータをコピーしつつバリデーション）
    config = data.get("config", {})
    if isinstance(config, dict):
        validated["config"] = dict(config)  # 全フィールドを保持
        if "ward" in config:
            validated["config"]["ward"] = validate_ward(config["ward"])
        # 数値フィールド（範囲チェック付き）
        range_rules = {
            "reqDayWeekday": (0, 20), "reqDayHoliday": (0, 20),
            "reqJunnya": (0, 10), "reqShinya": (0, 10),
            "reqLate": (0, 10), "maxLate": (0, 10),
        }
        for key in range_rules:
            if key in config:
                try:
                    val = int(config[key])
                    lo, hi = range_rules[key]
                    if val < lo or val > hi:
                        raise ValidationError(f"{key} は {lo}〜{hi} の範囲で指定してください（現在値: {val}）", key)
                    validated["config"][key] = val
                except (ValueError, TypeError):
                    raise ValidationError(f"{key} は整数である必要があります", key)
        # monthlyOff は範囲チェック付き
        if "monthlyOff" in config:
            try:
                mo = int(config["monthlyOff"])
                if mo < 6 or mo > 12:
                    raise ValidationError("monthlyOff は 6-12 の範囲である必要があります", "monthlyOff")
                validated["config"]["monthlyOff"] = mo
            except (ValueError, TypeError):
                raise ValidationError("monthlyOff は整数である必要があります", "monthlyOff")

    # dayDateOverrides（日付別オーバーライド）
    if isinstance(config, dict) and "dayDateOverrides" in config:
        ddo = config["dayDateOverrides"]
        if isinstance(ddo, dict):
            validated_ddo = {}
            for day_key, ovr in ddo.items():
                try:
                    dk = int(day_key)
                except (ValueError, TypeError):
                    continue
                if dk < 1 or dk > 31:
                    continue
                if not isinstance(ovr, dict):
                    continue
                validated_ovr = {}
                for field, hi in [("minQualified", 10), ("minAide", 10)]:
                    if field in ovr and ovr[field] is not None:
                        try:
                            v = int(ovr[field])
                        except (ValueError, TypeError):
                            raise ValidationError(f"dayDateOverrides.{day_key}.{field} は整数である必要があります")
                        if v < 0 or v > hi:
                            raise ValidationError(f"dayDateOverrides.{day_key}.{field} は0〜{hi}の範囲で指定してください")
                        validated_ovr[field] = v
                if validated_ovr:
                    validated_ddo[str(dk)] = validated_ovr
            validated["config"]["dayDateOverrides"] = validated_ddo

    # prevMonthData (そのまま渡す、各フィールドは使用時に検証)
    if "prevMonthData" in data:
        validated["prevMonthData"] = data["prevMonthData"]

    # fixedShifts
    if "fixedShifts" in data:
        validated["fixedShifts"] = data["fixedShifts"]

    # lockedShifts
    if "lockedShifts" in data:
        validated["lockedShifts"] = validate_locked_shifts(data["lockedShifts"])

    return validated


def validate_locked_shifts(locked_shifts):
    """lockedShiftsデータのバリデーション（flexRequest職員の手動シフト）

    フラット形式: {"staffId-day": "shift"}
    ネスト形式:   {"staffId": {"day": "shift"}}
    の両方をサポート。シフト値は VALID_SHIFTS のみ許可。
    """
    if not isinstance(locked_shifts, dict):
        raise ValidationError("lockedShifts は辞書である必要があります", "lockedShifts")
    validated = {}
    for key, val in locked_shifts.items():
        str_key = str(key)
        if isinstance(val, str):
            # フラット形式: "staffId-day": "shift"
            if val and val not in VALID_SHIFTS:
                raise ValidationError(f"lockedShifts に無効な shift が含まれています: {val}", "lockedShifts")
            validated[str_key] = val
        elif isinstance(val, dict):
            # ネスト形式: {staffId: {day: shift}}
            nested = {}
            for day_key, shift_val in val.items():
                if shift_val and shift_val not in VALID_SHIFTS:
                    raise ValidationError(f"lockedShifts に無効な shift が含まれています: {shift_val}", "lockedShifts")
                nested[str(day_key)] = shift_val
            validated[str_key] = nested
        # None や不明な型はスキップ
    return validated


def validate_ward_settings(settings):
    """病棟設定のバリデーション（範囲チェック付き）"""
    if not isinstance(settings, dict):
        raise ValidationError("settings は辞書である必要があります", "settings")

    validated = dict(settings)
    range_rules = {
        "reqDayWeekday": (0, 20, "平日日勤必要人数"),
        "reqDayHoliday": (0, 20, "休日日勤必要人数"),
        "reqJunnya": (0, 10, "準夜必要人数"),
        "reqShinya": (0, 10, "深夜必要人数"),
        "reqLate": (0, 10, "遅出必要人数"),
        "maxLate": (0, 10, "遅出上限人数"),
    }

    for key, (lo, hi, label) in range_rules.items():
        if key in settings:
            try:
                val = int(settings[key])
            except (ValueError, TypeError):
                raise ValidationError(f"{label}({key})は整数である必要があります", key)
            if val < lo or val > hi:
                raise ValidationError(f"{label}({key})は {lo}〜{hi} の範囲で指定してください（現在値: {val}）", key)
            validated[key] = val

    # 曜日別日勤人数（辞書型フィールド）
    valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    day_map_rules = {
        "dayStaffByDay": 20,
        "minQualifiedByDay": 10,
        "minAideByDay": 10,
    }
    for key, hi in day_map_rules.items():
        if key in settings:
            day_map = settings[key]
            if not isinstance(day_map, dict):
                raise ValidationError(f"{key} は辞書である必要があります", key)
            validated_map = {}
            for day_key, val in day_map.items():
                if day_key not in valid_days:
                    continue
                if val is None:
                    validated_map[day_key] = None
                else:
                    try:
                        v = int(val)
                    except (ValueError, TypeError):
                        raise ValidationError(f"{key}.{day_key} は整数またはnullである必要があります", key)
                    if v < 0 or v > hi:
                        raise ValidationError(f"{key}.{day_key} は0〜{hi}の範囲で指定してください", key)
                    validated_map[day_key] = v
            validated[key] = validated_map

    return validated


def validate_backup_data(data):
    """バックアップデータのバリデーション"""
    if not isinstance(data, dict):
        raise ValidationError("バックアップデータは辞書である必要があります")

    # 基本的なサイズチェック（10MBまで）
    data_str = json.dumps(data)
    if len(data_str) > 10 * 1024 * 1024:
        raise ValidationError("バックアップデータが大きすぎます（10MB以下）")

    return data


def validate_draft_name(name):
    """下書き名のバリデーション"""
    if not name:
        raise ValidationError("name は必須です", "name")
    if len(name) > 50:
        raise ValidationError("name は50文字以下である必要があります", "name")
    # 危険な文字のチェック（パストラバーサル防止含む）
    if re.search(r'[<>"\'/\\]', name):
        raise ValidationError("name に無効な文字が含まれています", "name")
    # ディレクトリトラバーサル防止
    if '..' in name or name.startswith('.') or name.startswith('~'):
        raise ValidationError("name に無効な文字列が含まれています", "name")
    return name


def is_localhost(request):
    """リクエストがlocalhostからかどうかをチェック"""
    remote_addr = request.remote_addr
    return remote_addr in ('127.0.0.1', '::1', 'localhost')


# ========== 従業員モデル変換ユーティリティ ==========
# バックエンド形式 (shiftCategory) がデータの正規形式
# フロントエンド形式 (workType) は表示用

# バックエンド形式 → フロントエンド形式
SHIFT_CATEGORY_TO_WORK_TYPE = {
    "twoShift": "2kohtai",
    "threeShift": "3kohtai",
    "dayOnly": "day_only",
    "nightOnly": "night_only",  # 夜勤専従
    "flexRequest": "fixed",  # flexRequest は fixed として扱う
}

# フロントエンド形式 → バックエンド形式
WORK_TYPE_TO_SHIFT_CATEGORY = {
    "2kohtai": "twoShift",
    "3kohtai": "threeShift",
    "day_only": "dayOnly",
    "night_only": "nightOnly",  # 夜勤専従
    "fixed": "flexRequest",  # fixed は flexRequest として保存
}

# 病棟ID変換
WARD_ID_TO_CODE = {
    "ichiboutou": "1",
    "nibyoutou": "2",
    "sanbyoutou": "3",
}

WARD_CODE_TO_ID = {
    "1": "ichiboutou",
    "2": "nibyoutou",
    "3": "sanbyoutou",
}


def convert_shift_category_to_work_type(shift_category):
    """バックエンド形式(shiftCategory)からフロントエンド形式(workType)に変換"""
    return SHIFT_CATEGORY_TO_WORK_TYPE.get(shift_category, "2kohtai")


def convert_work_type_to_shift_category(work_type):
    """フロントエンド形式(workType)からバックエンド形式(shiftCategory)に変換"""
    return WORK_TYPE_TO_SHIFT_CATEGORY.get(work_type, "twoShift")


def convert_ward_id_to_code(ward_id):
    """バックエンド病棟ID(ichiboutou等)からフロントエンド病棟コード(1,2,3)に変換"""
    return WARD_ID_TO_CODE.get(ward_id, ward_id)


def convert_ward_code_to_id(ward_code):
    """フロントエンド病棟コード(1,2,3)からバックエンド病棟ID(ichiboutou等)に変換"""
    return WARD_CODE_TO_ID.get(str(ward_code), str(ward_code))


def employee_to_frontend(emp):
    """
    バックエンド従業員データをフロントエンド形式に変換

    バックエンド形式 (employees.json):
    {
        "id": "123",
        "name": "田中",
        "ward": "nibyoutou",
        "shiftCategory": "twoShift",
        "type": "nurse",
        "personalRules": {...}
    }

    フロントエンド形式:
    {
        "id": "123",
        "name": "田中",
        "ward": "2",
        "workType": "2kohtai",
        "type": "nurse",
        "maxNight": 5
    }
    """
    personal_rules = emp.get("personalRules", {})

    frontend = {
        "id": emp.get("id"),
        "name": emp.get("name"),
        "ward": convert_ward_id_to_code(emp.get("ward", "nibyoutou")),
        "type": emp.get("type", "nurse"),
        "workType": convert_shift_category_to_work_type(emp.get("shiftCategory", "twoShift")),
        "maxNight": personal_rules.get("nightShift", {}).get("maxPerMonth", 5),
    }

    # minNightは明示的に設定されている場合のみ含める（未設定ならソルバーデフォルトを使用）
    min_per_month = personal_rules.get("nightShift", {}).get("minPerMonth")
    if min_per_month is not None:
        frontend["minNight"] = min_per_month

    # nightRestriction がある場合は追加
    night_restriction = personal_rules.get("nightRestriction")
    if night_restriction:
        frontend["nightRestriction"] = night_restriction

    # fixedPattern（固定シフトパターン）がある場合は保持
    if "fixedPattern" in emp:
        frontend["fixedPattern"] = emp["fixedPattern"]

    return frontend


def validate_actual_change(data):
    """実績変更データのバリデーション"""
    if not isinstance(data, dict):
        raise ValidationError("変更データは辞書である必要があります")

    validated = {}
    validated["staffId"] = validate_staff_id(data.get("staffId"))

    day = data.get("day")
    if not isinstance(day, int):
        try:
            day = int(day)
        except (ValueError, TypeError):
            raise ValidationError("day は整数である必要があります", "day")
    if day < 1 or day > 31:
        raise ValidationError("day は 1-31 の範囲である必要があります", "day")
    validated["day"] = day

    to_shift = data.get("to", "")
    if to_shift:
        validated["to"] = validate_shift(to_shift)
    else:
        validated["to"] = ""

    reason = data.get("reason", "")
    if len(reason) > 200:
        raise ValidationError("reason は200文字以下である必要があります", "reason")
    if '<' in reason or '>' in reason:
        raise ValidationError("reason に無効な文字が含まれています", "reason")
    validated["reason"] = reason

    return validated


def frontend_to_employee(staff):
    """
    フロントエンド職員データをバックエンド従業員形式に変換

    フロントエンド形式:
    {
        "id": "123",
        "name": "田中",
        "ward": "2",
        "workType": "2kohtai",
        "type": "nurse",
        "maxNight": 5
    }

    バックエンド形式 (employees.json):
    {
        "id": "123",
        "name": "田中",
        "ward": "nibyoutou",
        "shiftCategory": "twoShift",
        "type": "nurse",
        "personalRules": {...}
    }
    """
    work_type = staff.get('workType', '2kohtai')
    max_night = staff.get('maxNight', 5)
    min_night = staff.get('minNight', 0)

    # fixed/flexRequest の場合は夜勤0
    if work_type in ('fixed', 'day_only'):
        max_night = 0
        min_night = 0

    night_shift_rules = {"maxPerMonth": max_night}
    if min_night > 0:
        night_shift_rules["minPerMonth"] = min_night

    employee = {
        "id": str(staff.get('id', '')),
        "name": staff.get('name', ''),
        "ward": convert_ward_code_to_id(staff.get('ward', '2')),
        "shiftCategory": convert_work_type_to_shift_category(work_type),
        "type": staff.get('type', 'nurse'),
        "personalRules": {
            "nightShift": night_shift_rules,
            "dayOff": {"minPerMonth": 9},
            "consecutive": {"maxWorkDays": 5},
            "ngPartner": []
        }
    }

    # 夜勤制限がある場合は追加
    night_restriction = staff.get('nightRestriction')
    if night_restriction:
        employee['personalRules']['nightRestriction'] = night_restriction

    return employee
