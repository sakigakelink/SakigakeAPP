// app.js - ESモジュール エントリーポイント
import { D, W, Y, M, setW, setY, setM, sel, HOLIDAYS, setHOLIDAYS, currentViewDraft, setCurrentViewDraft, isShuttingDown } from './state.js';
import { SHIFT_BTNS, WARDS } from './constants.js';
import { load, save, cleanupOldData, backupToServer, checkBackupStatus, saveWardSettings, loadWardSettings, loadWardSettingsFromServer, migrateStaffToBackend, restoreFromBackup, exportSettings, importSettings, updateBackupStatus, restartServer, shutdownApp } from './api.js';
import { renderStaff, openStaffModal, saveStaff, openImportModal, showImportSample, previewImport, execImport, syncStaffToBackend } from './staff.js';
import { render, changeMonth, updateMonth, renderConstraintRules, renderConstraintsTab } from './render.js';
import { loadDraftList, saveDraft, confirmShift, checkConfirmStatus, migrateShiftsToFiles } from './draft.js';
import { solve, openShift, setShift } from './shift.js';
import { exportPdf, exportJson } from './export.js';
import { loadShiftFileAndTrackActual } from './actual.js';
import './wish.js';

// migrateData は元のコードで呼び出されているが定義がないためスタブ化
function migrateData() {}

function init() {
    load();
    cleanupOldData();
    // ページロード時に自動バックアップ（サーバーにデータを同期）
    setTimeout(backupToServer, 1000);

    if (D.staff && D.staff.length > 0) {
        // LocalStorageに職員データあり → バックエンドとマージ（バックエンドにしかない職員を取り込む）
        migrateData();
        fetch("/api/employees/all")
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.status === "success" && res.staff && res.staff.length > 0) {
                    var localIds = {};
                    for (var i = 0; i < D.staff.length; i++) {
                        localIds[D.staff[i].id] = true;
                    }
                    var added = 0;
                    for (var j = 0; j < res.staff.length; j++) {
                        if (!localIds[res.staff[j].id]) {
                            D.staff.push(res.staff[j]);
                            added++;
                        }
                    }
                    if (added > 0) {
                        save();
                    }
                }
            })
            .catch(function(e) {
                console.error("バックエンドとのマージエラー:", e);
            })
            .finally(function() {
                syncStaffToBackend();
                continueInit();
            });
        return;
    } else {
        // LocalStorage空 → バックエンドから取得
        fetch("/api/employees/all")
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.status === "success" && res.staff && res.staff.length > 0) {
                    D.staff = res.staff;
                    save();
                }
            })
            .catch(function(e) {
                console.error("職員データ取得エラー:", e);
            })
            .finally(function() {
                migrateData();
                continueInit();
            });
    }
}

function continueInit() {
    // 祝日データをサーバーから取得
    fetch("/api/holidays")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var h = {};
            for (var i = 0; i < data.length; i++) {
                var parts = data[i].split("-");
                var key = parseInt(parts[0]) + "-" + parseInt(parts[1]) + "-" + parseInt(parts[2]);
                h[key] = 1;
            }
            setHOLIDAYS(h);
        })
        .catch(function (e) { console.warn("fetch error:", e); })
        .finally(function () {
            setupShiftButtons();
            bindEvents();
            setupWardTabs();
            updateMonth();
            render();
            renderStaff();
            renderConstraintRules();
            checkBackupStatus();
        });
}

function setupShiftButtons() {
    var container = document.getElementById("shiftButtons");
    var html = "";
    var hideLate = (W === "1" || W === "3");
    for (var i = 0; i < SHIFT_BTNS.length; i++) {
        var b = SHIFT_BTNS[i];
        if (hideLate && b.shift === "late") continue;
        html += "<button class=\"btn " + b.cls + "\" data-shift=\"" + b.shift + "\">" + b.label + "</button>";
    }
    container.innerHTML = html;
}

