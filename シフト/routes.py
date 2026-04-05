"""
Sakigake Shift - APIエンドポイント（コーディネータ）
各機能モジュールからルートを登録する
"""
import os
import re
import calendar
import json as pyjson
import logging
import threading
import time
from datetime import date, datetime, timedelta
from flask import jsonify

from validation import WARD_CODE_TO_ID, WARD_ID_TO_CODE

logger = logging.getLogger(__name__)

# シフト略称マップ（PDF出力・CSV出力で共用）
SHIFT_ABBR = {
    "day": "日", "late": "遅", "night2": "夜",
    "junnya": "準", "shinya": "深", "off": "休", "paid": "有",
    "ake": "明", "refresh": "リ",
}

_REST_TYPES = {"off", "paid", "refresh"}  # akeは夜勤の一部であり休日ではない


def atomic_json_write(filepath, data):
    """アトミック書き込み: 一時ファイルに書き込み後リネーム（クラッシュ安全）"""
    tmp = filepath + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        pyjson.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, filepath)


def _safe_exit():
    """atexit/logging を実行してからプロセス終了（os._exitの安全なラッパー）"""
    import atexit
    atexit._run_exitfuncs()
    logging.shutdown()
    os._exit(0)


def _supplement_transfer_prevdata(staff_list, ward_code, year, month, prev_month_data):
    """異動職員の前月引継ぎデータを旧病棟の確定シフトから補完する。

    prevMonthDataに含まれていない職員で、transferHistoryに当病棟への転入記録がある場合、
    旧病棟の前月シフトから lastDay / consecutiveWork 等を計算して補完する。
    """
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    missing_ids = {s["id"] for s in staff_list if s["id"] not in prev_month_data}
    if not missing_ids:
        return prev_month_data

    threshold = f"{prev_year}-{prev_month:02d}-01"
    current_ward_id = WARD_CODE_TO_ID.get(ward_code, ward_code)

    employees_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared", "employees.json")
    try:
        with open(employees_path, "r", encoding="utf-8") as f:
            employees = pyjson.load(f)
    except (OSError, IOError, pyjson.JSONDecodeError):
        return prev_month_data

    result = dict(prev_month_data)
    prev_days = calendar.monthrange(prev_year, prev_month)[1]

    shifts_dir = os.path.join(os.path.dirname(__file__), "shifts")
    prev_shift_file = f"{prev_year}-{prev_month:02d}.json"
    ward_shift_cache = {}

    def _load_ward_shifts(ward_id):
        if ward_id in ward_shift_cache:
            return ward_shift_cache[ward_id]
        filepath = os.path.join(shifts_dir, ward_id, prev_shift_file)
        if not os.path.exists(filepath):
            ward_shift_cache[ward_id] = None
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                ward_shift_cache[ward_id] = pyjson.load(f)
        except (OSError, IOError, pyjson.JSONDecodeError):
            ward_shift_cache[ward_id] = None
        return ward_shift_cache[ward_id]

    def _extract_staff_shifts(shift_data, staff_id):
        """確定 or 選択済みドラフトからスタッフのシフトを取得"""
        if shift_data.get("status") == "confirmed" and shift_data.get("confirmed"):
            s = shift_data["confirmed"]["shifts"].get(staff_id)
            if s:
                return s
        selected = shift_data.get("selectedDraft")
        if selected and selected in shift_data.get("drafts", {}):
            return shift_data["drafts"][selected]["shifts"].get(staff_id)
        return None

    def _calc_prev_stats(staff_shifts, prev_days):
        """前月シフトから引継ぎ統計を計算"""
        last_day = staff_shifts.get(str(prev_days), "")
        second_last = staff_shifts.get(str(prev_days - 1), "")
        c_work = 0
        for k in range(10):
            d = prev_days - k
            if d < 1:
                break
            sh = staff_shifts.get(str(d), "")
            if not sh or sh in _REST_TYPES:
                break
            c_work += 1
        c_jun = 0
        for k in range(10):
            d = prev_days - k
            if d < 1:
                break
            sh = staff_shifts.get(str(d), "")
            if not sh or sh != "junnya":
                break
            c_jun += 1
        c_off = 0
        for k in range(10):
            d = prev_days - k
            if d < 1:
                break
            sh = staff_shifts.get(str(d), "")
            if not sh or sh not in _REST_TYPES:
                break
            c_off += 1
        if last_day or second_last or c_work > 0 or c_jun > 0 or c_off > 0:
            return {
                "lastDay": last_day,
                "secondLastDay": second_last,
                "consecutiveWork": c_work,
                "consecutiveJunnya": c_jun,
                "consecutiveOff": c_off,
            }
        return None

    still_missing = set(missing_ids)

    # Phase 1: transferHistory がある職員を旧病棟から補完
    for emp in employees:
        staff_id = emp["id"]
        if staff_id not in still_missing:
            continue
        for h in sorted(emp.get("transferHistory", []), key=lambda x: x.get("date", ""), reverse=True):
            if h.get("to") != current_ward_id:
                continue
            if h.get("date", "") < threshold:
                break
            from_ward_id = h.get("from", "")
            if from_ward_id not in WARD_ID_TO_CODE:
                break
            shift_data = _load_ward_shifts(from_ward_id)
            if not shift_data:
                break
            staff_shifts = _extract_staff_shifts(shift_data, staff_id)
            if not staff_shifts:
                break
            stats = _calc_prev_stats(staff_shifts, prev_days)
            if stats:
                result[staff_id] = stats
                still_missing.discard(staff_id)
            break

    # Phase 2: まだ見つからない職員は全病棟を検索
    if still_missing:
        all_ward_ids = [w for w in WARD_ID_TO_CODE if w != current_ward_id]
        for ward_id in all_ward_ids:
            shift_data = _load_ward_shifts(ward_id)
            if not shift_data:
                continue
            for staff_id in list(still_missing):
                staff_shifts = _extract_staff_shifts(shift_data, staff_id)
                if not staff_shifts:
                    continue
                stats = _calc_prev_stats(staff_shifts, prev_days)
                if stats:
                    result[staff_id] = stats
                    still_missing.discard(staff_id)
            if not still_missing:
                break

    return result


