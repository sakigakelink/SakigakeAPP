import { D, W, Y, M, currentViewDraft } from './state.js';
import { ABBR, WARDS } from './constants.js';
import { escHtml, isHoliday, getMonthlyOff } from './util.js';

function exportPdf() {
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }

    var days = new Date(Y, M, 0).getDate();
    var sk = Y + "-" + M + "-" + W;

    // 前月末2日分を取得
    var prevMonthDays = [];
    var prevY = Y, prevM = M - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var pDays = new Date(prevY, prevM, 0).getDate();
    var pSk = prevY + "-" + prevM + "-" + W;
    var pShifts = D.shifts[pSk] || {};

    // 前々日と前日 (pDays-1, pDays)
    var targetDays = [pDays - 1, pDays];
    for (var k = 0; k < targetDays.length; k++) {
        var d = targetDays[k];
        if (d < 1) continue; // 月初日が1日未満になることはないが一応
        var shiftsMap = {};
        for (var i = 0; i < staff.length; i++) {
            var sid = staff[i].id;
            shiftsMap[sid] = pShifts[sid + "-" + d] || "";
        }
        prevMonthDays.push({
            day: d,
            shifts: shiftsMap
        });
    }

    // Wishes for highlighting in PDF
    var wk = Y + "-" + M;
    var wishes = D.wishes[wk] || [];
    var wishMap = {};
    for (var i = 0; i < wishes.length; i++) {
        var w = wishes[i];
        if (w.days) {
            for (var j = 0; j < w.days.length; j++) {
                wishMap[w.staffId + "-" + w.days[j]] = w.shift;
            }
        }
    }

    if (!D.shiftCreationNum) D.shiftCreationNum = {};
    var creationNum = D.shiftCreationNum[sk] || 0;

    // dayHoursをstaff別に整理
    var dayHoursMap = {};
    if (D.dayHours) {
        var prefix = sk + "-";
        for (var dhk in D.dayHours) {
            if (dhk.indexOf(prefix) === 0) {
                // prefix後のstaffId-dayを取得
                var remainder = dhk.substring(prefix.length);
                dayHoursMap[remainder] = D.dayHours[dhk];
            }
        }
    }

    var payload = {
        year: Y,
        month: M,
        ward: W,
        creationNum: creationNum,
        prevMonthDays: prevMonthDays,
        staff: staff.map(function (s) {
            var shifts = [];
            var hours = [];
            for (var d = 1; d <= days; d++) {
                shifts.push(D.shifts[sk][s.id + "-" + d] || "");
                var dh = dayHoursMap[s.id + "-" + d];
                hours.push(dh !== undefined ? dh : null);
            }
            return {
                id: s.id,
                name: s.name,
                type: s.type,
                workType: s.workType || "2kohtai",
                shifts: shifts,
                dayHours: hours
            };
        }),
        wishMap: wishMap,
        config: (function() {
            var cfg = {
                reqDayWeekday: parseInt(document.getElementById("reqDayWeekday").value) || 7,
                reqDayHoliday: parseInt(document.getElementById("reqDayHoliday").value) || 5,
                reqJunnya: parseInt(document.getElementById("reqJunnya").value) || 2,
                reqShinya: parseInt(document.getElementById("reqShinya").value) || 2,
                reqLate: parseInt(document.getElementById("reqLate").value) || 1
            };
            var dsbd = {};
            var _days = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
            var _keys = ["sun","mon","tue","wed","thu","fri","sat"];
            for (var i = 0; i < _days.length; i++) {
                var el = document.getElementById("dayStaff" + _days[i]);
                dsbd[_keys[i]] = el && el.value !== "" ? parseInt(el.value) : null;
            }
            cfg.dayStaffByDay = dsbd;
            return cfg;
        })()
    };

    fetch("/export_pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            var pdfName = "shift_" + Y + "_" + (M < 10 ? "0" + M : M);
            if (creationNum > 0) pdfName += "_No" + creationNum;
            a.download = pdfName + ".pdf";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        })
        .catch(function (e) {
            alert("PDF出力エラー: " + e.message);
        });
}

function exportJson() {
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }

    var days = new Date(Y, M, 0).getDate();
    var sk = Y + "-" + M + "-" + W;
    var shifts = D.shifts[sk] || {};

    // Wishes
    var wk = Y + "-" + M;
    var wishes = D.wishes[wk] || [];

    var payload = {
        year: Y,
        month: M,
        staff: staff,
        shifts: shifts,
        wishes: wishes
    };

    fetch("/export_json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = "shift_" + Y + "_" + (M < 10 ? "0" + M : M) + ".json";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        })
        .catch(function (e) {
            alert("JSON出力エラー: " + e.message);
        });
}

