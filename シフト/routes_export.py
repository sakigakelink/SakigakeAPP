"""シフトデータエクスポートルート（JSON/PDF）"""
import os
import calendar
import json as pyjson
import logging
from datetime import date
from io import BytesIO
from flask import request, jsonify, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from utils import HOLIDAYS
from shift_quality import check_labor_law_compliance, calculate_gini, calculate_cv, evaluate_gini_grade
from validation import ValidationError, validate_year, validate_month, validate_ward

logger = logging.getLogger(__name__)


def register_export_routes(app, SHIFT_ABBR, _error_response, _safe_internal_error):
    """エクスポートルートを登録"""

    @app.route("/export_json", methods=["POST"])
    def export_json():
        """シフトデータをJSON形式でエクスポート"""
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

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
            "year": year, "month": month, "numDays": num_days,
            "exportedAt": date.today().isoformat(), "staff": []
        }

        for s in staff_data:
            staff_shifts = []
            stats = {"day": 0, "night": 0, "off": 0, "consecutive_work_max": 0}
            consecutive = 0
            for d in range(1, num_days + 1):
                key = f"{s['id']}-{d}"
                sh = shifts.get(key, "")
                staff_shifts.append({"day": d, "shift": sh, "abbr": abbr.get(sh, sh)})
                if sh in ["day", "late"]:
                    stats["day"] += 1
                if sh in ["night2", "junnya", "shinya"]:
                    stats["night"] += 1
                if sh in ["off", "paid", "refresh"]:
                    stats["off"] += 1
                if sh and sh not in ["off", "paid", "refresh", "ake"]:
                    consecutive += 1
                    stats["consecutive_work_max"] = max(stats["consecutive_work_max"], consecutive)
                else:
                    consecutive = 0
            export_data["staff"].append({
                "id": s["id"], "name": s["name"],
                "workType": s.get("workType", "2kohtai"),
                "shifts": staff_shifts, "stats": stats
            })

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

        # 公平性指標
        night_counts, weekend_counts, consecutive_maxes, late_counts = [], [], [], []
        for s_data in export_data["staff"]:
            wt = s_data["workType"]
            if wt not in ["day_only", "fixed"]:
                night_counts.append(s_data["stats"]["night"])
                late_counts.append(sum(1 for sh in s_data["shifts"] if sh["shift"] == "late"))
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
            if not is_fixed_schedule:
                consecutive_maxes.append(s_data["stats"]["consecutive_work_max"])

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

        try:
            compliance_result = {"shifts": shifts}
            compliance_data = {
                "year": year, "month": month,
                "staff": staff_data, "config": {},
                "wishes": wishes, "prevMonthData": {},
            }
            export_data["laborCompliance"] = check_labor_law_compliance(compliance_result, compliance_data)
        except Exception:
            pass

        response = app.response_class(
            response=pyjson.dumps(export_data, ensure_ascii=False, indent=2),
            status=200, mimetype='application/json'
        )
        response.headers["Content-Disposition"] = f"attachment; filename=shift_{year}_{month:02d}.json"
        return response

    @app.route("/export_pdf", methods=["POST"])
    def export_pdf():
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        except Exception:
            pass

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "リクエストデータがありません"}), 400

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

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                               leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
        styles = getSampleStyleSheet()
        elements = []

        title_text = f"{year}年{month}月 勤務表"
        if creation_num and creation_num > 0:
            title_text += f"　［作成#{creation_num}］"
        title = Paragraph(f"<font name='HeiseiKakuGo-W5' size='14'>{title_text}</font>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 10))

        abbr = SHIFT_ABBR
        num_prev = len(prev_month_days)

        header = ["氏名"]
        for pd in prev_month_days:
            header.append(f"{pd['day']}\n(前)")
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        for d in range(1, num_days + 1):
            wd = weekdays[calendar.weekday(year, month, d)]
            header.append(f"{d}\n({wd})")
        header.extend(["日", "夜", "休"])
        table_data = [header]

        for s in staff_data:
            row = [s["name"]]
            for pd in prev_month_days:
                sh = pd.get("shifts", {}).get(s["id"], "")
                row.append(abbr.get(sh, sh))
            shifts_list = s.get("shifts", [])
            day_hours_list = s.get("dayHours", [])
            for idx, sh in enumerate(shifts_list):
                label = abbr.get(sh, sh)
                if sh == "day" and idx < len(day_hours_list) and day_hours_list[idx] is not None:
                    dh = float(day_hours_list[idx])
                    if dh != 7.5:
                        dh_str = str(int(dh)) if dh == int(dh) else str(dh)
                        label += dh_str
                row.append(label)
            day_count, night_count, off_count = 0, 0, 0
            wt = s.get("workType", "2kohtai")
            for sh in shifts_list:
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

        summary_color_info = []

        if ward == "1":
            day_nurse_summary = ["日勤(看護)"]
            for _ in range(num_prev):
                day_nurse_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts_list = s.get("shifts", [])
                    stype = s.get("type", "nurse")
                    if d <= len(shifts_list):
                        sh = shifts_list[d - 1]
                        if sh in ["day", "late"] and stype != "nurseaide":
                            count += 1
                day_nurse_summary.append(str(count))
            day_nurse_summary.extend(["", "", ""])
            table_data.append(day_nurse_summary)

            day_na_summary = ["日勤(NA)"]
            for _ in range(num_prev):
                day_na_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts_list = s.get("shifts", [])
                    stype = s.get("type", "nurse")
                    if d <= len(shifts_list):
                        sh = shifts_list[d - 1]
                        if sh in ["day", "late"] and stype == "nurseaide":
                            count += 1
                day_na_summary.append(str(count))
            day_na_summary.extend(["", "", ""])
            table_data.append(day_na_summary)

        _DS_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        def calc_day_req(day_of_month):
            dt = date(year, month, day_of_month)
            wd = dt.weekday()
            is_hol = (year, month, day_of_month) in HOLIDAYS
            if wd == 6 or is_hol:
                v = day_staff_by_day.get("sun")
                return v if v is not None else req_day_holiday
            key = _DS_KEYS[wd]
            v = day_staff_by_day.get(key)
            return v if v is not None else req_day_weekday

        day_summary = ["日勤計"]
        day_counts = []
        day_reqs = []
        for _ in range(num_prev):
            day_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts_list = s.get("shifts", [])
                if d <= len(shifts_list):
                    sh = shifts_list[d - 1]
                    if sh in ["day", "late"]:
                        count += 1
            day_summary.append(str(count))
            day_counts.append(count)
            day_reqs.append(calc_day_req(d))
        day_summary.extend(["", "", ""])
        table_data.append(day_summary)
        day_summary_row = len(table_data) - 1
        summary_color_info.append((day_summary_row, day_counts, day_reqs, "gte"))

        nurse_summary = ["看護師計"]
        for _ in range(num_prev):
            nurse_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts_list = s.get("shifts", [])
                if d <= len(shifts_list):
                    sh = shifts_list[d - 1]
                    if sh in ["day", "late"]:
                        stype = s.get("staffType", "nurse")
                        if stype in ["nurse", "junkango"]:
                            count += 1
            nurse_summary.append(str(count))
        nurse_summary.extend(["", "", ""])
        table_data.append(nurse_summary)

        aide_summary = ["補助者計"]
        for _ in range(num_prev):
            aide_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts_list = s.get("shifts", [])
                if d <= len(shifts_list):
                    sh = shifts_list[d - 1]
                    if sh in ["day", "late"]:
                        stype = s.get("staffType", "nurse")
                        if stype == "nurseaide":
                            count += 1
            aide_summary.append(str(count))
        aide_summary.extend(["", "", ""])
        table_data.append(aide_summary)

        junnya_summary = ["準夜帯"]
        junnya_counts = []
        for _ in range(num_prev):
            junnya_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts_list = s.get("shifts", [])
                if d <= len(shifts_list):
                    sh = shifts_list[d - 1]
                    if sh in ["night2", "junnya"]:
                        count += 1
            junnya_summary.append(str(count))
            junnya_counts.append(count)
        junnya_summary.extend(["", "", ""])
        table_data.append(junnya_summary)
        junnya_row = len(table_data) - 1
        summary_color_info.append((junnya_row, junnya_counts, [req_junnya] * num_days, "eq"))

        shinya_summary = ["深夜帯"]
        shinya_counts = []
        for _ in range(num_prev):
            shinya_summary.append("")
        for d in range(1, num_days + 1):
            count = 0
            for s in staff_data:
                shifts_list = s.get("shifts", [])
                if d <= len(shifts_list):
                    sh = shifts_list[d - 1]
                    if sh in ["ake", "shinya"]:
                        count += 1
            shinya_summary.append(str(count))
            shinya_counts.append(count)
        shinya_summary.extend(["", "", ""])
        table_data.append(shinya_summary)
        shinya_row = len(table_data) - 1
        summary_color_info.append((shinya_row, shinya_counts, [req_shinya] * num_days, "eq"))

        if ward == "2":
            late_summary = ["遅出"]
            late_counts_pdf = []
            for _ in range(num_prev):
                late_summary.append("")
            for d in range(1, num_days + 1):
                count = 0
                for s in staff_data:
                    shifts_list = s.get("shifts", [])
                    if d <= len(shifts_list):
                        sh = shifts_list[d - 1]
                        if sh == "late":
                            count += 1
                late_summary.append(str(count))
                late_counts_pdf.append(count)
            late_summary.extend(["", "", ""])
            table_data.append(late_summary)
            late_row = len(table_data) - 1
            summary_color_info.append((late_row, late_counts_pdf, [req_late] * num_days, "gte"))

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

        for d_idx in range(num_prev, num_prev + num_days):
            day_of_month = d_idx - num_prev + 1
            dt = date(year, month, day_of_month)
            is_sunday = dt.weekday() == 6
            is_holiday = (year, month, day_of_month) in HOLIDAYS
            if is_sunday or is_holiday:
                style.add('BACKGROUND', (d_idx + 1, 0), (d_idx + 1, -1), colors.Color(1, 0.9, 0.9))

        for s_idx, s in enumerate(staff_data):
            row_idx = s_idx + 1
            for d in range(1, num_days + 1):
                key = f"{s['id']}-{d}"
                if key in wish_map:
                    wish_shift = wish_map[key]
                    col_idx = num_prev + d
                    if wish_shift in ["off", "paid"]:
                        style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(0.73, 0.9, 0.99))
                    else:
                        style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(1, 0.84, 0.66))

        for idx in range(num_prev):
            style.add('BACKGROUND', (idx + 1, 0), (idx + 1, -1), colors.Color(0.95, 0.95, 0.95))

        color_ok = colors.Color(0.85, 0.95, 0.85)
        color_ng = colors.Color(1.0, 0.85, 0.85)
        for row_idx, counts, reqs, mode in summary_color_info:
            for di, (cnt, req) in enumerate(zip(counts, reqs)):
                col_idx = num_prev + di + 1
                if mode == "gte":
                    ok = cnt >= req
                else:
                    ok = cnt == req
                bg = color_ok if ok else color_ng
                style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg)
                if not ok:
                    style.add('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.Color(0.6, 0.1, 0.1))
                    style.add('FONTSIZE', (col_idx, row_idx), (col_idx, row_idx), 7)

        rest_shifts = {"off", "paid", "ake", "refresh"}
        for s_idx, s in enumerate(staff_data):
            if s.get("workType") == "fixed":
                continue
            row_idx = s_idx + 1
            shifts_list = s.get("shifts", [])
            prev_work = 0
            for pd in reversed(prev_month_days):
                pd_shifts = pd.get("shifts", {})
                psh = pd_shifts.get(s["id"], "")
                if not psh or psh in rest_shifts:
                    break
                prev_work += 1
            streak_start = 1
            current_streak = prev_work
            for d in range(1, num_days + 1):
                sh = shifts_list[d - 1] if d <= len(shifts_list) else ""
                is_work = sh and sh not in rest_shifts
                if is_work:
                    current_streak += 1
                else:
                    if current_streak >= 5:
                        for dd in range(streak_start, d):
                            col = num_prev + dd
                            style.add('LINEBELOW', (col, row_idx), (col, row_idx), 1.5, colors.red)
                    current_streak = 0
                    streak_start = d + 1
            if current_streak >= 5:
                for dd in range(streak_start, num_days + 1):
                    col = num_prev + dd
                    style.add('LINEBELOW', (col, row_idx), (col, row_idx), 1.5, colors.red)

        table.setStyle(style)
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return send_file(
            buffer, mimetype='application/pdf',
            as_attachment=True,
            download_name=f'shift_{year}_{month:02d}.pdf'
        )
