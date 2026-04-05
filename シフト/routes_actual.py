"""実績管理・様式9・移行ルート"""
import os
import json as pyjson
import logging
from datetime import datetime
from flask import request, jsonify, send_file

from validation import (
    ValidationError, validate_year, validate_month, validate_ward,
    validate_actual_change,
)

logger = logging.getLogger(__name__)


def register_actual_routes(app, atomic_json_write, _error_response, _safe_internal_error):
    """実績管理・様式9・移行ルートを登録"""

    def get_ward_id(ward):
        ward_map = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
        return ward_map.get(ward, ward)

    def get_shift_filepath(ward, year, month):
        ward_id = get_ward_id(ward)
        return os.path.join(os.path.dirname(__file__), 'shifts', ward_id, f"{year}-{month:02d}.json")

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
                return send_file(zip_data, mimetype='application/zip', as_attachment=True,
                                 download_name=f'yoshiki9_{year}_{month:02d}.zip')
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
            import copy
            shift_data['actual'] = {
                'startedAt': datetime.now().isoformat(),
                'finalizedAt': None,
                'shifts': copy.deepcopy(shift_data['confirmed']['shifts']),
                'changes': []
            }
            if shift_data['confirmed'].get('dayHours'):
                shift_data['actual']['dayHours'] = copy.deepcopy(shift_data['confirmed']['dayHours'])
            shift_data['status'] = 'actual'
            atomic_json_write(filepath, shift_data)
            return jsonify({'status': 'success', 'message': '実績データを初期化しました', 'startedAt': shift_data['actual']['startedAt']})
        except (OSError, IOError) as e:
            logger.exception("実績初期化エラー: %s", e)
            return _error_response("実績データの初期化に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "start_actual")

    @app.route("/api/actual/<ward>/<int:year>/<int:month>", methods=["GET"])
    def get_actual(ward, year, month):
        """実績データを取得"""
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
                return jsonify({'status': 'success', 'hasActual': False, 'isFinalized': False, 'confirmed': confirmed})
            diffs = []
            if confirmed and confirmed.get('shifts') and actual.get('shifts'):
                for staff_id, actual_days in actual['shifts'].items():
                    confirmed_days = confirmed['shifts'].get(staff_id, {})
                    for day, actual_shift in actual_days.items():
                        confirmed_shift = confirmed_days.get(day, '')
                        if actual_shift != confirmed_shift:
                            diffs.append({'staffId': staff_id, 'day': int(day), 'confirmed': confirmed_shift, 'actual': actual_shift})
            return jsonify({
                'status': 'success', 'hasActual': True,
                'isFinalized': actual.get('finalizedAt') is not None,
                'actual': actual, 'confirmed': confirmed,
                'diffs': diffs, 'changeCount': len(actual.get('changes', []))
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
            for change in validated_changes:
                staff_id = change['staffId']
                day = str(change['day'])
                new_shift = change['to']
                if staff_id not in actual['shifts']:
                    actual['shifts'][staff_id] = {}
                old_shift = actual['shifts'][staff_id].get(day, '')
                actual['shifts'][staff_id][day] = new_shift
                actual['changes'].append({
                    'timestamp': datetime.now().isoformat(),
                    'staffId': staff_id, 'day': change['day'],
                    'from': old_shift, 'to': new_shift, 'reason': change.get('reason', '')
                })
            actual['lastUpdatedAt'] = datetime.now().isoformat()
            atomic_json_write(filepath, shift_data)
            return jsonify({'status': 'success', 'changesApplied': len(validated_changes)})
        except (OSError, IOError) as e:
            logger.exception("実績更新エラー: %s", e)
            return _error_response("実績データの更新に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "update_actual")

    @app.route("/api/actual/finalize", methods=["POST"])
    def finalize_actual():
        """実績データを確定"""
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
            return jsonify({'status': 'success', 'message': '実績を確定しました', 'finalizedAt': actual['finalizedAt']})
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
                parts = key.split('-')
                if len(parts) < 2:
                    continue
                year = int(parts[0])
                month = int(parts[1])
                filepath = os.path.join(shifts_dir, f"{year}-{month:02d}.json")
                staff_shifts = {}
                for shift_key, shift_val in shift_values.items():
                    sk_parts = shift_key.rsplit('-', 1)
                    if len(sk_parts) == 2:
                        staff_id, day = sk_parts
                        if staff_id not in staff_shifts:
                            staff_shifts[staff_id] = {}
                        staff_shifts[staff_id][day] = shift_val
                shift_data = {
                    "year": year, "month": month, "ward": ward_id,
                    "status": "draft", "selectedDraft": "移行データ",
                    "confirmedAt": None,
                    "drafts": {
                        "移行データ": {
                            "createdAt": datetime.now().isoformat(),
                            "score": 0, "shifts": staff_shifts
                        }
                    },
                    "confirmed": None, "changeHistory": []
                }
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
            return jsonify({'status': 'success', 'ward': ward_id, 'shiftMonths': migrated_months})
        except (OSError, IOError, ValueError) as e:
            logger.exception("LocalStorage移行エラー: %s", e)
            return _error_response("データ移行に失敗しました")
        except Exception as e:
            return _safe_internal_error(e, "migrate_localstorage")
