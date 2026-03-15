import { D, W, Y, M, ACTUAL_MODE, setACTUAL_MODE, actualData, setActualData, confirmedData, setConfirmedData, pendingActualChange, setPendingActualChange } from './state.js';
import { ABBR } from './constants.js';
import { escHtml, isHoliday } from './util.js';
import { save } from './api.js';
import { render } from './render.js';

// ========== 実績管理モード ==========

function updateActualButtons() {
    var btnGroup = document.getElementById("actualBtnGroup");
    var btnStart = document.getElementById("btnActualStart");
    var btnToggle = document.getElementById("btnModeToggle");
    var btnFinalize = document.getElementById("btnFinalizeActual");
    var btnYoshiki9 = document.getElementById("btnYoshiki9");

    // シフトデータの状態を確認
    var sk = Y + "-" + M + "-" + W;
    var shiftFile = D._shiftFiles && D._shiftFiles[sk];

    btnGroup.style.display = "none";
    btnStart.style.display = "none";
    btnToggle.style.display = "none";
    btnFinalize.style.display = "none";
    btnYoshiki9.style.display = "none";

    if (shiftFile) {
        btnGroup.style.display = "inline-flex";
        var status = shiftFile.status;
        if (status === "confirmed" && !shiftFile.actual) {
            btnStart.style.display = "inline-block";
        } else if (status === "actual" || (shiftFile.actual && !shiftFile.actual.finalizedAt)) {
            btnToggle.style.display = "inline-block";
            btnToggle.textContent = ACTUAL_MODE ? "予定に戻す" : "実績表示";
            btnFinalize.style.display = "inline-block";
        } else if (status === "finalized" || (shiftFile.actual && shiftFile.actual.finalizedAt)) {
            btnToggle.style.display = "inline-block";
            btnToggle.textContent = ACTUAL_MODE ? "予定に戻す" : "実績表示";
            btnYoshiki9.style.display = "inline-block";
        }
    }

    // 様式9ボタン: シフトデータがあれば常に表示（動作確認用に仮設定でもOK）
    if (hasAnyShiftData()) {
        btnYoshiki9.style.display = "inline-block";
    }
}

function hasAnyFinalizedData() {
    if (!D._shiftFiles) return false;
    for (var key in D._shiftFiles) {
        var sf = D._shiftFiles[key];
        if (sf && sf.actual && sf.actual.finalizedAt) return true;
    }
    return false;
}

function hasAnyShiftData() {
    if (!D._shiftFiles) return false;
    for (var key in D._shiftFiles) {
        var sf = D._shiftFiles[key];
        if (sf && sf.exists !== false && sf.selectedDraft) return true;
    }
    return false;
}

function startActualTracking() {
    if (!confirm("確定シフトから実績入力を開始しますか？")) return;
    fetch("/api/actual/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ward: W, year: Y, month: M })
    }).then(function(r) { return r.json(); })
    .then(function(res) {
        if (res.status === "success") {
            alert("実績入力を開始しました");
            loadShiftFileAndTrackActual();
            setACTUAL_MODE(true);
        } else {
            alert(res.message || "エラー");
        }
    }).catch(function(e) { alert("通信エラー: " + e); });
}

function toggleActualMode() {
    setACTUAL_MODE(!ACTUAL_MODE);
    if (ACTUAL_MODE) {
        loadActualData();
    } else {
        render();
    }
    updateActualButtons();
}

function loadActualData() {
    fetch("/api/actual/" + W + "/" + Y + "/" + M)
    .then(function(r) { return r.json(); })
    .then(function(res) {
        if (res.status === "success" && res.hasActual) {
            setActualData(res.actual.shifts || {});
            setConfirmedData((res.confirmed && res.confirmed.shifts) || {});
            renderActual();
        } else {
            alert("実績データがありません");
            setACTUAL_MODE(false);
            updateActualButtons();
        }
    }).catch(function(e) { alert("通信エラー: " + e); });
}