def _error_response(message, status_code=500, field=None):
    """統一エラーレスポンスを生成（内部情報の漏洩を防止）"""
    body = {"status": "error", "message": message}
    if field:
        body["field"] = field
    return jsonify(body), status_code


def _safe_internal_error(e, context=""):
    """内部エラーをログに記録し、安全なレスポンスを返す"""
    logger.exception("内部エラー [%s]: %s", context, e)
    return _error_response("サーバー内部エラーが発生しました")


def _run_daily_backup(backup_dir, daily_dir):
    """日次バックアップ実行: backup_latest.json → daily/daily_YYYY-MM-DD.json"""
    try:
        latest = os.path.join(backup_dir, "backup_latest.json")
        if not os.path.exists(latest):
            return
        today_str = date.today().isoformat()
        daily_file = os.path.join(daily_dir, f"daily_{today_str}.json")
        if os.path.exists(daily_file):
            return  # 同日バックアップ済み
        import shutil
        shutil.copy2(latest, daily_file)
        _cleanup_daily_backups(daily_dir)
        logger.info("日次バックアップ完了: %s", daily_file)
    except Exception as e:
        logger.exception("日次バックアップエラー: %s", e)


def _cleanup_daily_backups(daily_dir):
    """30日超の日次バックアップを削除（月初分は12ヶ月保持）"""
    today = date.today()
    for f in os.listdir(daily_dir):
        m = re.match(r"daily_(\d{4}-\d{2}-\d{2})\.json", f)
        if not m:
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        age_days = (today - d).days
        if age_days <= 30:
            continue
        if d.day == 1 and age_days <= 365:
            continue
        try:
            os.remove(os.path.join(daily_dir, f))
        except OSError:
            pass


def start_daily_backup(backup_dir):
    """日次バックアップスレッド起動（AM3:00に実行）"""
    daily_dir = os.path.join(backup_dir, "daily")
    os.makedirs(daily_dir, exist_ok=True)

    # 起動時に当日分がなければ即実行
    _run_daily_backup(backup_dir, daily_dir)

    def _backup_loop():
        while True:
            now = datetime.now()
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            sleep_sec = (next_run - now).total_seconds()
            time.sleep(sleep_sec)
            _run_daily_backup(backup_dir, daily_dir)

    t = threading.Thread(target=_backup_loop, daemon=True)
    t.start()
    logger.info("日次バックアップスレッド起動（次回: AM3:00）")


def register_routes(app, BACKUP_DIR, portal_mode=False):
    """Flaskアプリにルートを登録（各サブモジュールに委譲）"""

    from routes_solver import register_solver_routes
    from routes_backup import register_backup_routes
    from routes_export import register_export_routes
    from routes_shift import register_shift_routes
    from routes_actual import register_actual_routes

    register_solver_routes(app, _supplement_transfer_prevdata, _error_response, _safe_internal_error)
    register_backup_routes(app, BACKUP_DIR, atomic_json_write, _error_response, _safe_internal_error, _safe_exit, portal_mode)
    register_export_routes(app, SHIFT_ABBR, _error_response, _safe_internal_error)
    register_shift_routes(app, atomic_json_write, _error_response, _safe_internal_error, portal_mode)
    register_actual_routes(app, atomic_json_write, _error_response, _safe_internal_error)