function bindEvents() {
    var tabs = document.querySelectorAll(".nav-tab");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].addEventListener("click", function () {
            var t = this;
            var allTabs = document.querySelectorAll(".nav-tab");
            var allContent = document.querySelectorAll(".tab-content");
            for (var j = 0; j < allTabs.length; j++) allTabs[j].classList.remove("active");
            for (var j = 0; j < allContent.length; j++) allContent[j].classList.remove("active");
            t.classList.add("active");
            document.getElementById("tab-" + t.getAttribute("data-tab")).classList.add("active");
        });
    }
    document.getElementById("prevMonth").addEventListener("click", function () { changeMonth(-1); });
    document.getElementById("nextMonth").addEventListener("click", function () { changeMonth(1); });
    document.getElementById("pdfBtn").addEventListener("click", exportPdf);
    document.getElementById("jsonBtn").addEventListener("click", exportJson);
    document.getElementById("clearBtn").addEventListener("click", function () {
        if (confirm("シフトをクリアしますか？（希望は残ります）")) {
            var sk = Y + "-" + M + "-" + W;
            var wk = Y + "-" + M;
            var wishes = D.wishes[wk] || [];
            // 希望由来のシフトを復元用に収集
            var keep = {};
            var staff = [];
            for (var i = 0; i < D.staff.length; i++) {
                if (D.staff[i].ward === W) staff.push(D.staff[i]);
            }
            var fixedIds = {};
            for (var i = 0; i < staff.length; i++) {
                if (staff[i].workType === "fixed") fixedIds[staff[i].id] = true;
            }
            for (var i = 0; i < wishes.length; i++) {
                var w = wishes[i];
                if (fixedIds[w.staffId] && w.days) {
                    for (var di = 0; di < w.days.length; di++) {
                        keep[w.staffId + "-" + w.days[di]] = w.shift;
                    }
                }
            }
            D.shifts[sk] = keep;
            // dayHoursも該当病棟月のデータをクリア
            if (D.dayHours) {
                var prefix = sk + "-";
                for (var key in D.dayHours) {
                    if (key.indexOf(prefix) === 0) {
                        delete D.dayHours[key];
                    }
                }
            }
            save();
            render();
        }
    });
    document.getElementById("closeShiftModal").addEventListener("click", function () {
        document.getElementById("shiftModal").classList.remove("active");
        document.getElementById("dayHoursWrap").style.display = "none";
    });
    var shiftBtns = document.querySelectorAll("#shiftButtons button");
    for (var i = 0; i < shiftBtns.length; i++) {
        shiftBtns[i].addEventListener("click", function () {
            var sh = this.getAttribute("data-shift");
            if (sh === "day") {
                // 日勤選択時は時間数入力パネルを表示
                var wrap = document.getElementById("dayHoursWrap");
                wrap.style.display = "block";
                var inp = document.getElementById("dayHoursInput");
                // 既存の時間数があればセット、なければデフォルト7.5
                if (sel) {
                    var s = null;
                    for (var j = 0; j < D.staff.length; j++) {
                        if (D.staff[j].id === sel.id) { s = D.staff[j]; break; }
                    }
                    var sk = Y + "-" + M + "-" + (s ? s.ward : W);
                    var dhKey = sk + "-" + sel.id + "-" + sel.d;
                    var existing = D.dayHours && D.dayHours[dhKey];
                    inp.value = (existing !== undefined && existing !== null && existing !== "") ? existing : 7.5;
                }
                inp.focus();
                inp.select();
            } else {
                document.getElementById("dayHoursWrap").style.display = "none";
                setShift(sh);
            }
        });
    }
    // 日勤時間数確定ボタン
    document.getElementById("dayHoursConfirm").addEventListener("click", function () {
        var hours = parseFloat(document.getElementById("dayHoursInput").value);
        if (isNaN(hours)) hours = 7.5;
        setShift("day", hours);
    });
    // Enterキーでも確定
    document.getElementById("dayHoursInput").addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            document.getElementById("dayHoursConfirm").click();
        }
    });
    document.getElementById("btnSolve").addEventListener("click", function () { solve(Math.floor(Math.random() * 10000) + 1); });
    document.getElementById("addStaffBtn").addEventListener("click", openStaffModal);
    document.getElementById("closeStaffModal").addEventListener("click", function () {
        document.getElementById("staffModal").classList.remove("active");
    });
    document.getElementById("cancelStaffBtn").addEventListener("click", function () {
        document.getElementById("staffModal").classList.remove("active");
    });
    document.getElementById("staffForm").addEventListener("submit", saveStaff);
    document.getElementById("staffWorkType").addEventListener("change", function () {
        // 固定シフトパターンは希望シフトで対応するため非表示のまま
    });
    document.getElementById("importStaffBtn").addEventListener("click", openImportModal);
    document.getElementById("closeImportModal").addEventListener("click", function () {
        document.getElementById("importModal").classList.remove("active");
    });
    document.getElementById("cancelImportBtn").addEventListener("click", function () {
        document.getElementById("importModal").classList.remove("active");
    });
    document.getElementById("sampleImportBtn").addEventListener("click", showImportSample);
    document.getElementById("previewImportBtn").addEventListener("click", previewImport);
    document.getElementById("execImportBtn").addEventListener("click", execImport);

    // 設定変更時に自動保存
    var settingIds = ["reqDayWeekday", "reqDayHoliday", "reqJunnya", "reqShinya", "reqLate", "maxLate"];
    for (var i = 0; i < settingIds.length; i++) {
        var el = document.getElementById(settingIds[i]);
        if (el) el.addEventListener("change", saveWardSettings);
    }
    // 曜日別日勤人数テーブル
    var DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    var prefixes = ["dayStaff", "minQual", "minAide"];
    for (var p = 0; p < prefixes.length; p++) {
        for (var d = 0; d < DAYS.length; d++) {
            var el2 = document.getElementById(prefixes[p] + DAYS[d]);
            if (el2) el2.addEventListener("change", saveWardSettings);
        }
    }
}