function renderActual() {
    // 実績モードではactualDataを使ってテーブルを描画
    // 既存のrender()を利用し、実績データを一時的にD.shiftsに注入
    var sk = Y + "-" + M + "-" + W;
    var backup = {};
    // フラット形式に変換
    for (var staffId in actualData) {
        for (var day in actualData[staffId]) {
            var key = staffId + "-" + day;
            backup[key] = D.shifts[sk] ? D.shifts[sk][key] : undefined;
            if (!D.shifts[sk]) D.shifts[sk] = {};
            D.shifts[sk][key] = actualData[staffId][day];
        }
    }

    render();

    // テーブルにdiff表示を追加
    var table = document.getElementById("shiftTable");
    if (!table) return;
    var rows = table.querySelectorAll("tr");
    for (var i = 1; i < rows.length; i++) {
        var row = rows[i];
        var staffCell = row.querySelector(".staff-cell");
        if (!staffCell) continue;
        var staffId = staffCell.getAttribute("data-staff-id");
        if (!staffId) continue;

        var cells = row.querySelectorAll(".shift-cell");
        cells.forEach(function(cell) {
            var day = cell.getAttribute("data-day");
            if (!day) return;
            var actualShift = actualData[staffId] && actualData[staffId][day] || "";
            var confirmedShift = confirmedData[staffId] && confirmedData[staffId][day] || "";
            if (actualShift !== confirmedShift) {
                cell.classList.add("shift-changed");
                cell.title = "予定: " + (ABBR[confirmedShift] || confirmedShift || "-") + " → 実績: " + (ABBR[actualShift] || actualShift || "-");
            }
        });
    }

    // ステータスバーを実績モードに更新
    var badge = document.getElementById("shiftStatusBadge");
    if (badge) {
        badge.className = "status-badge actual";
        badge.textContent = "実績";
    }
    var nameEl = document.getElementById("currentDraftName");
    if (nameEl) nameEl.textContent = "実績入力中";
}

function openActualReasonModal(staffId, day, newShift) {
    setPendingActualChange({ staffId: staffId, day: day, newShift: newShift });
    var staff = D.staff.find(function(s) { return s.id === staffId; });
    var name = staff ? staff.name : staffId;
    var el = document.getElementById("actualReasonInfo");
    el.textContent = name + " " + day + "日: " + (ABBR[newShift] || newShift || "クリア") + " に変更";
    document.getElementById("actualReasonInput").value = "";
    document.getElementById("actualReasonModal").classList.add("active");
    document.getElementById("actualReasonInput").focus();
}

function closeActualReasonModal() {
    document.getElementById("actualReasonModal").classList.remove("active");
    setPendingActualChange(null);
}

function submitActualChange() {
    if (!pendingActualChange) return;
    var reason = document.getElementById("actualReasonInput").value.trim();
    var change = {
        staffId: pendingActualChange.staffId,
        day: parseInt(pendingActualChange.day),
        to: pendingActualChange.newShift,
        reason: reason
    };

    fetch("/api/actual/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ward: W, year: Y, month: M, changes: [change] })
    }).then(function(r) { return r.json(); })
    .then(function(res) {
        if (res.status === "success") {
            // ローカルデータを更新
            if (!actualData[change.staffId]) actualData[change.staffId] = {};
            actualData[change.staffId][String(change.day)] = change.to;
            closeActualReasonModal();
            renderActual();
        } else {
            alert(res.message || "更新エラー");
        }
    }).catch(function(e) { alert("通信エラー: " + e); });
}

function finalizeActual() {
    if (!confirm("実績を確定しますか？確定後は変更できません。")) return;
    fetch("/api/actual/finalize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ward: W, year: Y, month: M })
    }).then(function(r) { return r.json(); })
    .then(function(res) {
        if (res.status === "success") {
            alert("実績を確定しました");
            loadShiftFileAndTrackActual();
            updateActualButtons();
        } else {
            alert(res.message || "確定エラー");
        }
    }).catch(function(e) { alert("通信エラー: " + e); });
}

function loadShiftFileAndTrackActual() {
    var sk = Y + "-" + M + "-" + W;
    var wardMap = { "1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou" };
    var wardId = wardMap[W] || W;
    fetch("/api/shift/" + W + "/" + Y + "/" + M)
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.exists !== false) {
            D._shiftFiles[sk] = data;
        }
        updateActualButtons();
    }).catch(function(e) { console.warn("fetch error:", e); });
}

// Exports
export {
    updateActualButtons,
    hasAnyFinalizedData,
    hasAnyShiftData,
    startActualTracking,
    toggleActualMode,
    loadActualData,
    renderActual,
    openActualReasonModal,
    closeActualReasonModal,
    submitActualChange,
    finalizeActual,
    loadShiftFileAndTrackActual
};

// Window assignments for HTML onclick and cross-module access
window.updateActualButtons = updateActualButtons;
window.hasAnyFinalizedData = hasAnyFinalizedData;
window.hasAnyShiftData = hasAnyShiftData;
window.startActualTracking = startActualTracking;
window.toggleActualMode = toggleActualMode;
window.loadActualData = loadActualData;
window.renderActual = renderActual;
window.openActualReasonModal = openActualReasonModal;
window.closeActualReasonModal = closeActualReasonModal;
window.submitActualChange = submitActualChange;
window.finalizeActual = finalizeActual;
window.loadShiftFileAndTrackActual = loadShiftFileAndTrackActual;
