"""シフトデータ管理・職員管理ルート"""
import os
import re
import calendar
import json as pyjson
import logging
from datetime import datetime
from flask import request, jsonify, render_template

from solver import ShiftSolver
from validation import (
    ValidationError, validate_year, validate_month, validate_ward,
    validate_staff_id, validate_staff_name, validate_solve_request,
    validate_draft_name, validate_actual_change,
    employee_to_frontend, frontend_to_employee,
    WARD_CODE_TO_ID, WARD_ID_TO_CODE,
)

logger = logging.getLogger(__name__)


def register_shift_routes(app, atomic_json_write, _error_response, _safe_internal_error, portal_mode=False):
    """シフト管理・職員管理ルートを登録"""

    def get_ward_id(ward):
        """病棟コード変換"""
        ward_map = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
        return ward_map.get(ward, ward)

    def get_shift_filepath(ward, year, month):
        """シフトファイルパスを取得"""
        ward_id = get_ward_id(ward)
        return os.path.join(os.path.dirname(__file__), 'shifts', ward_id, f"{year}-{month:02d}.json")

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
        """前月からの引き継ぎ状態"""
        try:
            from engines import get_engine
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'リクエストデータがありません'}), 400
            try:
                ward = validate_ward(data.get('ward', 'nibyoutou'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            prev_shift = data.get('prevShift', {})
            engine = get_engine(ward)
            result = engine.get_carry_over_state(year, month, prev_shift)
            return jsonify({'status': 'success', 'ward': ward, 'carryOver': result})
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
            try:
                ward = validate_ward(data.get('ward', 'nibyoutou'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            assignments = data.get('assignments', {})
            engine = get_engine(ward)
            result = engine.validate_flex_complete(year, month, assignments)
            return jsonify({'status': 'success', 'ward': ward, 'validation': result})
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except ValueError as e:
            return _error_response(str(e), 400)
        except Exception as e:
            return _safe_internal_error(e, "validate_flex")

    @app.route("/api/solve/<ward>", methods=["POST"])
    def solve_ward(ward):
        """病棟別ソルバー実行"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400
            ward_map = {"ichiboutou": "1", "nibyoutou": "2", "sanbyoutou": "3"}
            ward_num = ward_map.get(ward)
            if not ward_num:
                return jsonify({"status": "error", "message": f"不明な病棟: {ward}"}), 400
            if "config" not in data:
                data["config"] = {}
            data["config"]["ward"] = ward_num
            validated_data = validate_solve_request(data)
            data.update(validated_data)
            return jsonify(ShiftSolver(data).solve())
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)
        except Exception as e:
            return _safe_internal_error(e, "solve_ward")

    @app.route("/api/employees/all", methods=["GET"])
    def get_all_staff():
        """全職員をフロントエンド形式で取得"""
        try:
            employees_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared', 'employees.json')
            if not os.path.exists(employees_path):
                return jsonify({'status': 'success', 'staff': []})
            with open(employees_path, 'r', encoding='utf-8') as f:
                employees = pyjson.load(f)
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
            all_staff = []
            for category, staff_list in staff_data.items():
                for s in staff_list:
                    s['category'] = category
                    all_staff.append(s)
            return jsonify({'status': 'success', 'ward': ward, 'staff': all_staff, 'byCategory': staff_data})
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
            converted_staff = []
            for s in frontend_staff:
                try:
                    validate_staff_id(s.get('id'))
                    validate_staff_name(s.get('name'))
                except ValidationError as e:
                    return jsonify({'status': 'error', 'message': f'職員データが不正: {e.message}'}), 400
                converted_staff.append(frontend_to_employee(s))
            employees_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared', 'employees.json')
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
            ward_counts = {}
            for s in converted_staff:
                w = s['ward']
                ward_counts[w] = ward_counts.get(w, 0) + 1
            return jsonify({'status': 'success', 'message': '職員データを移行しました', 'total': len(converted_staff), 'byWard': ward_counts})
        except (OSError, IOError) as e:
            logger.exception("職員データ移行エラー: %s", e)
            return _error_response("職員データの移行に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "migrate_staff")

    # ========== シフトCRUD ==========

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
                return jsonify({'exists': False, 'ward': get_ward_id(ward), 'year': year, 'month': month})
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
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    shift_data = pyjson.load(f)
            else:
                shift_data = {
                    "year": year, "month": month, "ward": ward_id,
                    "status": "draft", "selectedDraft": None, "confirmedAt": None,
                    "drafts": {}, "confirmed": None, "changeHistory": []
                }
            staff_shifts = {}
            for shift_key, shift_val in shifts.items():
                parts = shift_key.rsplit('-', 1)
                if len(parts) == 2:
                    staff_id, day = parts
                    if staff_id not in staff_shifts:
                        staff_shifts[staff_id] = {}
                    staff_shifts[staff_id][day] = shift_val
            solver_status = data.get('solverStatus', '')
            meta = data.get('meta')
            draft_obj = {"createdAt": datetime.now().isoformat(), "score": score, "shifts": staff_shifts}
            if solver_status:
                draft_obj["solverStatus"] = solver_status
            if meta and isinstance(meta, dict):
                draft_obj["meta"] = meta
            shift_data['drafts'][name] = draft_obj
            shift_data['selectedDraft'] = name
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
            ward_id = get_ward_id(ward)
            backup_dir = os.path.join(os.path.dirname(__file__), 'shifts', ward_id, 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{year}-{month:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            atomic_json_write(backup_path, shift_data)
            shift_data['status'] = 'confirmed'
            shift_data['confirmedAt'] = datetime.now().isoformat()
            shift_data['confirmed'] = {'shifts': shift_data['drafts'][selected]['shifts']}
            day_hours = data.get('dayHours')
            if day_hours and isinstance(day_hours, dict) and len(day_hours) > 0:
                shift_data['confirmed']['dayHours'] = day_hours
            atomic_json_write(filepath, shift_data)
            return jsonify({'status': 'success', 'confirmedAt': shift_data['confirmedAt'], 'draftName': selected})
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
            try:
                ward = validate_ward(data.get('ward'))
                year = validate_year(data.get('year'))
                month = validate_month(data.get('month'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            changes = data.get('changes', [])
            reason = data.get('reason', '')
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
                shift_data['changeHistory'].append({
                    'timestamp': datetime.now().isoformat(),
                    'staffId': staff_id, 'day': validated_change['day'],
                    'from': change.get('from', ''), 'to': new_shift, 'reason': reason
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
        """前月参照データを取得 + 異動職員の旧病棟データ補完"""
        try:
            try:
                ward = validate_ward(request.args.get('ward'))
                year = validate_year(request.args.get('year', type=int))
                month = validate_month(request.args.get('month', type=int))
            except (ValidationError, TypeError) as e:
                msg = e.message if hasattr(e, 'message') else 'ward, year, month が必要です'
                return jsonify({'status': 'error', 'message': msg}), 400
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
                if shift_data.get('confirmed') and isinstance(shift_data['confirmed'], dict) and 'shifts' in shift_data['confirmed']:
                    staff_shifts = shift_data['confirmed']['shifts']
                    for staff_id, days in staff_shifts.items():
                        for day, shift in days.items():
                            flat_shifts[f"{staff_id}-{day}"] = shift
                    source = 'confirmed'
                elif shift_data.get('selectedDraft') and shift_data['selectedDraft'] in shift_data.get('drafts', {}):
                    selected = shift_data['selectedDraft']
                    staff_shifts = shift_data['drafts'][selected]['shifts']
                    for staff_id, days in staff_shifts.items():
                        for day, shift in days.items():
                            flat_shifts[f"{staff_id}-{day}"] = shift
                    source = 'draft'
                    draft_name = selected
            # 異動職員の旧病棟シフトを補完
            ward_id = get_ward_id(ward)
            try:
                emp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared", "employees.json")
                with open(emp_path, "r", encoding="utf-8") as f:
                    all_employees = pyjson.load(f)
                ward_staff_ids = {e["id"] for e in all_employees if e.get("ward") == ward_id}
                staff_with_data = set()
                for key in flat_shifts:
                    sid = key.rsplit("-", 1)[0]
                    staff_with_data.add(sid)
                missing_ids = ward_staff_ids - staff_with_data
                if missing_ids:
                    shifts_dir = os.path.join(os.path.dirname(__file__), "shifts")
                    prev_shift_file = f"{prev_year}-{prev_month:02d}.json"
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
            resp = {'status': 'success', 'source': source, 'prevYear': prev_year, 'prevMonth': prev_month, 'shifts': flat_shifts, 'hasData': has_data}
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
            try:
                ward = validate_ward(request.args.get('ward'))
                year = validate_year(request.args.get('year', type=int))
                month = validate_month(request.args.get('month', type=int))
            except (ValidationError, TypeError) as e:
                msg = e.message if hasattr(e, 'message') else 'ward, year, month が必要です'
                return jsonify({'status': 'error', 'message': msg}), 400
            filepath = get_shift_filepath(ward, year, month)
            if not os.path.exists(filepath):
                return jsonify({'status': 'success', 'ward': get_ward_id(ward), 'month': f"{year}-{month:02d}", 'isConfirmed': False, 'selectedDraft': None})
            with open(filepath, 'r', encoding='utf-8') as f:
                shift_data = pyjson.load(f)
            return jsonify({
                'status': 'success', 'ward': get_ward_id(ward), 'month': f"{year}-{month:02d}",
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
            try:
                staff_id = validate_staff_id(data.get('staffId'))
                to_ward = validate_ward(data.get('toWard'))
            except ValidationError as e:
                return jsonify({'status': 'error', 'message': e.message}), 400
            effective_date = data.get('effectiveDate', datetime.now().strftime('%Y-%m-%d'))
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', effective_date):
                return jsonify({'status': 'error', 'message': '日付形式が無効です (YYYY-MM-DD)'}), 400
            to_ward_id = get_ward_id(to_ward)
            employees_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared', 'employees.json')
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
                    emp['transferHistory'].append({'date': effective_date, 'from': from_ward, 'to': to_ward_id})
                    found = True
                    break
            if not found:
                return jsonify({'status': 'error', 'message': '職員が見つかりません'}), 404
            atomic_json_write(employees_path, employees)
            return jsonify({'status': 'success', 'staffId': staff_id, 'fromWard': from_ward, 'toWard': to_ward_id, 'effectiveDate': effective_date})
        except (OSError, IOError) as e:
            logger.exception("職員異動エラー: %s", e)
            return _error_response("職員の異動処理に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "transfer_staff")
