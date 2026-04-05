"""シフトソルバー関連ルート"""
import os
import sys
import time
import calendar
import json as pyjson
import logging
import subprocess
import tempfile
import threading
from datetime import date
from flask import Response, request, jsonify, stream_with_context

from solver import ShiftSolver
from shift_quality import check_labor_law_compliance
from validation import ValidationError, validate_solve_request

logger = logging.getLogger(__name__)


def register_solver_routes(app, _supplement_transfer_prevdata, _error_response, _safe_internal_error):
    """ソルバー関連ルートを登録"""

    @app.route("/solve", methods=["POST"])
    def solve_route():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400
            validated_data = validate_solve_request(data)
            data.update(validated_data)
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

        try:
            validated_data = validate_solve_request(data)
            data.update(validated_data)
        except ValidationError as e:
            return _error_response(e.message, 400, e.field)

        # 固定シフト職員: 希望入力（assign）をfixedShiftsにマージ
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

            num_days_check = calendar.monthrange(data.get("year", 2026), data.get("month", 1))[1]
            incomplete_fixed = []
            for fs in fixed_staff_list:
                if fs.get("fixedPattern"):
                    continue
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

        try:
            emp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared", "employees.json")
            with open(emp_path, "r", encoding="utf-8") as f:
                data["allEmployees"] = pyjson.load(f)
        except Exception:
            data["allEmployees"] = []

        def generate():
            cfg = data.get("config", {})
            num_cores = os.cpu_count() or 4

            staff = data.get("staff", [])
            solver_staff = [s for s in staff if s.get("workType") not in ("fixed", "flexRequest")]
            num_staff = len(solver_staff)
            num_days = calendar.monthrange(data.get("year", 2026), data.get("month", 1))[1]

            mode_labels = {
                "quick": "⚡通常（15秒）",
                "balanced": "⚡バランス（45秒）",
                "quality": "💎品質重視（90秒）",
                "pool": "🎯複数案生成（50秒）",
            }
            mode_label = mode_labels.get(solve_mode, "⚡通常（15秒）")

            monthly_off_val = cfg.get('monthlyOff', '?')
            month_val = data.get('month', '?')
            yield f"data: {pyjson.dumps({'type': 'info', 'msg': f'職員{num_staff}名、{num_days}日間（{num_cores}コア）- {mode_label}【公休{monthly_off_val}日/月={month_val}】'})}\n\n"

            yield f"data: {pyjson.dumps({'type': 'attempt', 'num': 1, 'msg': '厳密解法で開始（制約緩和なし）'})}\n\n"

            total_start = time.time()
            solver_script = os.path.join(os.path.dirname(__file__), "solver_subprocess.py")
            input_json = pyjson.dumps(data, ensure_ascii=False).encode("utf-8")

            result_fd, result_path = tempfile.mkstemp(suffix=".json", prefix="solver_result_")
            os.close(result_fd)

            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW
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

            if res is None:
                logger.error("ソルバーサブプロセス失敗 (code=%s)", proc.returncode)
                res = {"status": "error", "message": "ソルバーが異常終了しました。OR-Toolsの内部エラーの可能性があります。"}

            total_elapsed = round(time.time() - total_start, 2)

            if res and res.get("status", "").lower() == "pool":
                count = res.get("count", 0)
                res["totalTime"] = total_elapsed
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
