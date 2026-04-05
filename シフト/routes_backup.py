"""バックアップ・設定・サーバー制御ルート"""
import os
import sys
import re
import time
import json as pyjson
import logging
import subprocess
import threading
from datetime import datetime
from flask import request, jsonify

from validation import ValidationError, validate_ward, validate_ward_settings, is_localhost

logger = logging.getLogger(__name__)


def register_backup_routes(app, BACKUP_DIR, atomic_json_write, _error_response, _safe_internal_error, _safe_exit, portal_mode=False):
    """バックアップ・設定・サーバー制御ルートを登録"""

    @app.route("/api/backup", methods=["POST"])
    def backup_save():
        """データをサーバーにバックアップ保存"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "データがありません"}), 400
            from validation import validate_backup_data
            try:
                validate_backup_data(data)
            except ValidationError as e:
                return jsonify({"status": "error", "message": e.message}), 400

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
            atomic_json_write(backup_file, data)
            latest_file = os.path.join(BACKUP_DIR, "backup_latest.json")
            atomic_json_write(latest_file, data)
            with open(latest_file, 'r', encoding='utf-8') as f:
                pyjson.load(f)
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
        """日次バックアップ概要"""
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
            existing = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    existing = pyjson.load(f)
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
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared")
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
                _safe_exit()

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
                _safe_exit()

            threading.Thread(target=restart_server).start()
            return jsonify({"status": "success", "message": "サーバーを再起動します"})