// ========== 様式9出力 ==========
function showYoshiki9Dialog() {
    var modal = document.getElementById("yoshiki9Modal");
    // 年月セレクタを設定
    var ySelect = document.getElementById("y9Year");
    var mSelect = document.getElementById("y9Month");
    ySelect.innerHTML = "";
    for (var y = Y - 1; y <= Y + 1; y++) {
        var opt = document.createElement("option");
        opt.value = y; opt.textContent = y + "年";
        if (y === Y) opt.selected = true;
        ySelect.appendChild(opt);
    }
    mSelect.innerHTML = "";
    for (var m = 1; m <= 12; m++) {
        var opt = document.createElement("option");
        opt.value = m; opt.textContent = m + "月";
        if (m === M) opt.selected = true;
        mSelect.appendChild(opt);
    }
    checkYoshiki9Status();
    modal.classList.add("active");
}

function closeYoshiki9Modal() {
    document.getElementById("yoshiki9Modal").classList.remove("active");
}

function checkYoshiki9Status() {
    var y = parseInt(document.getElementById("y9Year").value);
    var m = parseInt(document.getElementById("y9Month").value);
    fetch("/api/yoshiki9/status?year=" + y + "&month=" + m)
    .then(function(r) { return r.json(); })
    .then(function(res) {
        var el = document.getElementById("y9Status");
        if (res.status === "success") {
            var html = "<div style='font-weight:600;margin-bottom:.3rem'>実績確定状況:</div>";
            var wards = res.wards || {};
            ["ichiboutou", "nibyoutou", "sanbyoutou"].forEach(function(wid, i) {
                var wname = ["1病棟", "2病棟", "3病棟"][i];
                var info = wards[wid];
                if (info && info.finalized) {
                    html += "<div style='color:#10b981'>✓ " + wname + " - 確定済み (" + info.finalizedAt + ")</div>";
                } else if (info && info.hasActual) {
                    html += "<div style='color:#f59e0b'>◎ " + wname + " - 実績入力中（未確定）</div>";
                } else {
                    html += "<div style='color:#ef4444'>✗ " + wname + " - 実績未開始</div>";
                }
            });
            el.innerHTML = html;
        }
    }).catch(function(e) { console.warn("fetch error:", e); });
}

function generateYoshiki9(type) {
    var y = parseInt(document.getElementById("y9Year").value);
    var m = parseInt(document.getElementById("y9Month").value);
    var patients = {
        ward1: parseInt(document.getElementById("y9Patients1").value) || 58,
        ward2: parseInt(document.getElementById("y9Patients2").value) || 42,
        ward3: parseInt(document.getElementById("y9Patients3").value) || 58
    };

    var btn = event.target;
    btn.disabled = true;
    btn.textContent = "生成中...";

    // dayHoursデータをLocalStorageから取得して送信
    var dayHoursForY9 = {};
    if (D.dayHours) {
        for (var dhk in D.dayHours) {
            // キー形式: "year-month-ward-staffId-day" → "staffId-day" に変換
            var parts = dhk.split("-");
            if (parts.length >= 5) {
                var dhYear = parseInt(parts[0]);
                var dhMonth = parseInt(parts[1]);
                if (dhYear === y && dhMonth === m) {
                    // staffId-day (parts[3以降])
                    var staffDay = parts.slice(3).join("-");
                    dayHoursForY9[staffDay] = D.dayHours[dhk];
                }
            }
        }
    }

    fetch("/api/yoshiki9/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year: y, month: m, type: type, patients: patients, dayHours: dayHoursForY9 })
    }).then(function(r) {
        if (!r.ok) return r.json().then(function(j) { throw new Error(j.message || "エラー"); });
        var disposition = r.headers.get("Content-Disposition") || "";
        var filename = null;
        // RFC 5987: filename*=UTF-8''... (日本語対応)
        var matchStar = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (matchStar) {
            filename = decodeURIComponent(matchStar[1]);
        } else {
            var matchPlain = disposition.match(/filename=([^;]+)/);
            if (matchPlain) filename = matchPlain[1].replace(/"/g, "");
        }
        return r.blob().then(function(blob) { return { blob: blob, filename: filename }; });
    }).then(function(data) {
        var url = URL.createObjectURL(data.blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = data.filename || "yoshiki9_" + y + "_" + String(m).padStart(2, "0") + ".xlsx";
        a.click();
        URL.revokeObjectURL(url);
    }).catch(function(e) {
        alert("生成エラー: " + e.message);
    }).finally(function() {
        btn.disabled = false;
        btn.textContent = btn.getAttribute("data-original-text") || btn.textContent.replace("生成中...", "");
        // テキスト復元が難しいのでページリロードはしない
    });
}

export { exportPdf, exportJson, showYoshiki9Dialog, closeYoshiki9Modal, checkYoshiki9Status, generateYoshiki9 };

window.exportPdf = exportPdf;
window.exportJson = exportJson;
window.showYoshiki9Dialog = showYoshiki9Dialog;
window.closeYoshiki9Modal = closeYoshiki9Modal;
window.checkYoshiki9Status = checkYoshiki9Status;
window.generateYoshiki9 = generateYoshiki9;
