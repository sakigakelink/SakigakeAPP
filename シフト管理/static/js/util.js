// util.js - ユーティリティ関数
import { HOLIDAYS } from './state.js';

export function escHtml(s) { var d = document.createElement("div"); d.appendChild(document.createTextNode(s)); return d.innerHTML; }

export function isHoliday(y, m, d) {
    var dt = new Date(y, m - 1, d);
    if (dt.getDay() === 0 || dt.getDay() === 6) return true;
    return HOLIDAYS[y + "-" + m + "-" + d] ? true : false;
}

export function getMonthlyOff(month) {
    if (month === 2) return 8;
    if (month === 5) return 10;
    return 9;
}

export function getWorkTypeBadge(wt) {
    var baseStyle = "display:inline-block;width:60px;text-align:center;padding:.2rem 0;border-radius:4px;font-size:.75rem;color:#fff;font-weight:bold";
    if (wt === "day_only") return "<span style=\"" + baseStyle + ";background:#6b7280\">日勤のみ</span>";
    if (wt === "2kohtai") return "<span style=\"" + baseStyle + ";background:#8b5cf6\">二交代</span>";
    if (wt === "3kohtai") return "<span style=\"" + baseStyle + ";background:#ec4899\">三交代</span>";
    if (wt === "night_only") return "<span style=\"" + baseStyle + ";background:#1e40af\">夜専従</span>";
    if (wt === "fixed") return "<span style=\"" + baseStyle + ";background:#6b7280\">固定</span>";
    return "";
}

export function getStaffTypeBadge(t) {
    var baseStyle = "font-size:.7rem;display:inline-block;width:60px;text-align:center;padding:2px 0;border-radius:4px";
    if (t === "nurse") return "<span style=\"" + baseStyle + ";background:#dbeafe;color:#1e40af\">看護師</span>";
    if (t === "junkango") return "<span style=\"" + baseStyle + ";background:#fef3c7;color:#92400e\">准看護師</span>";
    if (t === "nurseaide") return "<span style=\"" + baseStyle + ";background:#f3e8ff;color:#7c3aed\">NurseAide</span>";
    return "";
}

export function getStaffTypeColor(t) {
    if (t === "nurse") return "#dbeafe";
    if (t === "junkango") return "#fef3c7";
    if (t === "nurseaide") return "#f3e8ff";
    return "#f3f4f6";
}

/**
 * prevShiftsにwindow.confirmedPrevShiftsをマージ（異動職員対応）
 * @param {Object} prevShifts - ローカルの前月シフト（変更される）
 * @returns {{ shifts: Object, merged: number }} マージ後のシフトと補完件数
 */
export function mergePrevWithConfirmed(prevShifts) {
    var merged = 0;
    if (!window.confirmedPrevShifts) return { shifts: prevShifts, merged: 0 };
    if (Object.keys(prevShifts).length === 0) {
        return { shifts: window.confirmedPrevShifts, merged: Object.keys(window.confirmedPrevShifts).length };
    }
    var cps = window.confirmedPrevShifts;
    for (var cpk in cps) {
        if (cps.hasOwnProperty(cpk) && !prevShifts[cpk]) {
            prevShifts[cpk] = cps[cpk];
            merged++;
        }
    }
    return { shifts: prevShifts, merged: merged };
}