function setupWardTabs() {
    var html = "";
    for (var i = 0; i < WARDS.length; i++) {
        var w = WARDS[i];
        if (w.status === "preparing") {
            html += "<button class=\"ward-tab\" data-ward=\"" + w.id + "\" disabled style=\"opacity:.5;cursor:not-allowed\" title=\"準備中\">" + w.name + "（準備中）</button>";
        } else {
            html += "<button class=\"ward-tab" + (w.id === W ? " active" : "") + "\" data-ward=\"" + w.id + "\">" + w.name + "</button>";
        }
    }
    var ids = ["wardTabs", "autoWardTabs", "staffWardTabs", "constraintWardTabs"];
    for (var i = 0; i < ids.length; i++) {
        var el = document.getElementById(ids[i]);
        if (el) el.innerHTML = html;
    }

    // 初期表示時の設定反映（サーバーから読み込み）
    loadWardSettingsFromServer();

    var wts = document.querySelectorAll(".ward-tab");
    for (var i = 0; i < wts.length; i++) {
        wts[i].addEventListener("click", function () {
            if (this.disabled) return;
            saveWardSettings(); // 切替前に現在の設定を保存
            setW(this.getAttribute("data-ward"));
            // 病棟切替時にログをクリア
            var logEl = document.getElementById("log");
            if (logEl) { logEl.innerHTML = ""; logEl.style.display = "none"; }
            var checkLogEl = document.getElementById("checkLog");
            if (checkLogEl) { checkLogEl.innerHTML = ""; checkLogEl.style.display = "none"; }
            var all = document.querySelectorAll(".ward-tab");
            for (var j = 0; j < all.length; j++) all[j].classList.remove("active");
            var selTabs = document.querySelectorAll(".ward-tab[data-ward=\"" + W + "\"]");
            for (var j = 0; j < selTabs.length; j++) selTabs[j].classList.add("active");

            loadWardSettings(); // 切替後に設定を読み込み

            // 病棟切替時にサーバーからシフトデータを再取得
            setCurrentViewDraft(null);

            render();
            renderStaff();
            renderConstraintRules();
            renderConstraintsTab();
            checkConfirmStatus();
            loadShiftFileAndTrackActual();
        });
    }
}

// Window assignments for functions called from HTML onclick
window.saveDraft = saveDraft;
window.confirmShift = confirmShift;
window.migrateShiftsToFiles = migrateShiftsToFiles;
window.saveWardSettings = saveWardSettings;
window.loadWardSettings = loadWardSettings;
window.backupToServer = backupToServer;
window.restoreFromBackup = restoreFromBackup;
window.exportSettings = exportSettings;
window.importSettings = importSettings;
window.migrateStaffToBackend = migrateStaffToBackend;
window.restartServer = restartServer;
window.shutdownApp = shutdownApp;
window.setupShiftButtons = setupShiftButtons;

// 初期化
init();

// 実績ボタンの初期更新
setTimeout(function() { loadShiftFileAndTrackActual(); }, 1500);

// ウィンドウを閉じようとしたときに確認
window.addEventListener("beforeunload", function (e) {
    if (isShuttingDown) return;
    e.preventDefault();
    e.returnValue = "終了ボタンからアプリを終了してください";
    return e.returnValue;
});
