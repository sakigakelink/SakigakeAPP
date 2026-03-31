"""
Sakigake Shift - APIエンドポイント
"""
import os
import re
import sys
import time
import calendar
import json as pyjson
import logging
import subprocess
import tempfile
import threading
from datetime import date, datetime, timedelta
from flask import Response, request, jsonify, send_file, render_template, stream_with_context
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from io import BytesIO

from solver import ShiftSolver
from utils import HOLIDAYS
from shift_quality import check_labor_law_compliance
from validation import (
    ValidationError, validate_year, validate_month, validate_ward,
    validate_staff_id, validate_staff_name, validate_shift_category,
    validate_staff_type, validate_max_night, validate_solve_request,
    validate_backup_data, validate_draft_name, validate_actual_change,
    validate_ward_settings,
    is_localhost,
    employee_to_frontend, frontend_to_employee,
    convert_ward_code_to_id, convert_ward_id_to_code,
    WARD_CODE_TO_ID, WARD_ID_TO_CODE,
)

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

    employees_path = os.path.join(os.path.dirname(__file__), "shared", "employees.json")
    try:
        with open(employees_path, "r", encoding="utf-8") as f:
            employees = pyjson.load(f)
    except (OSError, IOError, pyjson.JSONDecodeError):
        return prev_month_data

    result = dict(prev_month_data)
    prev_days = calendar.monthrange(prev_year, prev_month)[1]

    # 全病棟の前月シフトデータを読み込み（必要に応じて）
    shifts_dir = os.path.join(os.path.dirname(__file__), "shifts")
    prev_shift_file = f"{prev_year}-{prev_month:02d}.json"
    ward_shift_cache = {}  # ward_id -> shift_data

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
    """Flaskアプリにルートを登録"""

    @app.route("/solve", methods=["POST"])
    def solve_route():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400
            validated_data = validate_solve_request(data)
            # 元のデータにバリデーション済みフィールドをマージ
            data.update(validated_data)
            # maxNight補正はShiftSolver.__init__内で実施（employees.json読込は1回のみ）
            # 異動職員の前月引継ぎデータを旧病棟から補完
            ward_code = data.get("config", {}).get("ward", "")
            if ward_code:
                data["prevMonthData"] = _supplement_transfer_prevdata(
                    data.get("staff", []),
                    ward_code,
                    data.get("year", 0),
                    data.get("month", 0),
                    data.get("prevMonthData", {}),
                )
            return jsonify(ShiftSolver(data).solve())
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except Exception as e:
            return _safe_internal_error(e, "solve")

    @app.route("/solve-stream", methods=["POST"])
    def solve_stream():
        """SSEでソルバー進捗をストリーミング（効率化版）"""

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

        # 基本バリデーション（ストリーミング前に検証）
        try:
            validated_data = validate_solve_request(data)
            data.update(validated_data)
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)

        # maxNight補正はShiftSolver.__init__内で実施（employees.json読込は1回のみ）

        # 固定シフト職員: 希望入力（assign）をfixedShiftsにマージ
        # 直接入力と希望入力どちらで入れても同等に扱う
        fixed_staff_list = [s for s in data.get("staff", []) if s.get("workType") == "fixed"]
        if fixed_staff_list:
            fixed_ids = {s["id"] for s in fixed_staff_list}
            merged_fixed = {
                k: dict(v) if isinstance(v, dict) else v
                for k, v in data.get("fixedShifts", {}).items()
            }
            for w in data.get("wishes", []):
                if w.get("staffId") in fixed_ids and w.get("type") == "assign":
                    sid = w["staffId"]
                    sh = w.get("shift")
                    if not sh:
                        continue
                    if not isinstance(merged_fixed.get(sid), dict):
                        merged_fixed[sid] = {}
                    for day in w.get("days", []):
                        merged_fixed[sid][str(day)] = sh
            data["fixedShifts"] = merged_fixed

            # 全日入力チェック（直接入力＋希望入力のマージ後で判定）
            num_days_check = calendar.monthrange(data.get("year", 2026), data.get("month", 1))[1]
            incomplete_fixed = []
            for fs in fixed_staff_list:
                if fs.get("fixedPattern"):
                    continue  # 曜日パターンあり → 全日算出可能
                staff_id = fs["id"]
                staff_shifts = merged_fixed.get(str(staff_id), merged_fixed.get(staff_id, {}))
                if not isinstance(staff_shifts, dict):
                    staff_shifts = {}
                missing_days = [d for d in range(1, num_days_check + 1)
                                if not staff_shifts.get(str(d)) and not staff_shifts.get(d)]
                if missing_days:
                    incomplete_fixed.append({"name": fs.get("name", str(staff_id)), "missing": len(missing_days)})
            if incomplete_fixed:
                names = ", ".join(f"{x['name']}({x['missing']}日未入力)" for x in incomplete_fixed)
                return _error_response(f"固定シフト職員のシフトが未入力です: {names}", 400)

        # 異動職員の前月引継ぎデータを旧病棟から補完
        ward_code = data.get("config", {}).get("ward", "")
        if ward_code:
            data["prevMonthData"] = _supplement_transfer_prevdata(
                data.get("staff", []),
                ward_code,
                data.get("year", 0),
                data.get("month", 0),
                data.get("prevMonthData", {}),
            )

        solve_mode = data.get("config", {}).get("solveMode", "quick")

        # 全職員マスタを診断メッセージ用に追加（ID→名前解決）
        try:
            emp_path = os.path.join(os.path.dirname(__file__), "shared", "employees.json")
            with open(emp_path, "r", encoding="utf-8") as f:
                data["allEmployees"] = pyjson.load(f)
        except Exception:
            data["allEmployees"] = []

        def generate():
            cfg = data.get("config", {})
            num_cores = os.cpu_count() or 4

            # 職員数を事前計算（サブプロセス起動前のinfo表示用）
            staff = data.get("staff", [])
            solver_staff = [s for s in staff if s.get("workType") not in ("fixed", "flexRequest")]
            fixed_staff = [s for s in staff if s.get("workType") == "fixed"]
            flex_staff = [s for s in staff if s.get("workType") == "flexRequest"]
            num_staff = len(solver_staff)
            num_days = calendar.monthrange(data.get("year", 2026), data.get("month", 1))[1]

            # モード別の表示
            mode_labels = {
                "quick": "⚡通常（15秒）",
                "balanced": "⚡バランス（45秒）",
                "quality": "💎品質重視（90秒）",
                "pool": "🎯複数案生成（50秒）",
            }
            mode_label = mode_labels.get(solve_mode, "⚡通常（15秒）")

            # 初期情報
            monthly_off_val = cfg.get('monthlyOff', '?')
            month_val = data.get('month', '?')
            yield f"data: {pyjson.dumps({'type': 'info', 'msg': f'職員{num_staff}名、{num_days}日間（{num_cores}コア）- {mode_label}【公休{monthly_off_val}日/月={month_val}】'})}\n\n"

            yield f"data: {pyjson.dumps({'type': 'attempt', 'num': 1, 'msg': '厳密解法で開始（制約緩和なし）'})}\n\n"

            # サブプロセスでソルバー実行（OR-Tools C++ abort隔離）
            total_start = time.time()
            solver_script = os.path.join(os.path.dirname(__file__), "solver_subprocess.py")
            input_json = pyjson.dumps(data, ensure_ascii=False).encode("utf-8")

            # 結果ファイル（stdout汚染を回避するためファイル経由で受け渡し）
            result_fd, result_path = tempfile.mkstemp(suffix=".json", prefix="solver_result_")
            os.close(result_fd)

            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW
                # stderrはDEVNULL（バッファ溢れによるデッドロック防止）
                # クラッシュ時はresult_path不在＋returncodeで検知
                proc = subprocess.Popen(
                    [sys.executable, solver_script, result_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    cwd=os.path.dirname(__file__),
                    env=env,
                    creationflags=creation_flags,
                )
                def _feed_stdin(p, data_bytes):
                    try:
                        p.stdin.write(data_bytes)
                        p.stdin.close()
                    except Exception:
                        pass
                feeder = threading.Thread(target=_feed_stdin, args=(proc, input_json), daemon=True)
                feeder.start()
            except Exception as e:
                logger.exception("ソルバーサブプロセス起動失敗: %s", e)
                yield f"data: {pyjson.dumps({'type': 'error', 'msg': f'ソルバー起動失敗: {e}'})}\n\n"
                yield f"data: {pyjson.dumps({'type': 'result', 'data': {'status': 'error', 'message': str(e)}})}\n\n"
                try:
                    os.unlink(result_path)
                except Exception:
                    pass
                return

            res = None
            try:
                # stdoutからJSONLを逐次読み取り（進捗メッセージのみ）
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        msg = pyjson.loads(line)
                    except pyjson.JSONDecodeError:
                        continue

                    msg_type = msg.get("type")
                    if msg_type == "progress":
                        yield f"data: {pyjson.dumps({'type': 'progress', 'obj': msg.get('obj'), 'time': msg.get('time'), 'improvement': msg.get('improvement'), 'solutions': msg.get('solutions')})}\n\n"
                    elif msg_type == "log":
                        yield f"data: {pyjson.dumps({'type': 'attempt', 'num': 0, 'msg': msg.get('msg', '')})}\n\n"

                proc.wait(timeout=120)
            except Exception as e:
                logger.exception("ソルバーサブプロセス読み取りエラー: %s", e)
                try:
                    proc.kill()
                except Exception:
                    pass

            # 結果ファイルから読み取り
            try:
                with open(result_path, "r", encoding="utf-8") as rf:
                    res = pyjson.load(rf)
            except Exception as e:
                logger.error("結果ファイル読み取り失敗: %s", e)
            finally:
                try:
                    os.unlink(result_path)
                except Exception:
                    pass

            # プロセスがクラッシュして結果ファイルもない場合
            if res is None:
                logger.error("ソルバーサブプロセス失敗 (code=%s)", proc.returncode)
                res = {"status": "error", "message": "ソルバーが異常終了しました。OR-Toolsの内部エラーの可能性があります。"}

            total_elapsed = round(time.time() - total_start, 2)

            if res and res.get("status", "").lower() == "pool":
                # 解プールモード: 複数案を返す
                count = res.get("count", 0)
                res["totalTime"] = total_elapsed
                # 労基法コンプライアンスチェック（各案に付加）
                for ver in res.get("versions", []):
                    try:
                        ver["labor_compliance"] = check_labor_law_compliance(ver, data)
                    except Exception:
                        pass
                quality_msg = f"{count}案を生成しました ({total_elapsed}秒)"
                if res.get("sensitivity"):
                    quality_msg += f" + 感度分析{len(res['sensitivity'])}件"
                yield f"data: {pyjson.dumps({'type': 'success', 'msg': quality_msg})}\n\n"
                yield f"data: {pyjson.dumps({'type': 'result', 'data': res})}\n\n"
                return
            elif res and res.get("status", "").lower() in ["optimal", "feasible"]:
                attempt_num = res.get("attempt", 1)
                res["totalTime"] = total_elapsed
                # 労基法コンプライアンスチェック
                try:
                    res["labor_compliance"] = check_labor_law_compliance(res, data)
                except Exception:
                    pass
                completeness = res.get("completeness", "feasible")
                if completeness == "optimal":
                    quality_msg = f"試行{attempt_num}で最適解を発見 ({total_elapsed}秒)"
                else:
                    quality_msg = f"試行{attempt_num}で実行可能解を発見 ({total_elapsed}秒) ※タイムアウトにより最適解ではない可能性があります"
                yield f"data: {pyjson.dumps({'type': 'success', 'msg': quality_msg})}\n\n"
                yield f"data: {pyjson.dumps({'type': 'result', 'data': res})}\n\n"
                return
            else:
                err_msg = (res.get("message") if res else None) or '解が見つかりません'
                yield f"data: {pyjson.dumps({'type': 'error', 'msg': f'全試行失敗: {err_msg}（合計{total_elapsed}秒）'})}\n\n"
                yield f"data: {pyjson.dumps({'type': 'result', 'data': res or {'status': 'infeasible', 'message': err_msg}})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    # === バックアップAPI ===
    @app.route("/api/backup", methods=["POST"])
    def backup_save():
        """データをサーバーにバックアップ保存"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "データがありません"}), 400

            # バリデーション
            try:
                validate_backup_data(data)
            except ValidationError as e:
                return jsonify({"status": "error", "message": e.message}), 400

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # タイムスタンプ付きファイルに保存
            backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
            atomic_json_write(backup_file, data)

            # 最新版を上書き保存
            latest_file = os.path.join(BACKUP_DIR, "backup_latest.json")
            atomic_json_write(latest_file, data)

            # 書き込み検証（最新バックアップが正しく読めることを確認）
            with open(latest_file, 'r', encoding='utf-8') as f:
                pyjson.load(f)  # JSONDecodeErrorなら例外→エラー応答

            # 古いバックアップを削除（最新10件のみ保持）
            files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f != "backup_latest.json"], reverse=True)
            for old_file in files[10:]:
                os.remove(os.path.join(BACKUP_DIR, old_file))

            return jsonify({"status": "success", "file": backup_file, "timestamp": timestamp})
        except (OSError, IOError) as e:
            logger.exception("バックアップ保存エラー: %s", e)
            return _error_response("バックアップの保存に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "backup_save")

    @app.route("/api/backup/load", methods=["GET"])
    def backup_load():
        """最新バックアップを読み込み"""
        try:
            latest_file = os.path.join(BACKUP_DIR, "backup_latest.json")
            if os.path.exists(latest_file):
                with open(latest_file, "r", encoding="utf-8") as f:
                    data = pyjson.load(f)
                mtime = os.path.getmtime(latest_file)
                timestamp = datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
                return jsonify({"status": "success", "data": data, "timestamp": timestamp})
            else:
                return jsonify({"status": "empty", "message": "バックアップがありません"})
        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("バックアップ読み込みエラー: %s", e)
            return _error_response("バックアップの読み込みに失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "backup_load")

    @app.route("/api/backup/list", methods=["GET"])
    def backup_list():
        """バックアップ一覧を取得"""
        try:
            files = []
            for f in os.listdir(BACKUP_DIR):
                if f.startswith("backup_") and f.endswith(".json") and f != "backup_latest.json":
                    filepath = os.path.join(BACKUP_DIR, f)
                    mtime = os.path.getmtime(filepath)
                    files.append({
                        "filename": f,
                        "timestamp": datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S"),
                        "size": os.path.getsize(filepath)
                    })
            files.sort(key=lambda x: x["timestamp"], reverse=True)
            return jsonify({"status": "success", "files": files})
        except (OSError, IOError) as e:
            logger.exception("バックアップ一覧エラー: %s", e)
            return _error_response("バックアップ一覧の取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "backup_list")

    # === 日次バックアップAPI ===
    @app.route("/api/backup/daily/list", methods=["GET"])
    def daily_backup_list():
        """日次バックアップ一覧"""
        try:
            daily_dir = os.path.join(BACKUP_DIR, "daily")
            if not os.path.isdir(daily_dir):
                return jsonify({"status": "success", "files": []})
            files = []
            for f in sorted(os.listdir(daily_dir), reverse=True):
                if not f.startswith("daily_") or not f.endswith(".json"):
                    continue
                filepath = os.path.join(daily_dir, f)
                m = re.match(r"daily_(\d{4}-\d{2}-\d{2})\.json", f)
                files.append({
                    "filename": f,
                    "date": m.group(1) if m else "",
                    "size": os.path.getsize(filepath),
                })
            return jsonify({"status": "success", "files": files, "count": len(files)})
        except Exception as e:
            return _safe_internal_error(e, "daily_backup_list")

    @app.route("/api/backup/daily/info", methods=["GET"])
    def daily_backup_info():
        """日次バックアップ概要（バックアップ状態表示用）"""
        try:
            daily_dir = os.path.join(BACKUP_DIR, "daily")
            if not os.path.isdir(daily_dir):
                return jsonify({"count": 0, "latest": None})
            files = sorted([f for f in os.listdir(daily_dir)
                            if f.startswith("daily_") and f.endswith(".json")], reverse=True)
            latest = None
            if files:
                m = re.match(r"daily_(\d{4}-\d{2}-\d{2})\.json", files[0])
                if m:
                    latest = m.group(1)
            return jsonify({"count": len(files), "latest": latest})
        except Exception as e:
            return _safe_internal_error(e, "daily_backup_info")

    # === 病棟設定API ===
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "shared", "ward_settings.json")

    @app.route("/api/settings/ward", methods=["GET"])
    def get_ward_settings():
        """病棟設定を取得"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = pyjson.load(f)
                return jsonify({"status": "success", "data": data})
            else:
                return jsonify({"status": "success", "data": {}})
        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("病棟設定取得エラー: %s", e)
            return _error_response("病棟設定の取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_ward_settings")

    @app.route("/api/settings/ward", methods=["POST"])
    def save_ward_settings():
        """病棟設定を保存"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "データがありません"}), 400

            # 既存の設定を読み込み
            existing = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    existing = pyjson.load(f)

            # マージして保存
            ward_id = data.get("wardId")
            settings = data.get("settings", {})
            if ward_id:
                try:
                    ward_id = validate_ward(ward_id)
                except ValidationError as e:
                    return jsonify({"status": "error", "message": e.message}), 400
                if not isinstance(settings, dict):
                    return jsonify({"status": "error", "message": "settings は辞書である必要があります"}), 400
                try:
                    settings = validate_ward_settings(settings)
                except ValidationError as e:
                    return jsonify({"status": "error", "message": e.message}), 400
                existing[ward_id] = settings

            atomic_json_write(SETTINGS_FILE, existing)

            return jsonify({"status": "success"})
        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("病棟設定保存エラー: %s", e)
            return _error_response("病棟設定の保存に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "save_ward_settings")

    # === 設定エクスポート/インポートAPI ===
    SHARED_DIR = os.path.join(os.path.dirname(__file__), "shared")
    HOLIDAYS_FILE = os.path.join(os.path.dirname(__file__), "holidays.json")

    @app.route("/api/settings/export", methods=["POST"])
    def export_settings():
        """全設定を1つのJSONとしてエクスポート"""
        try:
            export_data = {
                "exportedAt": datetime.now().isoformat(),
                "version": "1.0",
                "employees": [],
                "wardSettings": {},
                "holidays": [],
            }

            emp_path = os.path.join(SHARED_DIR, "employees.json")
            if os.path.exists(emp_path):
                with open(emp_path, "r", encoding="utf-8") as f:
                    export_data["employees"] = pyjson.load(f)

            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    export_data["wardSettings"] = pyjson.load(f)

            if os.path.exists(HOLIDAYS_FILE):
                with open(HOLIDAYS_FILE, "r", encoding="utf-8") as f:
                    export_data["holidays"] = pyjson.load(f)

            return jsonify(export_data)
        except Exception as e:
            return _safe_internal_error(e, "export_settings")

    @app.route("/api/settings/import", methods=["POST"])
    def import_settings():
        """エクスポートJSONから設定を復元"""
        try:
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify({"status": "error", "message": "無効なデータ"}), 400

            version = data.get("version", "")
            if not version.startswith("1."):
                return jsonify({"status": "error", "message": f"未対応のバージョン: {version}"}), 400

            employees = data.get("employees")
            ward_settings = data.get("wardSettings")
            holidays = data.get("holidays")

            if employees is not None and not isinstance(employees, list):
                return jsonify({"status": "error", "message": "employees は配列である必要があります"}), 400
            if ward_settings is not None and not isinstance(ward_settings, dict):
                return jsonify({"status": "error", "message": "wardSettings は辞書である必要があります"}), 400

            # インポート前バックアップ
            pre_backup_dir = os.path.join(SHARED_DIR, "pre_import_backup")
            os.makedirs(pre_backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            restored = []

            if employees is not None:
                emp_path = os.path.join(SHARED_DIR, "employees.json")
                if os.path.exists(emp_path):
                    import shutil
                    shutil.copy2(emp_path, os.path.join(pre_backup_dir, f"employees_{timestamp}.json"))
                atomic_json_write(emp_path, employees)
                restored.append(f"職員データ({len(employees)}件)")

            if ward_settings is not None:
                if os.path.exists(SETTINGS_FILE):
                    import shutil
                    shutil.copy2(SETTINGS_FILE, os.path.join(pre_backup_dir, f"ward_settings_{timestamp}.json"))
                atomic_json_write(SETTINGS_FILE, ward_settings)
                restored.append(f"病棟設定({len(ward_settings)}病棟)")

            if holidays is not None and isinstance(holidays, list):
                if os.path.exists(HOLIDAYS_FILE):
                    import shutil
                    shutil.copy2(HOLIDAYS_FILE, os.path.join(pre_backup_dir, f"holidays_{timestamp}.json"))
                atomic_json_write(HOLIDAYS_FILE, holidays)
                restored.append("祝日データ")

            msg = "インポート完了: " + "、".join(restored) if restored else "インポート対象がありません"
            return jsonify({"status": "success", "message": msg})
        except (pyjson.JSONDecodeError, OSError) as e:
            logger.exception("設定インポートエラー: %s", e)
            return _error_response("設定のインポートに失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "import_settings")

    if not portal_mode:
        @app.route("/api/shutdown", methods=["POST"])
        def shutdown():
            """サーバーを終了（localhost からのみ許可）"""
            if not is_localhost(request):
                return jsonify({"status": "error", "message": "この操作は許可されていません"}), 403

            def shutdown_server():
                time.sleep(0.5)
                os._exit(0)

            threading.Thread(target=shutdown_server).start()
            return jsonify({"status": "success", "message": "サーバーを終了します"})

        @app.route("/api/restart", methods=["POST"])
        def restart():
            """サーバーを再起動（localhost からのみ許可）"""
            if not is_localhost(request):
                return jsonify({"status": "error", "message": "この操作は許可されていません"}), 403

            def restart_server():
                time.sleep(0.5)
                subprocess.Popen(
                    [sys.executable] + sys.argv,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                time.sleep(0.3)
                os._exit(0)

            threading.Thread(target=restart_server).start()
            return jsonify({"status": "success", "message": "サーバーを再起動します"})

    @app.route("/export_json", methods=["POST"])
    def export_json():
        """シフトデータをJSON形式でエクスポート（Antigravity分析用）"""
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

        # バリデーション
        try:
            year = validate_year(data.get("year"))
            month = validate_month(data.get("month"))
        except (ValidationError, TypeError) as e:
            msg = e.message if hasattr(e, 'message') else 'year, month が必要です'
            return jsonify({"status": "error", "message": msg}), 400

        staff_data = data.get("staff", [])
        if not isinstance(staff_data, list):
            return jsonify({"status": "error", "message": "staff は配列である必要があります"}), 400

        shifts = data.get("shifts", {})
        wishes = data.get("wishes", [])

        num_days = calendar.monthrange(year, month)[1]

        abbr = SHIFT_ABBR

        export_data = {
            "year": year,
            "month": month,
            "numDays": num_days,
            "exportedAt": date.today().isoformat(),
            "staff": []
        }

        for s in staff_data:
            staff_shifts = []
            stats = {"day": 0, "night": 0, "off": 0, "consecutive_work_max": 0}
            consecutive = 0

            for d in range(1, num_days + 1):
                key = f"{s['id']}-{d}"
                sh = shifts.get(key, "")
                staff_shifts.append({"day": d, "shift": sh, "abbr": abbr.get(sh, sh)})

                # 統計計算
                if sh in ["day", "late"]:
                    stats["day"] += 1
                if sh in ["night2", "junnya", "shinya"]:
                    stats["night"] += 1
                if sh in ["off", "paid", "refresh"]:
                    stats["off"] += 1

                # 連続勤務計算
                if sh and sh not in ["off", "paid", "refresh", "ake"]:
                    consecutive += 1
                    stats["consecutive_work_max"] = max(stats["consecutive_work_max"], consecutive)
                else:
                    consecutive = 0

            export_data["staff"].append({
                "id": s["id"],
                "name": s["name"],
                "workType": s.get("workType", "2kohtai"),
                "shifts": staff_shifts,
                "stats": stats
            })

        # 日別集計
        daily_stats = []
        for d in range(1, num_days + 1):
            day_stat = {"day": d, "dayShift": 0, "junnya": 0, "shinya": 0, "late": 0}
            for s in staff_data:
                key = f"{s['id']}-{d}"
                sh = shifts.get(key, "")
                if sh in ["day", "late"]:
                    day_stat["dayShift"] += 1
                if sh in ["night2", "junnya"]:
                    day_stat["junnya"] += 1
                if sh in ["ake", "shinya"]:
                    day_stat["shinya"] += 1
                if sh == "late":
                    day_stat["late"] += 1
            daily_stats.append(day_stat)

        export_data["dailyStats"] = daily_stats

        # ========== 公平性・負担評価指標 ==========
        from shift_quality import calculate_gini, calculate_cv, evaluate_gini_grade

        # 夜勤回数リスト（夜勤対象者のみ）
        night_counts = []
        weekend_counts = []
        consecutive_maxes = []
        late_counts = []

        for s_data in export_data["staff"]:
            wt = s_data["workType"]
            # 夜勤カウント（夜勤対象者のみ、固定シフトも除外）
            if wt not in ["day_only", "fixed"]:
                night_counts.append(s_data["stats"]["night"])
                late_counts.append(sum(1 for sh in s_data["shifts"] if sh["shift"] == "late"))

            # 週末勤務カウント（固定シフト職員は除外）
            # workType == "fixed" の職員は公平性計算から除外
            is_fixed_schedule = (wt == "fixed")
            if not is_fixed_schedule:
                weekend_work = 0
                for sh in s_data["shifts"]:
                    d = sh["day"]
                    wd = date(year, month, d).weekday()
                    is_weekend = wd >= 5 or (year, month, d) in HOLIDAYS
                    if is_weekend and sh["shift"] not in ["off", "paid", "refresh"]:
                        weekend_work += 1
                weekend_counts.append(weekend_work)

            # 連続勤務MAX（固定シフト職員は除外）
            if not is_fixed_schedule:
                consecutive_maxes.append(s_data["stats"]["consecutive_work_max"])

        # 指標計算
        fairness_metrics = {
            "nightShiftGini": round(calculate_gini(night_counts), 4) if night_counts else 0,
            "nightShiftCV": round(calculate_cv(night_counts), 4) if night_counts else 0,
            "weekendGini": round(calculate_gini(weekend_counts), 4) if weekend_counts else 0,
            "weekendCV": round(calculate_cv(weekend_counts), 4) if weekend_counts else 0,
            "lateShiftGini": round(calculate_gini(late_counts), 4) if late_counts else 0,
            "lateShiftCV": round(calculate_cv(late_counts), 4) if late_counts else 0,
            "consecutiveWorkAvg": round(sum(consecutive_maxes) / len(consecutive_maxes), 2) if consecutive_maxes else 0,
            "consecutiveWorkMax": max(consecutive_maxes) if consecutive_maxes else 0,
            "nightShiftStd": round((sum((v - sum(night_counts)/len(night_counts))**2 for v in night_counts) / len(night_counts))**0.5, 2) if night_counts else 0,
            "nightShiftRange": (max(night_counts) - min(night_counts)) if night_counts else 0,
        }

        fairness_metrics["評価"] = {
            "夜勤公平性": evaluate_gini_grade(fairness_metrics["nightShiftGini"]),
            "週末公平性": evaluate_gini_grade(fairness_metrics["weekendGini"]),
            "遅出公平性": evaluate_gini_grade(fairness_metrics["lateShiftGini"]),
        }

        export_data["fairnessMetrics"] = fairness_metrics

        # 労基法コンプライアンスチェック
        try:
            compliance_result = {"shifts": shifts}
            compliance_data = {
                "year": year, "month": month,
                "staff": staff_data, "config": {},
                "wishes": wishes, "prevMonthData": {},
            }
            export_data["laborCompliance"] = check_labor_law_compliance(
                compliance_result, compliance_data
            )
        except Exception:
            pass

        # JSONレスポンスを返す
        response = app.response_class(
            response=pyjson.dumps(export_data, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json'
        )
        response.headers["Content-Disposition"] = f"attachment; filename=shift_{year}_{month:02d}.json"
        return response


    @app.route("/export_pdf", methods=["POST"])
    def export_pdf():
        # 日本語フォント登録
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        except Exception:
            pass  # Already registered or error

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

        # バリデーション
        try:
            year = validate_year(data.get("year"))
            month = validate_month(data.get("month"))
            ward = validate_ward(data.get("ward", "1"))
        except (ValidationError, TypeError) as e:
            msg = e.message if hasattr(e, 'message') else 'year, month が必要です'
            return jsonify({"status": "error", "message": msg}), 400

        staff_data = data.get("staff", [])
        if not isinstance(staff_data, list):
            return jsonify({"status": "error", "message": "staff は配列である必要があります"}), 400

        wish_map = data.get("wishMap", {})
        prev_month_days = data.get("prevMonthDays", [])
        creation_num = data.get("creationNum", 0)
        pdf_config = data.get("config", {})
        req_day_weekday = pdf_config.get("reqDayWeekday", 7)
        req_day_holiday = pdf_config.get("reqDayHoliday", 5)
        day_staff_by_day = pdf_config.get("dayStaffByDay", {})
        req_junnya = pdf_config.get("reqJunnya", 2)
        req_shinya = pdf_config.get("reqShinya", 2)
        req_late = pdf_config.get("reqLate", 1)

        num_days = calendar.monthrange(year, month)[1]

        # PDF作成
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                               leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)

        styles = getSampleStyleSheet()
        jp_style = ParagraphStyle('Japanese', fontName='HeiseiKakuGo-W5', fontSize=10)

        elements = []

        # タイトル（シフト作成番号付き）
        title_text = f"{year}年{month}月 勤務表"
        if creation_num and creation_num > 0:
            title_text += f"　［作成#{creation_num}］"
        title = Paragraph(f"<font name='HeiseiKakuGo-W5' size='14'>{title_text}</font>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 10))

        abbr = SHIFT_ABBR

        # ヘッダー行
        SHIFT_lab = abbr
        num_prev = len(prev_month_days)  # 前月分の日数

        # ヘッダー作成
        header = ["氏名"]
        # 前月分ヘッダー
        for pd in prev_month_days:
            header.append(f"{pd['day']}\n(前)")

        # 当月分ヘッダー
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        for d in range(1, num_days + 1):
            wd = weekdays[calendar.weekday(year, month, d)]
            header.append(f"{d}\n({wd})")
        header.extend(["日", "夜", "休"])

        table_data = [header]

        for s in staff_data:
            row = [s["name"]]
            # 前月分
            for pd in prev_month_days:
                # pd["shifts"] は {staffId: shiftVal} の辞書想定
                sh = pd.get("shifts", {}).get(s["id"], "")
                row.append(SHIFT_lab.get(sh, sh))

            shifts = s.get("shifts", [])
            day_hours_list = s.get("dayHours", [])
            for idx, sh in enumerate(shifts):
                label = SHIFT_lab.get(sh, sh)
                # 日勤で時間数がデフォルト(7.5)以外の場合、時間数を付加
                if sh == "day" and idx < len(day_hours_list) and day_hours_list[idx] is not None:
                    dh = float(day_hours_list[idx])
                    if dh != 7.5:
                        # 整数表示できる場合は整数で
                        dh_str = str(int(dh)) if dh == int(dh) else str(dh)
                        label += dh_str
                row.append(label)

            # 集計
            day_count = 0
            night_count = 0
            off_count = 0
            wt = s.get("workType", "2kohtai")
            # 当月分のみ集計対象とする
            for sh in shifts:
                # 日勤カウント：日勤のみの人は遅出を除く
                if wt == "day_only":
                    if sh in ["day"]: day_count += 1
                else:
                    if sh in ["day", "late"]: day_count += 1
                if sh in ["night2", "junnya", "shinya", "ake"]: night_count += 1
                if sh in ["off", "paid", "refresh"]: off_count += 1

            row.append(str(day_count))
            row.append(str(night_count))
            row.append(str(off_count))
            table_data.append(row)

        # 集計行の色付け用: (row_index, col_offset, day_values, required_values, mode)
        # mode: "gte" (>=で緑), "eq" (==で緑)
        summary_color_info = []
        num_staff_rows = len(staff_data)  # ヘッダー除く職員行数

        # 小計行を追加
        # 一病棟の場合は日勤を看護とNAに分ける
        if ward == "1":
            # 日勤(看護)集計
            day_nurse_summary = ["日勤(看護)"]
            for _ in range(num_prev):
                day_nurse_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts = s.get("shifts", [])
                    stype = s.get("type", "nurse")
                    if d <= len(shifts):
                        sh = shifts[d - 1]
                        if sh in ["day", "late"] and stype != "nurseaide":
                            count += 1
                day_nurse_summary.append(str(count))
            day_nurse_summary.extend(["", "", ""])
            table_data.append(day_nurse_summary)

            # 日勤(NA)集計
            day_na_summary = ["日勤(NA)"]
            for _ in range(num_prev):
                day_na_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts = s.get("shifts", [])
                    stype = s.get("type", "nurse")
                    if d <= len(shifts):
                        sh = shifts[d - 1]
                        if sh in ["day", "late"] and stype == "nurseaide":
                            count += 1
                day_na_summary.append(str(count))
            day_na_summary.extend(["", "", ""])
            table_data.append(day_na_summary)

        # 曜日別の日勤必要数を事前計算（solver.pyと同一ロジック）
        # dayStaffByDay UIフィールドから曜日別必要数を取得
        _DS_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        def calc_day_req(day_of_month):
            dt = date(year, month, day_of_month)
            wd = dt.weekday()  # 0=Mon..6=Sun
            is_hol = (year, month, day_of_month) in HOLIDAYS
            if wd == 6 or is_hol:  # 日曜 or 祝日
                v = day_staff_by_day.get("sun")
                return v if v is not None else req_day_holiday
            key = _DS_KEYS[wd]
            v = day_staff_by_day.get(key)
            return v if v is not None else req_day_weekday

        # 日勤計集計
        day_summary = ["日勤計"]
        day_counts = []
        day_reqs = []
        for _ in range(num_prev):
            day_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts = s.get("shifts", [])
                if d <= len(shifts):
                    sh = shifts[d - 1]
                    if sh in ["day", "late"]:
                        count += 1
            day_summary.append(str(count))
            day_counts.append(count)
            day_reqs.append(calc_day_req(d))
        day_summary.extend(["", "", ""])
        table_data.append(day_summary)
        day_summary_row = len(table_data) - 1
        summary_color_info.append((day_summary_row, day_counts, day_reqs, "gte"))

        # 看護師計
        nurse_summary = ["看護師計"]
        for _ in range(num_prev):
            nurse_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts = s.get("shifts", [])
                if d <= len(shifts):
                    sh = shifts[d - 1]
                    if sh in ["day", "late"]:
                        stype = s.get("staffType", "nurse")
                        if stype in ["nurse", "junkango"]:
                            count += 1
            nurse_summary.append(str(count))
        nurse_summary.extend(["", "", ""])
        table_data.append(nurse_summary)

        # 補助者計
        aide_summary = ["補助者計"]
        for _ in range(num_prev):
            aide_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts = s.get("shifts", [])
                if d <= len(shifts):
                    sh = shifts[d - 1]
                    if sh in ["day", "late"]:
                        stype = s.get("staffType", "nurse")
                        if stype == "nurseaide":
                            count += 1
            aide_summary.append(str(count))
        aide_summary.extend(["", "", ""])
        table_data.append(aide_summary)

        # 準夜帯集計
        junnya_summary = ["準夜帯"]
        junnya_counts = []
        for _ in range(num_prev):
            junnya_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts = s.get("shifts", [])
                if d <= len(shifts):
                    sh = shifts[d - 1]
                    if sh in ["night2", "junnya"]:
                        count += 1
            junnya_summary.append(str(count))
            junnya_counts.append(count)
        junnya_summary.extend(["", "", ""])
        table_data.append(junnya_summary)
        junnya_row = len(table_data) - 1
        summary_color_info.append((junnya_row, junnya_counts, [req_junnya] * num_days, "eq"))

        # 深夜帯集計
        shinya_summary = ["深夜帯"]
        shinya_counts = []
        for _ in range(num_prev):
            shinya_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts = s.get("shifts", [])
                if d <= len(shifts):
                    sh = shifts[d - 1]
                    if sh in ["ake", "shinya"]:
                        count += 1
            shinya_summary.append(str(count))
            shinya_counts.append(count)
        shinya_summary.extend(["", "", ""])
        table_data.append(shinya_summary)
        shinya_row = len(table_data) - 1
        summary_color_info.append((shinya_row, shinya_counts, [req_shinya] * num_days, "eq"))

        # 遅出集計（二病棟のみ）
        if ward == "2":
            late_summary = ["遅出"]
            late_counts = []
            for _ in range(num_prev):
                late_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts = s.get("shifts", [])
                    if d <= len(shifts):
                        sh = shifts[d - 1]
                        if sh == "late":
                            count += 1
                late_summary.append(str(count))
                late_counts.append(count)
            late_summary.extend(["", "", ""])
            table_data.append(late_summary)
            late_row = len(table_data) - 1
            summary_color_info.append((late_row, late_counts, [req_late] * num_days, "gte"))

        # テーブルスタイル
        # 列幅: 名前60, 前月分18*num_prev, 当月分18*num_days, 集計22*3
        col_widths = [60] + [18] * num_prev + [18] * num_days + [22, 22, 22]

        table = Table(table_data, colWidths=col_widths)

        style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ])

        # 土日祝の背景色
        for d_idx in range(num_prev, num_prev + num_days): # 当月の日付の列インデックス
            day_of_month = d_idx - num_prev + 1
            dt = date(year, month, day_of_month)
            is_sunday = dt.weekday() == 6
            is_holiday = (year, month, day_of_month) in HOLIDAYS
            if is_sunday or is_holiday:
                style.add('BACKGROUND', (d_idx + 1, 0), (d_idx + 1, -1), colors.Color(1, 0.9, 0.9)) # +1は氏名列の分

        # 希望の反映（背景色）
        # wish_map: { "staffId-day": "off"|"day"|... }
        for s_idx, s in enumerate(staff_data):
            row_idx = s_idx + 1 # ヘッダー行が0なので+1
            for d in range(1, num_days + 1):
                key = f"{s['id']}-{d}"
                if key in wish_map:
                    wish_shift = wish_map[key]
                    col_idx = num_prev + d # 名前列(1) + 前月分(num_prev) + 日付(d-1)?
                    # col_widths = [60] + [18]*num_prev + [18]*num_days...
                    # Tableの列インデックス: 名前=0, 前月=1..num_prev, 当月=num_prev+1..
                    # d=1 -> num_prev+1
                    col_idx = num_prev + d
                    if wish_shift in ["off", "paid"]:
                        style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(0.73, 0.9, 0.99)) # Light Blue
                    else:
                        style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(1, 0.84, 0.66)) # Light Orange

        # 前月分の背景色
        for idx in range(num_prev):
            style.add('BACKGROUND', (idx + 1, 0), (idx + 1, -1), colors.Color(0.95, 0.95, 0.95))

        # 集計行の色付け（日勤不足=赤、充足=緑）
        color_ok = colors.Color(0.85, 0.95, 0.85)    # 薄緑
        color_ng = colors.Color(1.0, 0.85, 0.85)      # 薄赤
        for row_idx, counts, reqs, mode in summary_color_info:
            for di, (cnt, req) in enumerate(zip(counts, reqs)):
                col_idx = num_prev + di + 1  # +1 for 氏名列
                if mode == "gte":
                    ok = cnt >= req
                else:  # "eq"
                    ok = cnt == req
                bg = color_ok if ok else color_ng
                style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg)
                if not ok:
                    style.add('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.Color(0.6, 0.1, 0.1))
                    style.add('FONTSIZE', (col_idx, row_idx), (col_idx, row_idx), 7)  # 少し大きく

        # 5連勤の赤下線（各職員の連勤検出）
        rest_shifts = {"off", "paid", "ake", "refresh"}
        for s_idx, s in enumerate(staff_data):
            if s.get("workType") == "fixed":
                continue
            row_idx = s_idx + 1  # ヘッダー行が0
            shifts = s.get("shifts", [])
            # 前月末からの連勤数
            prev_work = 0
            for pd in reversed(prev_month_days):
                pd_shifts = pd.get("shifts", {})
                psh = pd_shifts.get(s["id"], "")
                if not psh or psh in rest_shifts:
                    break
                prev_work += 1
            # 当月の連勤検出
            streak_start = 1
            current_streak = prev_work
            for d in range(1, num_days + 1):
                sh = shifts[d - 1] if d <= len(shifts) else ""
                is_work = sh and sh not in rest_shifts
                if is_work:
                    current_streak += 1
                else:
                    if current_streak >= 5:
                        for dd in range(streak_start, d):
                            col = num_prev + dd  # +1 for name col, but dd is 1-based
                            style.add('LINEBELOW', (col, row_idx), (col, row_idx), 1.5, colors.red)
                    current_streak = 0
                    streak_start = d + 1
            # 月末で終わる連勤
            if current_streak >= 5:
                for dd in range(streak_start, num_days + 1):
                    col = num_prev + dd
                    style.add('LINEBELOW', (col, row_idx), (col, row_idx), 1.5, colors.red)

        table.setStyle(style)
        elements.append(table)

        doc.build(elements)

        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'shift_{year}_{month:02d}.pdf'
        )

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/holidays")
    def get_holidays():
        holidays_path = os.path.join(os.path.dirname(__file__), "holidays.json")
        try:
            with open(holidays_path, "r", encoding="utf-8") as f:
                data = pyjson.load(f)
            return jsonify(data)
        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("祝日データ読み込みエラー: %s", e)
            return _error_response("祝日データの読み込みに失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_holidays")

    if not portal_mode:
        @app.route("/")
        def index():
            return render_template("index.html")

    # ========== 新規API（病棟別エンジン対応） ==========

    @app.route("/api/wards")
    def get_wards():
        """利用可能な病棟リストを取得"""
        return jsonify([
            {'id': 'ichiboutou', 'name': '1病棟'},
            {'id': 'nibyoutou', 'name': '2病棟'},
            {'id': 'sanbyoutou', 'name': '3病棟'},
        ])

    @app.route("/api/carry-over", methods=["POST"])
    def get_carry_over():
        """前月からの引き継ぎ状態（休みまで遡る）"""
        try:
            from engines import get_engine

            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward', 'nibyoutou'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            prev_shift = data.get('prevShift', {})

            engine = get_engine(ward)
            result = engine.get_carry_over_state(year, month, prev_shift)

            return jsonify({
                'status': 'success',
                'ward': ward,
                'carryOver': result
            })
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except ValueError as e:
            return _error_response(str(e), 400)
        except (OSError, IOError) as e:
            logger.exception("引き継ぎデータ取得エラー: %s", e)
            return _error_response("引き継ぎデータの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "carry_over")

    @app.route("/api/validate-flex", methods=["POST"])
    def validate_flex():
        """flexRequest職員の全日入力チェック"""
        try:
            from engines import get_engine

            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward', 'nibyoutou'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            assignments = data.get('assignments', {})

            engine = get_engine(ward)
            result = engine.validate_flex_complete(year, month, assignments)

            return jsonify({
                'status': 'success',
                'ward': ward,
                'validation': result
            })
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except ValueError as e:
            return _error_response(str(e), 400)
        except Exception as e:
            return _safe_internal_error(e, "validate_flex")

    @app.route("/api/solve/<ward>", methods=["POST"])
    def solve_ward(ward):
        """病棟別ソルバー実行（メインソルバーに統合）"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

            # 病棟IDを数値コードに変換
            ward_map = {"ichiboutou": "1", "nibyoutou": "2", "sanbyoutou": "3"}
            ward_num = ward_map.get(ward)
            if not ward_num:
                return jsonify({"status": "error", "message": f"不明な病棟: {ward}"}), 400

            # configにward番号を設定してメインソルバーで実行
            if "config" not in data:
                data["config"] = {}
            data["config"]["ward"] = ward_num

            validated_data = validate_solve_request(data)
            data.update(validated_data)
            # maxNight補正はShiftSolver.__init__内で実施
            return jsonify(ShiftSolver(data).solve())
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except Exception as e:
            return _safe_internal_error(e, "solve_ward")

    @app.route("/api/employees/all", methods=["GET"])
    def get_all_staff():
        """全職員をフロントエンド形式で取得"""
        try:
            employees_path = os.path.join(os.path.dirname(__file__), 'shared', 'employees.json')
            if not os.path.exists(employees_path):
                return jsonify({'status': 'success', 'staff': []})

            with open(employees_path, 'r', encoding='utf-8') as f:
                employees = pyjson.load(f)

            # バックエンド形式からフロントエンド形式に変換（一元化された変換関数を使用）
            frontend_staff = [employee_to_frontend(emp) for emp in employees]

            return jsonify({'status': 'success', 'staff': frontend_staff})
        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("全職員データ取得エラー: %s", e)
            return _error_response("職員データの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_all_staff")

    @app.route("/api/staff/<ward>")
    def get_staff(ward):
        """病棟別の職員リストを取得"""
        try:
            from engines import get_engine

            engine = get_engine(ward)
            staff_data = engine.load_staff()

            # フラットなリストに変換
            all_staff = []
            for category, staff_list in staff_data.items():
                for s in staff_list:
                    s['category'] = category
                    all_staff.append(s)

            return jsonify({
                'status': 'success',
                'ward': ward,
                'staff': all_staff,
                'byCategory': staff_data
            })
        except ValueError as e:
            return _error_response(str(e), 400)
        except (OSError, IOError) as e:
            logger.exception("病棟別職員取得エラー: %s", e)
            return _error_response("職員データの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_staff")

    @app.route("/api/staff/migrate", methods=["POST"])
    def migrate_staff():
        """フロントエンドのLocalStorageから職員データをemployees.jsonに移行"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            frontend_staff = data.get('staff', [])

            if not frontend_staff:
                return jsonify({'status': 'error', 'message': '職員データがありません'}), 400

            if not isinstance(frontend_staff, list):
                return jsonify({'status': 'error', 'message': 'staff は配列である必要があります'}), 400

            if len(frontend_staff) > 500:
                return jsonify({'status': 'error', 'message': '職員数が多すぎます（上限500名）'}), 400

            # 変換処理（バリデーション → 変換）
            from validation import validate_staff_id, validate_staff_name
            converted_staff = []
            for s in frontend_staff:
                try:
                    validate_staff_id(s.get('id'))
                    validate_staff_name(s.get('name'))
                except ValidationError as e:
                    return jsonify({'status': 'error', 'message': f'職員データが不正: {e.message}'}), 400
                converted_staff.append(frontend_to_employee(s))

            # 既存employees.jsonからtransferHistoryを保持
            employees_path = os.path.join(os.path.dirname(__file__), 'shared', 'employees.json')
            existing_by_id = {}
            if os.path.exists(employees_path):
                try:
                    with open(employees_path, 'r', encoding='utf-8') as f:
                        existing_employees = pyjson.load(f)
                    existing_by_id = {e['id']: e for e in existing_employees if 'id' in e}
                except (OSError, IOError, pyjson.JSONDecodeError):
                    pass
            for emp in converted_staff:
                existing = existing_by_id.get(emp.get('id'))
                if existing and 'transferHistory' in existing:
                    emp['transferHistory'] = existing['transferHistory']

            os.makedirs(os.path.dirname(employees_path), exist_ok=True)

            atomic_json_write(employees_path, converted_staff)

            # 病棟別集計
            ward_counts = {}
            for s in converted_staff:
                ward = s['ward']
                ward_counts[ward] = ward_counts.get(ward, 0) + 1

            return jsonify({
                'status': 'success',
                'message': f'職員データを移行しました',
                'total': len(converted_staff),
                'byWard': ward_counts
            })

        except (OSError, IOError) as e:
            logger.exception("職員データ移行エラー: %s", e)
            return _error_response("職員データの移行に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "migrate_staff")

    # ========== シフト管理API（ファイルベース） ==========

    def get_ward_id(ward):
        """病棟コード変換"""
        ward_map = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
        return ward_map.get(ward, ward)

    def get_shift_filepath(ward, year, month):
        """シフトファイルパスを取得"""
        ward_id = get_ward_id(ward)
        return os.path.join(os.path.dirname(__file__), 'shifts', ward_id, f"{year}-{month:02d}.json")

    @app.route("/api/shift/<ward>/<int:year>/<int:month>", methods=["GET"])
    def get_shift(ward, year, month):
        """指定月のシフトデータを取得"""
        try:
            try:
                ward = validate_ward(ward)
                year = validate_year(year)
                month = validate_month(month)
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({
                    'exists': False,
                    'ward': get_ward_id(ward),
                    'year': year,
                    'month': month
                })

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            shift_data['exists'] = True
            return jsonify(shift_data)

        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("シフトデータ取得エラー: %s", e)
            return _error_response("シフトデータの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_shift")

    @app.route("/api/shift/save-draft", methods=["POST"])
    def save_draft():
        """シフトパターンを下書き保存"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            ward = data.get('ward')
            year = data.get('year')
            month = data.get('month')
            name = data.get('name')
            shifts = data.get('shifts', {})
            score = data.get('score', 0)

            # バリデーション
            try:
                ward = validate_ward(ward)
                year = validate_year(year)
                month = validate_month(month)
                name = validate_draft_name(name)
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            if not all([ward, year, month, name]):
                return jsonify({'status': 'error', 'message': 'ward, year, month, name が必要です'}), 400

            filepath = get_shift_filepath(ward, year, month)
            ward_id = get_ward_id(ward)

            # 既存データ読み込み or 新規作成
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    shift_data = pyjson.load(f)
            else:
                shift_data = {
                    "year": year,
                    "month": month,
                    "ward": ward_id,
                    "status": "draft",
                    "selectedDraft": None,
                    "confirmedAt": None,
                    "drafts": {},
                    "confirmed": None,
                    "changeHistory": []
                }

            # シフトデータを職員別に整理
            staff_shifts = {}
            for shift_key, shift_val in shifts.items():
                parts = shift_key.rsplit('-', 1)
                if len(parts) == 2:
                    staff_id, day = parts
                    if staff_id not in staff_shifts:
                        staff_shifts[staff_id] = {}
                    staff_shifts[staff_id][day] = shift_val

            # 下書き追加
            solver_status = data.get('solverStatus', '')
            meta = data.get('meta')
            draft_obj = {
                "createdAt": datetime.now().isoformat(),
                "score": score,
                "shifts": staff_shifts
            }
            if solver_status:
                draft_obj["solverStatus"] = solver_status
            if meta and isinstance(meta, dict):
                draft_obj["meta"] = meta
            shift_data['drafts'][name] = draft_obj

            # 保存した案を自動的に仮選択
            shift_data['selectedDraft'] = name

            # 保存
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            atomic_json_write(filepath, shift_data)

            return jsonify({'status': 'success', 'name': name})

        except (OSError, IOError) as e:
            logger.exception("下書き保存エラー: %s", e)
            return _error_response("下書きの保存に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "save_draft")

    @app.route("/api/shift/select-draft", methods=["POST"])
    def select_draft():
        """下書きを「仮」として選択"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
                name = validate_draft_name(data.get('name'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            if name not in shift_data.get('drafts', {}):
                return jsonify({'status': 'error', 'message': f'{name} が見つかりません'}), 404

            shift_data['selectedDraft'] = name

            atomic_json_write(filepath, shift_data)

            return jsonify({'status': 'success', 'selectedDraft': name})

        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("下書き選択エラー: %s", e)
            return _error_response("下書きの選択に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "select_draft")

    @app.route("/api/shift/confirm", methods=["POST"])
    def confirm_shift():
        """選択中の仮シフトを確定"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            selected = shift_data.get('selectedDraft')
            if not selected or selected not in shift_data.get('drafts', {}):
                return jsonify({'status': 'error', 'message': '仮シフトが選択されていません'}), 400

            # 確定前のバックアップ
            ward_id = get_ward_id(ward)
            backup_dir = os.path.join(os.path.dirname(__file__), 'shifts', ward_id, 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{year}-{month:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            atomic_json_write(backup_path, shift_data)

            # 確定
            shift_data['status'] = 'confirmed'
            shift_data['confirmedAt'] = datetime.now().isoformat()
            shift_data['confirmed'] = {
                'shifts': shift_data['drafts'][selected]['shifts']
            }
            # dayHoursがあれば保存（日勤時短者の時間数）
            day_hours = data.get('dayHours')
            if day_hours and isinstance(day_hours, dict) and len(day_hours) > 0:
                shift_data['confirmed']['dayHours'] = day_hours

            atomic_json_write(filepath, shift_data)

            return jsonify({
                'status': 'success',
                'confirmedAt': shift_data['confirmedAt'],
                'draftName': selected
            })

        except (OSError, IOError) as e:
            logger.exception("シフト確定エラー: %s", e)
            return _error_response("シフトの確定に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "confirm_shift")

    @app.route("/api/shift/modify", methods=["POST"])
    def modify_confirmed():
        """確定シフトを修正（履歴付き）"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            changes = data.get('changes', [])
            reason = data.get('reason', '')

            # 変更データのバリデーション
            if not isinstance(changes, list):
                return jsonify({'status': 'error', 'message': 'changes は配列である必要があります'}), 400
            if len(reason) > 500:
                return jsonify({'status': 'error', 'message': 'reason は500文字以下である必要があります'}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            if shift_data.get('status') != 'confirmed':
                return jsonify({'status': 'error', 'message': '確定されていません'}), 400

            # 変更適用
            for change in changes:
                try:
                    validated_change = validate_actual_change(change)
                except ValidationError as e:
                    return jsonify({'status': 'error', 'message': e.message}), 400

                staff_id = validated_change['staffId']
                day = str(validated_change['day'])
                new_shift = validated_change['to']

                if staff_id not in shift_data['confirmed']['shifts']:
                    shift_data['confirmed']['shifts'][staff_id] = {}

                shift_data['confirmed']['shifts'][staff_id][day] = new_shift

                # 履歴追加
                shift_data['changeHistory'].append({
                    'timestamp': datetime.now().isoformat(),
                    'staffId': staff_id,
                    'day': validated_change['day'],
                    'from': change.get('from', ''),
                    'to': new_shift,
                    'reason': reason
                })

            atomic_json_write(filepath, shift_data)

            return jsonify({'status': 'success', 'changesApplied': len(changes)})

        except (OSError, IOError) as e:
            logger.exception("シフト修正エラー: %s", e)
            return _error_response("シフトの修正に失敗しました")
        except (KeyError, TypeError) as e:
            logger.warning("シフト修正データエラー: %s", e)
            return _error_response("変更データの形式が不正です", 400)
        except Exception as e:
            return _safe_internal_error(e, "modify_confirmed")

    @app.route("/api/shift/delete-draft", methods=["POST"])
    def delete_draft():
        """下書きを削除"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
                name = validate_draft_name(data.get('name'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            if name not in shift_data.get('drafts', {}):
                return jsonify({'status': 'error', 'message': f'{name} が見つかりません'}), 404

            # 選択中の下書きを削除する場合は選択解除
            if shift_data.get('selectedDraft') == name:
                shift_data['selectedDraft'] = None
                shift_data['status'] = 'draft'

            del shift_data['drafts'][name]

            atomic_json_write(filepath, shift_data)

            return jsonify({'status': 'success'})

        except (OSError, IOError) as e:
            logger.exception("下書き削除エラー: %s", e)
            return _error_response("下書きの削除に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "delete_draft")

    @app.route("/api/shift/prev-month", methods=["GET"])
    def get_prev_month_shifts():
        """前月参照データを取得（確定 > 仮 > なし）+ 異動職員の旧病棟データ補完"""
        try:
            # バリデーション
            try:
                ward = validate_ward(request.args.get('ward'))
                year = validate_year(request.args.get('year', type=int))
                month = validate_month(request.args.get('month', type=int))
            except (ValidationError, TypeError) as e:
                msg = e.message if hasattr(e, 'message') else 'ward, year, month が必要です'
                return jsonify({'status': 'error', 'message': msg}), 400

            # 前月計算
            if month == 1:
                prev_year, prev_month = year - 1, 12
            else:
                prev_year, prev_month = year, month - 1

            filepath = get_shift_filepath(ward, prev_year, prev_month)
            flat_shifts = {}
            source = 'none'
            draft_name = None

            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    shift_data = pyjson.load(f)

                # 確定版があればそれを使用（statusに関わらずconfirmedデータを優先）
                if shift_data.get('confirmed') and isinstance(shift_data['confirmed'], dict) and 'shifts' in shift_data['confirmed']:
                    staff_shifts = shift_data['confirmed']['shifts']
                    for staff_id, days in staff_shifts.items():
                        for day, shift in days.items():
                            flat_shifts[f"{staff_id}-{day}"] = shift
                    source = 'confirmed'

                # なければ仮選択中のドラフト
                elif shift_data.get('selectedDraft') and shift_data['selectedDraft'] in shift_data.get('drafts', {}):
                    selected = shift_data['selectedDraft']
                    staff_shifts = shift_data['drafts'][selected]['shifts']
                    for staff_id, days in staff_shifts.items():
                        for day, shift in days.items():
                            flat_shifts[f"{staff_id}-{day}"] = shift
                    source = 'draft'
                    draft_name = selected

            # 異動職員の旧病棟シフトを補完
            prev_days = calendar.monthrange(prev_year, prev_month)[1]
            ward_id = get_ward_id(ward)
            try:
                emp_path = os.path.join(os.path.dirname(__file__), "shared", "employees.json")
                with open(emp_path, "r", encoding="utf-8") as f:
                    all_employees = pyjson.load(f)
                # 当病棟の職員IDを取得
                ward_staff_ids = {e["id"] for e in all_employees if e.get("ward") == ward_id}
                # flat_shiftsに前月データがない職員を特定
                staff_with_data = set()
                for key in flat_shifts:
                    sid = key.rsplit("-", 1)[0]
                    staff_with_data.add(sid)
                missing_ids = ward_staff_ids - staff_with_data
                if missing_ids:
                    shifts_dir = os.path.join(os.path.dirname(__file__), "shifts")
                    prev_shift_file = f"{prev_year}-{prev_month:02d}.json"
                    # transferHistoryから旧病棟を特定、またはward全検索
                    other_wards = [w for w in WARD_ID_TO_CODE if w != ward_id]
                    for ow in other_wards:
                        if not missing_ids:
                            break
                        ow_path = os.path.join(shifts_dir, ow, prev_shift_file)
                        if not os.path.exists(ow_path):
                            continue
                        with open(ow_path, "r", encoding="utf-8") as f:
                            ow_data = pyjson.load(f)
                        ow_shifts = None
                        if ow_data.get("confirmed") and isinstance(ow_data["confirmed"], dict) and "shifts" in ow_data["confirmed"]:
                            ow_shifts = ow_data["confirmed"]["shifts"]
                        elif ow_data.get("selectedDraft") and ow_data["selectedDraft"] in ow_data.get("drafts", {}):
                            ow_shifts = ow_data["drafts"][ow_data["selectedDraft"]]["shifts"]
                        if not ow_shifts:
                            continue
                        for sid in list(missing_ids):
                            if sid in ow_shifts:
                                for day, shift in ow_shifts[sid].items():
                                    flat_shifts[f"{sid}-{day}"] = shift
                                missing_ids.discard(sid)
            except Exception as e:
                logger.warning("異動職員の前月データ補完エラー: %s", e)

            has_data = len(flat_shifts) > 0
            resp = {
                'status': 'success',
                'source': source,
                'prevYear': prev_year,
                'prevMonth': prev_month,
                'shifts': flat_shifts,
                'hasData': has_data
            }
            if draft_name:
                resp['draftName'] = draft_name
            return jsonify(resp)

        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("前月シフト取得エラー: %s", e)
            return _error_response("前月シフトデータの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_prev_month_shifts")

    @app.route("/api/shift/confirmed-month", methods=["GET"])
    def get_confirmed_month():
        """指定月の確定状態を取得"""
        try:
            # バリデーション
            try:
                ward = validate_ward(request.args.get('ward'))
                year = validate_year(request.args.get('year', type=int))
                month = validate_month(request.args.get('month', type=int))
            except (ValidationError, TypeError) as e:
                msg = e.message if hasattr(e, 'message') else 'ward, year, month が必要です'
                return jsonify({'status': 'error', 'message': msg}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({
                    'status': 'success',
                    'ward': get_ward_id(ward),
                    'month': f"{year}-{month:02d}",
                    'isConfirmed': False,
                    'selectedDraft': None
                })

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            return jsonify({
                'status': 'success',
                'ward': get_ward_id(ward),
                'month': f"{year}-{month:02d}",
                'isConfirmed': shift_data.get('status') == 'confirmed',
                'confirmedAt': shift_data.get('confirmedAt'),
                'selectedDraft': shift_data.get('selectedDraft'),
                'draftCount': len(shift_data.get('drafts', {}))
            })

        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("確定月取得エラー: %s", e)
            return _error_response("確定状態の取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_confirmed_month")

    @app.route("/api/staff/transfer", methods=["POST"])
    def transfer_staff():
        """職員を別病棟に異動する"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            # バリデーション
            try:
                staff_id = validate_staff_id(data.get('staffId'))
                to_ward = validate_ward(data.get('toWard'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            effective_date = data.get('effectiveDate', datetime.now().strftime('%Y-%m-%d'))

            # 日付形式のバリデーション
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', effective_date):
                return jsonify({'status': 'error', 'message': '日付形式が無効です (YYYY-MM-DD)'}), 400

            to_ward_id = get_ward_id(to_ward)

            employees_path = os.path.join(os.path.dirname(__file__), 'shared', 'employees.json')
            with open(employees_path, 'r', encoding='utf-8') as f:
                employees = pyjson.load(f)

            found = False
            from_ward = None

            for emp in employees:
                if emp['id'] == staff_id:
                    from_ward = emp['ward']
                    emp['ward'] = to_ward_id

                    if 'transferHistory' not in emp:
                        emp['transferHistory'] = []

                    emp['transferHistory'].append({
                        'date': effective_date,
                        'from': from_ward,
                        'to': to_ward_id
                    })
                    found = True
                    break

            if not found:
                return jsonify({'status': 'error', 'message': '職員が見つかりません'}), 404

            atomic_json_write(employees_path, employees)

            return jsonify({
                'status': 'success',
                'staffId': staff_id,
                'fromWard': from_ward,
                'toWard': to_ward_id,
                'effectiveDate': effective_date
            })

        except (OSError, IOError) as e:
            logger.exception("職員異動エラー: %s", e)
            return _error_response("職員の異動処理に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "transfer_staff")

    # ========== 様式9 出力API ==========

    @app.route("/api/yoshiki9/status", methods=["GET"])
    def yoshiki9_status():
        """各病棟の実績確定状況を返す"""
        try:
            from yoshiki9 import get_finalization_status
            year = request.args.get('year', type=int)
            month = request.args.get('month', type=int)
            if not year or not month:
                return jsonify({'status': 'error', 'message': 'year, month が必要です'}), 400
            result = get_finalization_status(year, month)
            return jsonify({'status': 'success', 'wards': result})
        except Exception as e:
            return _safe_internal_error(e, "yoshiki9_status")

    @app.route("/api/yoshiki9/generate", methods=["POST"])
    def yoshiki9_generate():
        """様式9 Excelファイルを生成"""
        try:
            from yoshiki9 import Yoshiki9Generator
            data = request.get_json()
            if not data:
                return _error_response("リクエストデータがありません", 400)

            year = validate_year(data.get('year'))
            month = validate_month(data.get('month'))
            gen_type = data.get('type', 'all')
            patients = data.get('patients', {})
            day_hours = data.get('dayHours', {})

            generator = Yoshiki9Generator(year, month, patients, day_hours=day_hours)

            if gen_type == 'all':
                zip_data = generator.generate_all_zip()
                return send_file(
                    zip_data,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f'yoshiki9_{year}_{month:02d}.zip'
                )
            elif gen_type in ('ward1', 'ward3', 'ward23'):
                xlsx_data = generator.generate(gen_type)
                wc = generator.config["ward_configs"][gen_type]
                filename = f"{wc['file_label']}_{year}年{month}月.xlsx"
                from urllib.parse import quote
                encoded = quote(filename)
                response = send_file(
                    xlsx_data,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'yoshiki9_{gen_type}_{year}_{month:02d}.xlsx'
                )
                # 日本語ファイル名を RFC 5987 形式で明示設定
                response.headers["Content-Disposition"] = (
                    f"attachment; filename=yoshiki9_{gen_type}_{year}_{month:02d}.xlsx; "
                    f"filename*=UTF-8''{encoded}"
                )
                return response
            else:
                return _error_response("無効な type パラメータ", 400)

        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except Exception as e:
            return _safe_internal_error(e, "yoshiki9_generate")

    # ========== 実績管理API ==========

    @app.route("/api/actual/start", methods=["POST"])
    def start_actual():
        """確定シフトから実績データを初期化"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            if not shift_data.get('confirmed'):
                return jsonify({'status': 'error', 'message': 'シフトが確定されていません'}), 400

            force = data.get('force', False)
            if shift_data.get('actual') and shift_data['actual'].get('shifts') and not force:
                return jsonify({'status': 'error', 'message': '実績データは既に初期化されています。上書きする場合は force=true を指定してください'}), 409

            # confirmed のシフトをコピーして actual を初期化
            import copy
            shift_data['actual'] = {
                'startedAt': datetime.now().isoformat(),
                'finalizedAt': None,
                'shifts': copy.deepcopy(shift_data['confirmed']['shifts']),
                'changes': []
            }
            # dayHoursもコピー
            if shift_data['confirmed'].get('dayHours'):
                shift_data['actual']['dayHours'] = copy.deepcopy(shift_data['confirmed']['dayHours'])
            shift_data['status'] = 'actual'

            atomic_json_write(filepath, shift_data)

            return jsonify({
                'status': 'success',
                'message': '実績データを初期化しました',
                'startedAt': shift_data['actual']['startedAt']
            })

        except (OSError, IOError) as e:
            logger.exception("実績初期化エラー: %s", e)
            return _error_response("実績データの初期化に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "start_actual")

    @app.route("/api/actual/<ward>/<int:year>/<int:month>", methods=["GET"])
    def get_actual(ward, year, month):
        """実績データを取得（confirmed との差分情報含む）"""
        try:
            try:
                ward = validate_ward(ward)
                year = validate_year(year)
                month = validate_month(month)
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            actual = shift_data.get('actual')
            confirmed = shift_data.get('confirmed')

            if not actual:
                return jsonify({
                    'status': 'success',
                    'hasActual': False,
                    'isFinalized': False,
                    'confirmed': confirmed
                })

            # 差分を計算
            diffs = []
            if confirmed and confirmed.get('shifts') and actual.get('shifts'):
                for staff_id, actual_days in actual['shifts'].items():
                    confirmed_days = confirmed['shifts'].get(staff_id, {})
                    for day, actual_shift in actual_days.items():
                        confirmed_shift = confirmed_days.get(day, '')
                        if actual_shift != confirmed_shift:
                            diffs.append({
                                'staffId': staff_id,
                                'day': int(day),
                                'confirmed': confirmed_shift,
                                'actual': actual_shift
                            })

            return jsonify({
                'status': 'success',
                'hasActual': True,
                'isFinalized': actual.get('finalizedAt') is not None,
                'actual': actual,
                'confirmed': confirmed,
                'diffs': diffs,
                'changeCount': len(actual.get('changes', []))
            })

        except (OSError, IOError, pyjson.JSONDecodeError) as e:
            logger.exception("実績データ取得エラー: %s", e)
            return _error_response("実績データの取得に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "get_actual")

    @app.route("/api/actual/update", methods=["POST"])
    def update_actual():
        """実績データをセル単位で更新"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            changes = data.get('changes', [])
            if not isinstance(changes, list) or not changes:
                return jsonify({'status': 'error', 'message': 'changes は空でない配列である必要があります'}), 400

            # 各変更をバリデーション
            validated_changes = []
            for change in changes:
                try:
                    validated_changes.append(validate_actual_change(change))
                except ValidationError as e:
                    return jsonify({'status': 'error', 'message': e.message, 'field': e.field}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            actual = shift_data.get('actual')
            if not actual:
                return jsonify({'status': 'error', 'message': '実績データが初期化されていません'}), 400

            if actual.get('finalizedAt'):
                return jsonify({'status': 'error', 'message': '実績は既に確定済みです'}), 400

            # 変更を適用
            for change in validated_changes:
                staff_id = change['staffId']
                day = str(change['day'])
                new_shift = change['to']

                if staff_id not in actual['shifts']:
                    actual['shifts'][staff_id] = {}

                old_shift = actual['shifts'][staff_id].get(day, '')

                actual['shifts'][staff_id][day] = new_shift

                # 変更履歴を記録
                actual['changes'].append({
                    'timestamp': datetime.now().isoformat(),
                    'staffId': staff_id,
                    'day': change['day'],
                    'from': old_shift,
                    'to': new_shift,
                    'reason': change.get('reason', '')
                })

            actual['lastUpdatedAt'] = datetime.now().isoformat()

            atomic_json_write(filepath, shift_data)

            return jsonify({
                'status': 'success',
                'changesApplied': len(validated_changes)
            })

        except (OSError, IOError) as e:
            logger.exception("実績更新エラー: %s", e)
            return _error_response("実績データの更新に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "update_actual")

    @app.route("/api/actual/finalize", methods=["POST"])
    def finalize_actual():
        """実績データを確定（様式9出力可能にする）"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            filepath = get_shift_filepath(ward, year, month)

            if not os.path.exists(filepath):
                return jsonify({'status': 'error', 'message': 'シフトデータがありません'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)

            actual = shift_data.get('actual')
            if not actual:
                return jsonify({'status': 'error', 'message': '実績データが初期化されていません'}), 400

            if actual.get('finalizedAt'):
                return jsonify({'status': 'error', 'message': '実績は既に確定済みです'}), 400

            actual['finalizedAt'] = datetime.now().isoformat()
            shift_data['status'] = 'finalized'

            atomic_json_write(filepath, shift_data)

            return jsonify({
                'status': 'success',
                'message': '実績を確定しました',
                'finalizedAt': actual['finalizedAt']
            })

        except (OSError, IOError) as e:
            logger.exception("実績確定エラー: %s", e)
            return _error_response("実績の確定に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "finalize_actual")

    @app.route("/api/migrate/localstorage", methods=["POST"])
    def migrate_from_localstorage():
        """LocalStorageのデータを新システムに移行"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400

            try:
                ward = validate_ward(data.get('ward'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400

            shifts = data.get('shifts', {})
            versions = data.get('shiftVersions', {})

            ward_id = get_ward_id(ward)
            shifts_dir = os.path.join(os.path.dirname(__file__), 'shifts', ward_id)
            os.makedirs(shifts_dir, exist_ok=True)

            migrated_months = 0

            for key, shift_values in shifts.items():
                # キー形式: "2026-2-2" (year-month-ward)
                parts = key.split('-')
                if len(parts) < 2:
                    continue
                year = int(parts[0])
                month = int(parts[1])

                filepath = os.path.join(shifts_dir, f"{year}-{month:02d}.json")

                # シフトデータを職員別に整理
                staff_shifts = {}
                for shift_key, shift_val in shift_values.items():
                    sk_parts = shift_key.rsplit('-', 1)
                    if len(sk_parts) == 2:
                        staff_id, day = sk_parts
                        if staff_id not in staff_shifts:
                            staff_shifts[staff_id] = {}
                        staff_shifts[staff_id][day] = shift_val

                shift_data = {
                    "year": year,
                    "month": month,
                    "ward": ward_id,
                    "status": "draft",
                    "selectedDraft": "移行データ",
                    "confirmedAt": None,
                    "drafts": {
                        "移行データ": {
                            "createdAt": datetime.now().isoformat(),
                            "score": 0,
                            "shifts": staff_shifts
                        }
                    },
                    "confirmed": None,
                    "changeHistory": []
                }

                # バージョンがあれば追加
                version_key = f"{year}-{month}-{ward}"
                if version_key in versions:
                    for v in versions[version_key].get('versions', []):
                        name = v.get('name', f"案{v.get('id', '?')}")
                        v_staff_shifts = {}
                        for sk, sv in v.get('shifts', {}).items():
                            sk_parts = sk.rsplit('-', 1)
                            if len(sk_parts) == 2:
                                sid, d = sk_parts
                                if sid not in v_staff_shifts:
                                    v_staff_shifts[sid] = {}
                                v_staff_shifts[sid][d] = sv

                        shift_data['drafts'][name] = {
                            "createdAt": v.get('timestamp', datetime.now().isoformat()),
                            "score": v.get('metrics', {}).get('totalScore', 0),
                            "shifts": v_staff_shifts
                        }

                atomic_json_write(filepath, shift_data)

                migrated_months += 1

            return jsonify({
                'status': 'success',
                'ward': ward_id,
                'shiftMonths': migrated_months
            })

        except (OSError, IOError, ValueError) as e:
            logger.exception("LocalStorage移行エラー: %s", e)
            return _error_response("データ移行に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "migrate_localstorage")
