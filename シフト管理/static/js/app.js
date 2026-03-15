function escHtml(s) { var d = document.createElement("div"); d.appendChild(document.createTextNode(s)); return d.innerHTML; }
var ABBR = { day: "日", late: "遅", night2: "夜", junnya: "準", shinya: "深", off: "休", paid: "有", ake: "明", refresh: "リ" };
var WARDS = [{ id: "1", name: "一病棟" }, { id: "2", name: "二病棟" }, { id: "3", name: "三病棟" }];
var WORK_TYPES = { day_only: "日勤のみ", "2kohtai": "二交代", "3kohtai": "三交代", night_only: "夜勤専従", fixed: "固定シフト" };
var HOLIDAYS = {};
var SHIFT_BTNS = [
    { shift: "day", label: "日勤", cls: "shift-day" },
    { shift: "late", label: "遅出", cls: "shift-late" },
    { shift: "night2", label: "夜勤", cls: "shift-night2" },
    { shift: "junnya", label: "準夜", cls: "shift-junnya" },
    { shift: "shinya", label: "深夜", cls: "shift-shinya" },
    { shift: "off", label: "休み", cls: "shift-off" },
    { shift: "paid", label: "有給", cls: "shift-paid" },
    { shift: "ake", label: "明け", cls: "shift-ake" },
    { shift: "refresh", label: "リフレッシュ", cls: "shift-refresh" },
    { shift: "", label: "クリア", cls: "btn-secondary" }
];
var D = { staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} };
var _now = new Date();
var Y = _now.getMonth() === 11 ? _now.getFullYear() + 1 : _now.getFullYear();
var M = _now.getMonth() === 11 ? 1 : _now.getMonth() + 2;
var W = "2";
var sel = null;
var currentViewDraft = null; // 現在表示中の案名
var compareDraftShifts = null; // 比較対象のシフトデータ（フラット形式）
var compareDraftName = null; // 比較対象の案名
var solveTimer = null;
var solveStartTime = null;
var solveChartData = [];
var solveAttemptNum = 0;

function isHoliday(y, m, d) {
    var dt = new Date(y, m - 1, d);
    if (dt.getDay() === 0 || dt.getDay() === 6) return true;
    return HOLIDAYS[y + "-" + m + "-" + d] ? true : false;
}

function saveWardSettings() {
    if (!D.wardSettings) D.wardSettings = {};
    var settings = {
        reqDayWeekday: parseInt(document.getElementById("reqDayWeekday").value) || 7,
        reqDayHoliday: parseInt(document.getElementById("reqDayHoliday").value) || 5,
        reqJunnya: parseInt(document.getElementById("reqJunnya").value) || 2,
        reqShinya: parseInt(document.getElementById("reqShinya").value) || 2,
        reqLate: parseInt(document.getElementById("reqLate").value) || 1,
        maxLate: parseInt(document.getElementById("maxLate").value) || 4
    };
    D.wardSettings[W] = settings;
    save();

    // サーバーにも保存し、成功後にサーバーから最新設定を再読込
    fetch("/api/settings/ward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wardId: W, settings: settings })
    }).then(function(r) { return r.json(); })
    .then(function(res) {
        if (res.status === "error") {
            alert("設定保存エラー: " + (res.message || "不明なエラー"));
            loadWardSettingsFromServer();
        }
    }).catch(function(e) { console.warn("fetch error:", e); });
}

function getMonthlyOff(month) {
    if (month === 2) return 8;
    if (month === 5) return 10;
    return 9;
}

function loadWardSettings() {
    // 病棟別デフォルト値（三病棟は準夜3・深夜2、一・三病棟は遅出なし）
    var defaults = (W === "3") ? {
        reqDayWeekday: 7, reqDayHoliday: 5, reqJunnya: 3, reqShinya: 2,
        reqLate: 0, maxLate: 0
    } : (W === "1") ? {
        reqDayWeekday: 7, reqDayHoliday: 5, reqJunnya: 2, reqShinya: 2,
        reqLate: 0, maxLate: 0
    } : {
        reqDayWeekday: 7, reqDayHoliday: 5, reqJunnya: 2, reqShinya: 2,
        reqLate: 1, maxLate: 4
    };
    var s = D.wardSettings && D.wardSettings[W] ? D.wardSettings[W] : defaults;
    document.getElementById("reqDayWeekday").value = s.reqDayWeekday;
    document.getElementById("reqDayHoliday").value = s.reqDayHoliday;
    document.getElementById("reqJunnya").value = s.reqJunnya;
    document.getElementById("reqShinya").value = s.reqShinya;
    // 一病棟・三病棟は遅出なし（UI非表示、値は0にセット）
    var hideLate = (W === "1" || W === "3");
    document.getElementById("reqLate").value = hideLate ? 0 : s.reqLate;
    document.getElementById("maxLate").value = hideLate ? 0 : s.maxLate;
    var rlw = document.getElementById("reqLateWrap");
    var mlw = document.getElementById("maxLateWrap");
    if (rlw) rlw.style.display = hideLate ? "none" : "";
    if (mlw) mlw.style.display = hideLate ? "none" : "";
    // 公休日数は月で決まるため、読込後に上書き
    var mo = document.getElementById("monthlyOff");
    if (mo) {
        mo.value = getMonthlyOff(M);
    }
}

function loadWardSettingsFromServer() {
    // サーバーから設定を読み込み、LocalStorageにマージ
    fetch("/api/settings/ward")
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success" && res.data) {
                if (!D.wardSettings) D.wardSettings = {};
                for (var wardId in res.data) {
                    // サーバーの設定で上書き（サーバー優先）
                    D.wardSettings[wardId] = res.data[wardId];
                }
                save();
                loadWardSettings();  // 現在の病棟の設定をUIに反映
            }
        })
        .catch(function(e) { console.warn("fetch error:", e); });
}


function init() {
    load();
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
            HOLIDAYS = {};
            for (var i = 0; i < data.length; i++) {
                var parts = data[i].split("-");
                var key = parseInt(parts[0]) + "-" + parseInt(parts[1]) + "-" + parseInt(parts[2]);
                HOLIDAYS[key] = 1;
            }
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

function checkBackupStatus() {
    fetch("/api/backup/load")
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                updateBackupStatus("💾 " + res.timestamp);
            }
        })
        .catch(function (e) { console.warn("fetch error:", e); });
}

function load() {
    var s = localStorage.getItem("sakigakeData");
    if (s) {
        try {
            D = JSON.parse(s);
        } catch (e) {
            console.error("LocalStorageデータ破損 - 初期状態で起動:", e);
            alert("保存データが破損していたため初期状態で起動します。バックアップから復元してください。");
            D = { staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} };
        }
    }
    if (!D.dayHours) D.dayHours = {};
}

var backupTimer = null;
function save() {
    localStorage.setItem("sakigakeData", JSON.stringify(D));

    // デバウンス付き自動バックアップ（3秒後）
    if (backupTimer) clearTimeout(backupTimer);
    backupTimer = setTimeout(function () {
        backupToServer();
    }, 3000);
}

function backupToServer() {
    fetch("/api/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(D)
    })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                updateBackupStatus("✅ " + new Date().toLocaleString("ja-JP"));
            } else {
                updateBackupStatus("❌ バックアップ失敗");
            }
        })
        .catch(function (e) {
            updateBackupStatus("❌ 接続エラー");
        });
}

function restoreFromBackup() {
    if (!confirm("サーバーのバックアップからデータを復元しますか？\n現在のデータは上書きされます。")) return;

    fetch("/api/backup/load")
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                D = res.data;
                save();
                alert("バックアップを復元しました（" + res.timestamp + "）");
                location.reload();
            } else if (res.status === "empty") {
                alert("バックアップがありません");
            } else {
                alert("復元エラー: " + res.message);
            }
        })
        .catch(function (e) {
            alert("接続エラー");
        });
}

function migrateStaffToBackend() {
    if (!D.staff || D.staff.length === 0) {
        alert("移行する職員データがありません");
        return;
    }

    var msg = "LocalStorageの職員データ（" + D.staff.length + "名）を\nshared/employees.json に移行しますか？\n\n既存のemployees.jsonは上書きされます。";
    if (!confirm(msg)) return;

    fetch("/api/staff/migrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staff: D.staff })
    })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                var summary = "移行完了！\n\n";
                summary += "合計: " + res.total + "名\n";
                if (res.byWard) {
                    if (res.byWard.ichiboutou) summary += "1病棟: " + res.byWard.ichiboutou + "名\n";
                    if (res.byWard.nibyoutou) summary += "2病棟: " + res.byWard.nibyoutou + "名\n";
                    if (res.byWard.sanbyoutou) summary += "3病棟: " + res.byWard.sanbyoutou + "名\n";
                }
                alert(summary);
            } else {
                alert("移行エラー: " + res.message);
            }
        })
        .catch(function (e) {
            alert("接続エラー: " + e.message);
        });
}

// ========== ドラフト管理機能 ==========

function loadDraftList() {
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";
    var wardName = W === "1" ? "一病棟" : W === "2" ? "二病棟" : "三病棟";

    fetch("/api/shift/" + wardId + "/" + Y + "/" + M)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var listEl = document.getElementById("draftList");
            var statusBadge = document.getElementById("shiftStatusBadge");
            var statusDetail = document.getElementById("shiftStatusDetail");
            var draftNameEl = document.getElementById("currentDraftName");
            var contextEl = document.getElementById("shiftStatusContext");

            // シフトデータをキャッシュ（実績ボタン表示用・比較用）
            if (!D._shiftFiles) D._shiftFiles = {};
            var sk = Y + "-" + M + "-" + W;
            if (data.exists !== false) {
                D._shiftFiles[sk] = data;
            }
            window._lastDraftData = data;
            updateActualButtons();

            // コンテキスト表示（常に）
            if (contextEl) {
                contextEl.textContent = Y + "年" + M + "月 / " + wardName;
            }

            if (!data.exists) {
                listEl.innerHTML = "<div style='color:var(--text2)'>保存されたパターンはありません</div>";
                statusBadge.className = "status-badge draft";
                statusBadge.textContent = "仮";
                if (draftNameEl) draftNameEl.textContent = "未保存";
                statusDetail.textContent = "";
                return;
            }

            // ステータス表示
            if (data.status === "finalized" || (data.actual && data.actual.finalizedAt)) {
                statusBadge.className = "status-badge finalized";
                statusBadge.textContent = "実績確定";
                if (draftNameEl) draftNameEl.textContent = data.selectedDraft || "確定済み";
                statusDetail.textContent = data.actual && data.actual.finalizedAt ? "実績確定日: " + data.actual.finalizedAt.slice(0, 10) : "";
            } else if (data.status === "actual" || (data.actual && !data.actual.finalizedAt)) {
                statusBadge.className = "status-badge actual";
                statusBadge.textContent = "実績入力中";
                if (draftNameEl) draftNameEl.textContent = data.selectedDraft || "確定済み";
                statusDetail.textContent = data.actual && data.actual.startedAt ? "実績開始日: " + data.actual.startedAt.slice(0, 10) : "";
            } else if (data.status === "confirmed") {
                statusBadge.className = "status-badge confirmed";
                statusBadge.textContent = "✓ 確定";
                if (draftNameEl) draftNameEl.textContent = data.selectedDraft || "確定済み";
                statusDetail.textContent = data.confirmedAt ? "確定日: " + data.confirmedAt.slice(0, 10) : "";
            } else {
                statusBadge.className = "status-badge draft";
                statusBadge.textContent = "仮";
                if (draftNameEl) draftNameEl.textContent = data.selectedDraft || "未選択";
                statusDetail.textContent = data.selectedDraft ? "" : "下の一覧から案を選択してください";
            }

            // ドラフト一覧
            var html = "";
            var drafts = data.drafts || {};
            for (var name in drafts) {
                var draft = drafts[name];
                var isSelected = name === data.selectedDraft;
                var score = draft.score || 0;
                var createdAt = draft.createdAt ? draft.createdAt.slice(0, 16).replace("T", " ") : "";

                html += "<div class='draft-item" + (isSelected ? " selected" : "") + "'>";
                html += "<span class='draft-name'>" + escHtml(name) + "</span>";
                html += "<span class='draft-score'>" + score + "点</span>";
                // ペナルティバッジ
                if (draft.shifts) {
                    html += "<span class='draft-penalties'>" + getDraftPenaltySummary(draft.shifts) + "</span>";
                }
                html += "<span class='draft-date'>" + createdAt + "</span>";
                if (isSelected) {
                    html += "<span class='draft-selected'>← 選択中</span>";
                }
                var isViewing = (name === currentViewDraft);
                if (!isViewing) {
                    html += "<button class='btn btn-secondary' onclick=\"loadDraft('" + name + "')\">表示</button>";
                } else {
                    html += "<span class='draft-selected'>表示中</span>";
                }
                // 比較ボタン（表示中でない案のみ）
                if (!isViewing) {
                    var isComparing = (name === compareDraftName);
                    if (isComparing) {
                        html += "<button class='btn btn-warning' onclick=\"clearCompareDraft()\">比較解除</button>";
                    } else {
                        html += "<button class='btn btn-secondary' onclick=\"setCompareDraft('" + name + "')\">比較</button>";
                    }
                }
                if (!isSelected) {
                    html += "<button class='btn btn-primary' onclick=\"selectDraft('" + name + "')\">仮に設定</button>";
                }
                if (!isViewing) {
                    html += "<button class='btn btn-danger' onclick=\"deleteDraft('" + name + "')\">削除</button>";
                }
                html += "</div>";
            }

            listEl.innerHTML = html || "<div style='color:var(--text2)'>保存されたパターンはありません</div>";

            // 選択中のドラフトがあれば自動的にシフトをロード（別の案を表示中でなければ）
            var shouldAutoLoad = data.selectedDraft && data.drafts[data.selectedDraft] && !currentViewDraft;
            if (shouldAutoLoad) {
                currentViewDraft = data.selectedDraft;
                var draftShifts = data.drafts[data.selectedDraft].shifts;
                var sk = Y + "-" + M + "-" + W;
                // 固定シフト者の既存データを保持
                var existingFixed = {};
                for (var k in (D.shifts[sk] || {})) {
                    var parts = k.split("-");
                    var sid = parts.slice(0, -1).join("-");
                    for (var fi = 0; fi < D.staff.length; fi++) {
                        if (D.staff[fi].id === sid && D.staff[fi].workType === "fixed") {
                            existingFixed[k] = D.shifts[sk][k];
                            break;
                        }
                    }
                }
                D.shifts[sk] = {};
                // 固定シフト者のデータを復元
                for (var k in existingFixed) {
                    D.shifts[sk][k] = existingFixed[k];
                }

                // 職員別形式からフラット形式に変換
                for (var staffId in draftShifts) {
                    var days = draftShifts[staffId];
                    for (var day in days) {
                        D.shifts[sk][staffId + "-" + day] = days[day];
                    }
                }
                // ドラフト読み込み時はdayHoursをクリア（自動生成はデフォルト7.5h）
                if (D.dayHours) {
                    var prefix = sk + "-";
                    for (var dhk in D.dayHours) {
                        if (dhk.indexOf(prefix) === 0) delete D.dayHours[dhk];
                    }
                }
                // 確定データにdayHoursがあれば復元
                if (data.confirmed && data.confirmed.dayHours) {
                    if (!D.dayHours) D.dayHours = {};
                    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";
                    var dhPrefix = Y + "-" + M + "-" + wardId + "-";
                    for (var dhKey in data.confirmed.dayHours) {
                        D.dayHours[sk + "-" + dhKey] = data.confirmed.dayHours[dhKey];
                    }
                    save();
                }
                render();
            }
        })
        .catch(function(e) {
            console.error("Draft list load error:", e);
        });
}

function saveDraft() {
    var defaultName = "案" + (Date.now() % 1000);
    var name = prompt("パターン名を入力", defaultName);
    if (!name) return;

    var sk = Y + "-" + M + "-" + W;
    var currentShifts = D.shifts[sk] || {};

    if (Object.keys(currentShifts).length === 0) {
        alert("保存するシフトがありません");
        return;
    }

    // スコア計算
    var metrics = calculateMetrics(Y, M, currentShifts);
    var score = metrics.totalScore || 0;

    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/shift/save-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            year: Y,
            month: M,
            name: name,
            shifts: currentShifts,
            score: score
        })
    })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                currentViewDraft = name;  // 保存した案を表示中に設定
                loadDraftList();
            } else {
                alert("保存エラー: " + res.message);
            }
        })
        .catch(function(e) {
            alert("接続エラー: " + e.message);
        });
}

function autoSaveDraft(shifts) {
    // 自動保存：生成完了時に自動的にサーバーに保存
    var now = new Date();
    var name = "自動_" +
        String(now.getMonth() + 1).padStart(2, "0") +
        String(now.getDate()).padStart(2, "0") + "_" +
        String(now.getHours()).padStart(2, "0") +
        String(now.getMinutes()).padStart(2, "0");

    var metrics = calculateMetrics(Y, M, shifts);
    var score = metrics.totalScore || 0;
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/shift/save-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            year: Y,
            month: M,
            name: name,
            shifts: shifts,
            score: score
        })
    })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                currentViewDraft = name;
                loadDraftList();
            }
        })
        .catch(function(e) { console.warn("auto-save error:", e); });
}

function selectDraft(name) {
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/shift/select-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            year: Y,
            month: M,
            name: name
        })
    })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                currentViewDraft = name;  // 選択した案を表示中に設定
                loadDraftList();
            } else {
                alert("選択エラー: " + res.message);
            }
        })
        .catch(function(e) {
            alert("接続エラー: " + e.message);
        });
}

function loadDraft(name) {
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/shift/" + wardId + "/" + Y + "/" + M)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data.exists || !data.drafts || !data.drafts[name]) {
                alert("パターンが見つかりません");
                return;
            }

            var draftShifts = data.drafts[name].shifts;
            var sk = Y + "-" + M + "-" + W;
            // 固定シフト者の既存データを保持
            var existingFixed = {};
            for (var k in (D.shifts[sk] || {})) {
                var parts = k.split("-");
                var sid = parts.slice(0, -1).join("-");
                for (var fi = 0; fi < D.staff.length; fi++) {
                    if (D.staff[fi].id === sid && D.staff[fi].workType === "fixed") {
                        existingFixed[k] = D.shifts[sk][k];
                        break;
                    }
                }
            }
            D.shifts[sk] = {};
            // 固定シフト者のデータを復元
            for (var k in existingFixed) {
                D.shifts[sk][k] = existingFixed[k];
            }

            // 職員別形式からフラット形式に変換
            for (var staffId in draftShifts) {
                var days = draftShifts[staffId];
                for (var day in days) {
                    D.shifts[sk][staffId + "-" + day] = days[day];
                }
            }
            // ドラフト読み込み時はdayHoursをクリア
            if (D.dayHours) {
                var prefix = sk + "-";
                for (var dhk in D.dayHours) {
                    if (dhk.indexOf(prefix) === 0) delete D.dayHours[dhk];
                }
            }

            // 表示中の案名を更新
            var draftNameEl = document.getElementById("currentDraftName");
            var statusDetail = document.getElementById("shiftStatusDetail");
            var isSelected = (name === data.selectedDraft);

            if (draftNameEl) {
                draftNameEl.textContent = name;
                if (!isSelected) {
                    draftNameEl.innerHTML = name + ' <span style="font-size:.75rem;color:#f59e0b">(プレビュー中)</span>';
                }
            }
            if (statusDetail && !isSelected) {
                statusDetail.textContent = "※この案は仮設定されていません";
            }

            currentViewDraft = name;
            save();
            render();
            loadDraftList(); // 削除ボタンの表示を更新
        })
        .catch(function(e) {
            alert("読み込みエラー: " + e.message);
        });
}

function deleteDraft(name) {
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/shift/delete-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            year: Y,
            month: M,
            name: name
        })
    })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                loadDraftList();
            } else {
                alert("削除エラー: " + res.message);
            }
        })
        .catch(function(e) {
            alert("接続エラー: " + e.message);
        });
}

function confirmShift() {
    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    // まず現在のシフトを保存
    var sk = Y + "-" + M + "-" + W;
    var currentShifts = D.shifts[sk] || {};

    if (Object.keys(currentShifts).length === 0) {
        alert("確定するシフトがありません。\n先にシフトを保存してください。");
        return;
    }

    // スコア計算
    var metrics = calculateMetrics(Y, M, currentShifts);
    var score = metrics.totalScore || 0;

    // 現在のシフトを自動保存してから確定
    fetch("/api/shift/save-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            year: Y,
            month: M,
            name: "確定版",
            shifts: currentShifts,
            score: score
        })
    })
        .then(function(r) { return r.json(); })
        .then(function() {
            // 仮選択
            return fetch("/api/shift/select-draft", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ward: wardId,
                    year: Y,
                    month: M,
                    name: "確定版"
                })
            });
        })
        .then(function(r) { return r.json(); })
        .then(function() {
            // dayHoursを該当月病棟分のみ抽出
            var dhForConfirm = {};
            if (D.dayHours) {
                var prefix = sk + "-";
                for (var dhk in D.dayHours) {
                    if (dhk.indexOf(prefix) === 0) {
                        // sk + "-staffId-day" → "staffId-day" を抽出
                        var remainder = dhk.substring(prefix.length);
                        dhForConfirm[remainder] = D.dayHours[dhk];
                    }
                }
            }
            // 確定
            return fetch("/api/shift/confirm", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ward: wardId,
                    year: Y,
                    month: M,
                    dayHours: dhForConfirm
                })
            });
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                alert(Y + "年" + M + "月のシフトを確定しました");
                loadDraftList();
            } else {
                alert("確定エラー: " + res.message);
            }
        })
        .catch(function(e) {
            alert("接続エラー: " + e.message);
        });
}

function checkConfirmStatus() {
    loadDraftList();
}

function migrateShiftsToFiles() {
    if (!confirm("LocalStorageのシフトデータを新システムに移行しますか？")) return;

    var wardId = W === "1" ? "ichiboutou" : W === "2" ? "nibyoutou" : "sanbyoutou";

    fetch("/api/migrate/localstorage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ward: wardId,
            shifts: D.shifts || {},
            shiftVersions: D.shiftVersions || {}
        })
    })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success") {
                alert("移行完了: " + res.shiftMonths + "ヶ月分");
                loadDraftList();
            } else {
                alert("移行エラー: " + res.message);
            }
        })
        .catch(function(e) {
            alert("接続エラー: " + e.message);
        });
}

function updateBackupStatus(msg) {
    var el = document.getElementById("backupStatus");
    if (el) el.textContent = msg;
}

var isShuttingDown = false;

function restartServer() {
    // バックアップ → サーバー再起動（新ブラウザが開く）→ このウィンドウを閉じる
    fetch("/api/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(D)
    })
        .then(function () {
            return fetch("/api/restart", { method: "POST" });
        })
        .then(function () {
            // サーバー側が新ブラウザを開くので、このウィンドウは閉じる
            setTimeout(function () {
                window.close();
                // window.close() が効かない場合はリロードで代替
                setTimeout(function () {
                    var attempts = 0;
                    (function tryReload() {
                        fetch("/health")
                            .then(function (r) {
                                if (r.ok) location.reload();
                                else throw new Error("not ready");
                            })
                            .catch(function () {
                                attempts++;
                                if (attempts < 20) setTimeout(tryReload, 500);
                                else location.reload();
                            });
                    })();
                }, 2000);
            }, 500);
        })
        .catch(function () {
            location.reload();
        });
}

function shutdownApp() {
    if (!confirm("アプリを終了しますか？\nデータは自動バックアップされています。")) return;

    isShuttingDown = true;

    // 最終バックアップ
    fetch("/api/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(D)
    })
        .then(function () {
            // サーバー終了
            return fetch("/api/shutdown", { method: "POST" });
        })
        .then(function () {
            // ブラウザを閉じる試行
            window.close();
            // 閉じれなかった場合は空白ページへ
            setTimeout(function () {
                document.body.innerHTML = "<h1 style='text-align:center;margin-top:100px'>サーバーが終了しました。このタブを閉じてください。</h1>";
            }, 500);
        })
        .catch(function () {
            isShuttingDown = false;
            alert("終了処理中にエラーが発生しました");
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
            W = this.getAttribute("data-ward");
            // 病棟切替時にログをクリア
            var logEl = document.getElementById("log");
            if (logEl) { logEl.innerHTML = ""; logEl.style.display = "none"; }
            var checkLogEl = document.getElementById("checkLog");
            if (checkLogEl) { checkLogEl.innerHTML = ""; checkLogEl.style.display = "none"; }
            var all = document.querySelectorAll(".ward-tab");
            for (var j = 0; j < all.length; j++) all[j].classList.remove("active");
            var sel = document.querySelectorAll(".ward-tab[data-ward=\"" + W + "\"]");
            for (var j = 0; j < sel.length; j++) sel[j].classList.add("active");

            loadWardSettings(); // 切替後に設定を読み込み

            // 病棟切替時にサーバーからシフトデータを再取得
            currentViewDraft = null;

            render();
            renderStaff();
            renderConstraintRules();
            renderConstraintsTab();
            checkConfirmStatus();
            loadShiftFileAndTrackActual();
        });
    }
}

function changeMonth(d) {
    M += d;
    if (M > 12) { M = 1; Y++; }
    if (M < 1) { M = 12; Y--; }
    // 月切替時にサーバーからシフトデータを再取得
    currentViewDraft = null;
    updateMonth();
    render();
    renderWishes();
    loadShiftFileAndTrackActual();
}

function updateMonth() {
    document.getElementById("currentMonth").textContent = Y + "年" + M + "月";
    // 月別公休数自動設定（月によって固定: 2月=8日, 5月=10日, 他=9日）
    var mo = document.getElementById("monthlyOff");
    if (mo) {
        if (M === 2) mo.value = 8;
        else if (M === 5) mo.value = 10;
        else mo.value = 9;
    }
    updateConstraintSummary();
    checkConfirmStatus();
    // 前月の確定シフトをプリロード（render用）
    loadConfirmedPrevShiftsForRender();
}

function loadConfirmedPrevShiftsForRender() {
    fetch("/api/shift/prev-month?ward=" + W + "&year=" + Y + "&month=" + M)
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success" && res.hasData) {
                window.confirmedPrevShifts = res.shifts;
            } else {
                window.confirmedPrevShifts = null;
            }
            // 確定シフトを読み込んだ後に再描画
            render();
        })
        .catch(function(e) {
            window.confirmedPrevShifts = null;
        });
}

function updateConstraintSummary() {
    var s = document.getElementById("constraintSummary");
    if (!s) return;
    var html = "";

    if (W === "1") {
        // 一病棟専用
        html += "<div style='color:var(--red);font-weight:bold;margin-bottom:.3rem'>🔴 必ず守る制約</div>";
        html += "<ul style='margin:0 0 .5rem 0;padding-left:1.2rem;font-size:.85rem'>";
        html += "<li>連続勤務 5日以下</li>";
        html += "<li>夜勤回数 ≤ 個人上限</li>";
        html += "<li>二交代: 夜勤→明け→休み</li>";
        html += "<li>三交代: 準夜連続 2回まで</li>";
        html += "<li>準夜→深夜 禁止、遅出→深夜 禁止</li>";
        html += "<li>準夜" + document.getElementById("reqJunnya").value + "人、深夜" + document.getElementById("reqShinya").value + "人</li>";
        html += "<li>夜勤・準夜・深夜: 准看護師2人は不可</li>";
        // 夜勤制限を動的表示
        var wardStaff = D.staff.filter(function (s) { return s.ward === W; });
        for (var ri = 0; ri < wardStaff.length; ri++) {
            var rs = wardStaff[ri];
            if (rs.nightRestriction === "junnya_only") {
                html += "<li>" + escHtml(rs.name) + ": 準夜のみ（深夜不可）</li>";
            } else if (rs.nightRestriction === "shinya_only") {
                html += "<li>" + escHtml(rs.name) + ": 深夜のみ（準夜不可）</li>";
            }
        }
        html += "</ul>";

        html += "<div style='color:var(--blue);font-weight:bold;margin-bottom:.3rem'>🔵 なるべく守る制約（ソフト）</div>";
        html += "<ul style='margin:0;padding-left:1.2rem;font-size:.85rem'>";
        html += "<li>準夜、深夜はなるべく看護師or准看護師1人+NurseAide1人</li>";
        html += "<li>連続勤務 4日以下が望ましい</li>";
        html += "<li>夜勤平準化: 二交代=2pt, 準/深=1pt</li>";
        html += "<li>日勤人数: 月木(基準) → 水金(-1) → 火土(-2) → 日祝(休日) [ソフト制約]</li>";
        html += "<li>準夜・深夜: 各設定人数</li>";
        html += "<li>公休日数: 設定日数（±許容範囲）</li>";
        html += "</ul>";
    } else {
        // 二病棟・他病棟は従来の表示
        var mo = document.getElementById("monthlyOff").value;
        html += "<ul>";
        html += "<li>公休数: <b>" + mo + "日</b></li>";
        if (M === 2) html += "<li><small>(2月のため8日に設定)</small></li>";
        if (M === 5) html += "<li><small>(5月のため10日に設定)</small></li>";
        html += "<li>日勤(平日): " + document.getElementById("reqDayWeekday").value + "名</li>";
        html += "<li style='font-size:.8rem;color:var(--text2);margin-left:1rem'>曜日調整: 月金(基準) → 木(+1) → 火水土(-1) [ソフト制約]</li>";
        html += "<li>日勤(休日): " + document.getElementById("reqDayHoliday").value + "名</li>";
        html += "<li>準夜/深夜: 各" + document.getElementById("reqJunnya").value + "名 (固定)</li>";
        if (W === "2") html += "<li>遅出: " + document.getElementById("reqLate").value + "名/日（個人上限" + document.getElementById("maxLate").value + "回/月）</li>";
        html += "</ul>";
        html += "<hr style='margin:0.5rem 0;border-top:1px dashed var(--border)'>";
        html += "<div style='font-size:.85rem;color:var(--text2)'><b>固定ルール:</b></div>";
        html += "<ul style='margin-top:0.2rem;font-size:.85rem;color:var(--text2)'>";
        html += "<li>6連勤禁止 (最大5連勤) / 連休: 最大2日</li>";
        html += "<li>準夜連続は2回まで</li>";
        html += "<li>インターバル確保 (準≠深, 夜→明→休)</li>";
        html += "<li>三交代: 正循環のみ</li>";
        html += "<li>深夜→休→深夜 より 深夜→深夜→休 優先</li>";
        html += "<li><b>夜勤平準化: 二交代=2pt, 準/深=1pt</b></li>";
        html += "</ul>";
    }
    s.innerHTML = html;
}

function renderConstraintRules() {
    updateConstraintSummary();
    renderConstraintsTab();
}

function renderConstraintsTab() {
    var body = document.getElementById("constraintsBody");
    if (!body) return;

    var wardStaff = D.staff.filter(function (s) { return s.ward === W; });
    var wardName = W === "1" ? "一病棟" : W === "2" ? "二病棟" : "三病棟";
    var rdw = parseInt(document.getElementById("reqDayWeekday").value) || 7;
    var rdh = parseInt(document.getElementById("reqDayHoliday").value) || 5;
    var rj = parseInt(document.getElementById("reqJunnya").value) || 2;
    var rs = parseInt(document.getElementById("reqShinya").value) || 2;
    var rl = (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("reqLate").value) || 1);
    var ml = (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("maxLate").value) || 4);
    var mo = parseInt(document.getElementById("monthlyOff").value) || 9;

    // 夜勤制限のある職員を収集
    var nightRestricted = [];
    for (var i = 0; i < wardStaff.length; i++) {
        var st = wardStaff[i];
        if (st.nightRestriction === "junnya_only") nightRestricted.push(st.name + " (準夜のみ/深夜不可)");
        else if (st.nightRestriction === "shinya_only") nightRestricted.push(st.name + " (深夜のみ/準夜不可)");
    }

    var secStyle = "margin-bottom:1.5rem";
    var headStyle = "font-size:1rem;font-weight:bold;margin-bottom:.8rem;padding-bottom:.4rem;border-bottom:2px solid";
    var tblStyle = "width:100%;border-collapse:collapse;font-size:.88rem";
    var thStyle = "text-align:left;padding:.5rem .8rem;background:var(--bg3);border:1px solid var(--border);white-space:nowrap";
    var tdStyle = "padding:.5rem .8rem;border:1px solid var(--border)";
    var tagH = "display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.75rem;font-weight:bold;color:#fff;margin-right:.3rem";

    var h = "";

    // ---- ヘッダー ----
    h += "<div style='margin-bottom:1rem;padding:.8rem;background:var(--bg2);border-radius:8px;border-left:4px solid var(--blue)'>";
    h += "<span style='font-size:1.1rem;font-weight:bold'>" + wardName + "</span> の制約ルール";
    h += "<span style='float:right;font-size:.85rem;color:var(--text2)'>" + Y + "年" + M + "月</span>";
    h += "</div>";

    // ==== セクション1: ハード制約（全体共通） ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#dc2626;color:#dc2626'>ハード制約（必ず守る）</div>";
    h += "<table style='" + tblStyle + "'>";
    h += "<tr><th style='" + thStyle + "' width='30%'>制約名</th><th style='" + thStyle + "'>内容</th><th style='" + thStyle + "' width='15%'>対象</th></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H1</span>1日1シフト</td>";
    h += "<td style='" + tdStyle + "'>各職員は1日に1つのシフトのみ割当</td><td style='" + tdStyle + "'>全員</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H2</span>公休日数</td>";
    h += "<td style='" + tdStyle + "'>月間公休 = <b>" + mo + "日</b>（リフレッシュ休暇分は加算）</td><td style='" + tdStyle + "'>固定以外</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H3</span>有給は希望日のみ</td>";
    h += "<td style='" + tdStyle + "'>希望登録のない日は有給を割り当てない</td><td style='" + tdStyle + "'>全員</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H4</span>6連勤禁止</td>";
    h += "<td style='" + tdStyle + "'>連続勤務は最大<b>5日</b>まで（off/paid/akeを休みとみなす）<br>前月末からの引き継ぎも考慮</td><td style='" + tdStyle + "'>固定以外</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H5</span>リフレッシュ休暇</td>";
    h += "<td style='" + tdStyle + "'>希望登録のない日はリフレッシュ休暇を割り当てない</td><td style='" + tdStyle + "'>全員</td></tr>";

    // 人員要件
    h += "<tr><td style='" + tdStyle + "' colspan='3' style='background:var(--bg3);font-weight:bold;padding:.4rem .8rem'>日別人員要件</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H6</span>日勤人数</td>";
    h += "<td style='" + tdStyle + "'>";
    if (W === "2") {
        h += "月木金: <b>" + rdw + "</b>名 / 火: <b>" + (rdw - 1) + "</b>名 / 水土: <b>" + (rdw - 2) + "</b>名 / 日祝: <b>" + rdh + "</b>名";
    } else {
        h += "平日: <b>" + rdw + "</b>名 / 水曜: <b>" + (rdw - 1) + "</b>名 / 日祝: <b>" + rdh + "</b>名";
    }
    h += "</td><td style='" + tdStyle + "'>日別</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H7</span>準夜帯人数</td>";
    h += "<td style='" + tdStyle + "'>毎日 <b>" + rj + "</b>名（night2 + junnya）</td><td style='" + tdStyle + "'>日別</td></tr>";

    h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H8</span>深夜帯人数</td>";
    h += "<td style='" + tdStyle + "'>毎日 <b>" + rs + "</b>名（shinya + ake）</td><td style='" + tdStyle + "'>日別</td></tr>";

    if (rl > 0) {
        h += "<tr><td style='" + tdStyle + "'><span style='" + tagH + ";background:#dc2626'>H9</span>遅出人数</td>";
        h += "<td style='" + tdStyle + "'>毎日 <b>" + rl + "</b>名 / 個人上限 <b>" + ml + "</b>回/月</td><td style='" + tdStyle + "'>日別</td></tr>";
    }

    h += "</table></div>";

    // ==== セクション2: 病棟固有のハード制約 ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#ea580c;color:#ea580c'>" + wardName + " 固有のハード制約</div>";
    h += "<table style='" + tblStyle + "'>";
    h += "<tr><th style='" + thStyle + "' width='30%'>制約名</th><th style='" + thStyle + "'>内容</th><th style='" + thStyle + "' width='15%'>対象</th></tr>";

    if (W === "1") {
        h += "<tr><td style='" + tdStyle + "'>遅出・早出完全禁止</td>";
        h += "<td style='" + tdStyle + "'>一病棟では遅出・早出シフトを一切割り当てない</td><td style='" + tdStyle + "'>全員</td></tr>";

        h += "<tr><td style='" + tdStyle + "'>NurseAide 2人夜勤禁止</td>";
        h += "<td style='" + tdStyle + "'>準夜帯・深夜帯で NurseAide が2人同時に入ることを禁止<br>(看護師 or 准看護師が必ず1人以上)</td><td style='" + tdStyle + "'>NurseAide</td></tr>";
    }

    if (W === "3") {
        h += "<tr><td style='" + tdStyle + "'>遅出完全禁止</td>";
        h += "<td style='" + tdStyle + "'>三病棟では遅出シフトを一切割り当てない</td><td style='" + tdStyle + "'>全員</td></tr>";
    }

    if (nightRestricted.length > 0) {
        h += "<tr><td style='" + tdStyle + "'>夜勤制限（個人別）</td>";
        h += "<td style='" + tdStyle + "'>";
        for (var ri = 0; ri < nightRestricted.length; ri++) {
            h += nightRestricted[ri] + "<br>";
        }
        h += "</td><td style='" + tdStyle + "'>該当者</td></tr>";
    }

    if (W === "2" && nightRestricted.length === 0) {
        h += "<tr><td style='" + tdStyle + "' colspan='3' style='color:var(--text2);text-align:center'>固有制約なし</td></tr>";
    }

    h += "</table></div>";

    // ==== セクション3: 勤務区分別ハード制約 ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#7c3aed;color:#7c3aed'>勤務区分別ハード制約</div>";

    // day_only
    h += "<div style='margin-bottom:1rem'>";
    h += "<div style='font-weight:bold;margin-bottom:.4rem;color:#6b7280'>日勤のみ (day_only)</div>";
    h += "<table style='" + tblStyle + "'>";
    h += "<tr><td style='" + tdStyle + "'>夜勤系・遅出すべて禁止</td><td style='" + tdStyle + "'>night2, junnya, shinya, ake, late は割当不可</td></tr>";
    h += "</table></div>";

    // 2kohtai
    h += "<div style='margin-bottom:1rem'>";
    h += "<div style='font-weight:bold;margin-bottom:.4rem;color:#8b5cf6'>二交代 (2kohtai)</div>";
    h += "<table style='" + tblStyle + "'>";
    h += "<tr><td style='" + tdStyle + "' width='40%'>使用不可シフト</td><td style='" + tdStyle + "'>junnya, shinya は割当不可</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>夜勤 → 翌日明け（必須）</td><td style='" + tdStyle + "'>night2 の翌日は必ず ake</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>明け → 翌日休み（必須）</td><td style='" + tdStyle + "'>ake の翌日は必ず off/paid/refresh</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>明けは夜勤翌日のみ</td><td style='" + tdStyle + "'>単独 ake 禁止（前月 night2 → 当月1日 ake は許可）</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>夜勤回数上限</td><td style='" + tdStyle + "'>night2 の回数 ≤ 個人上限（akeは自動付与のためカウント外）</td></tr>";
    h += "</table></div>";

    // 3kohtai
    h += "<div style='margin-bottom:1rem'>";
    h += "<div style='font-weight:bold;margin-bottom:.4rem;color:#ec4899'>三交代 (3kohtai)</div>";
    h += "<table style='" + tblStyle + "'>";
    h += "<tr><td style='" + tdStyle + "' width='40%'>使用不可シフト</td><td style='" + tdStyle + "'>night2, ake は割当不可</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>準夜 → 翌日は準夜 or 休み</td><td style='" + tdStyle + "'>正循環ルール（準夜翌日に日勤/遅出/深夜は不可）</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>深夜連続禁止</td><td style='" + tdStyle + "'>shinya の翌日に shinya は不可</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>夜勤3連続禁止</td><td style='" + tdStyle + "'>junnya/shinya の任意の組合せで3日連続は不可</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>準夜 → 深夜 禁止</td><td style='" + tdStyle + "'>インターバル不足（16:30終了 → 00:30開始 = 8h &lt; 11h）</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>遅出 → 深夜 禁止</td><td style='" + tdStyle + "'>インターバル不足（21:00終了 → 00:30開始 = 3.5h &lt; 11h）</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>夜勤回数上限</td><td style='" + tdStyle + "'>(junnya + shinya) ≤ 個人上限</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>月またぎ: 前月末 junnya</td><td style='" + tdStyle + "'>当月1日目は junnya or off のみ</td></tr>";
    h += "<tr><td style='" + tdStyle + "'>月またぎ: 前月末 shinya</td><td style='" + tdStyle + "'>当月1日目は shinya 禁止</td></tr>";
    h += "</table></div>";

    h += "</div>";

    // ==== セクション4: ソフト制約 ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#2563eb;color:#2563eb'>ソフト制約（なるべく守る / ペナルティ最小化）</div>";
    h += "<p style='font-size:.85rem;color:var(--text2);margin-bottom:.8rem'>ソルバーは以下のペナルティの合計を最小化します。重みが大きいほど優先的に守られます。</p>";

    h += "<table style='" + tblStyle + "'>";
    h += "<tr><th style='" + thStyle + "'>階層</th><th style='" + thStyle + "'>制約名</th><th style='" + thStyle + "'>内容</th><th style='" + thStyle + "'>重み</th></tr>";

    // 階層A
    h += "<tr style='background:rgba(239,68,68,0.05)'><td style='" + tdStyle + ";font-weight:bold;color:#dc2626' rowspan='2'>A<br>人員充足</td>";
    h += "<td style='" + tdStyle + "'>人員不足ペナルティ</td>";
    h += "<td style='" + tdStyle + "'>" + (W === "2" ? "日勤・準夜・深夜・遅出" : "日勤・準夜・深夜") + "の不足（試行4のみ緩和）</td>";
    h += "<td style='" + tdStyle + ";font-weight:bold'>10,000/人/日</td></tr>";
    h += "<tr style='background:rgba(239,68,68,0.05)'>";
    h += "<td style='" + tdStyle + "'>勤務間インターバル</td>";
    h += "<td style='" + tdStyle + "'>日勤/早出→深夜禁止（試行4のみ緩和）、準夜/遅出→深夜は常時禁止</td>";
    h += "<td style='" + tdStyle + ";font-weight:bold'>必須</td></tr>";

    // 階層B
    h += "<tr style='background:rgba(245,158,11,0.05)'><td style='" + tdStyle + ";font-weight:bold;color:#f59e0b' rowspan='1'>B<br>希望反映</td>";
    h += "<td style='" + tdStyle + "'>希望違反</td>";
    h += "<td style='" + tdStyle + "'>職員の休み・出勤希望が反映されなかった場合</td>";
    h += "<td style='" + tdStyle + ";font-weight:bold'>1,000/件</td></tr>";

    // 階層C
    var cRows = [
        ["C1", "夜勤pt平準化", "二交代=2pt, 三交代=1ptで換算し、職員間の (max - min) を最小化", "50"],
        ["C2", "5連勤/6連勤回避", "5連勤→150pt, 6連勤→300pt（前月末からの引き継ぎ含む）", "150/300"],
        ["C3", "（廃止）", "連休は減点不要のため廃止", "-"],
        ["C4", "週末勤務平準化", "週末・祝日の勤務回数の (max - min) を最小化", "40"],
        ["C5", "夜勤間隔確保", "二交代: 間隔1日→30, 間隔2日→10<br>三交代: 連続夜勤(準準除く)→20", "10~30"],
        ["C6", "準深バランス", "三交代の準夜・深夜回数差を最小化<br>月全体: |準夜-深夜|×10, 前半/後半: 各×15", "10/15"],
        W === "2" ? ["C7", "遅出均等化", "遅出回数の (max - min) を最小化", "20"] : null,
        ["C8", "散発夜勤回避", "深夜→休→深夜 パターン1回につきペナルティ（三交代）<br>リフレッシュ日数で軽減: 0日→15, 1日→10, 2日→6, 3日+→3", "3~15"],
        ["C9", "深夜翌日休み推奨", "深夜の翌日が休みでない場合にペナルティ<br>リフレッシュ日数で軽減: 0日→20, 1日→12, 2日→7, 3日+→3", "3~20"],
        ["C10", "準夜→休→深夜回避", "体内リズム切替負担ペナルティ<br>リフレッシュ日数で軽減: 0日→50, 1日→35, 2日→25, 3日+→12<br>希望休みの場合は+50", "12~100"],
        ["C11", "希望休み前後夜勤", "希望休み前日の準夜→10pt、翌日の深夜→10pt", "10"],
        ["C12", "日勤帯→深夜回避", "三交代: day/late→翌日shinya（インターバル約7時間）", "25"]
    ];

    var filteredCRows = cRows.filter(function(r) { return r !== null; });
    for (var ci = 0; ci < filteredCRows.length; ci++) {
        var cr = filteredCRows[ci];
        h += "<tr style='background:rgba(37,99,235,0.03)'>";
        if (ci === 0) {
            h += "<td style='" + tdStyle + ";font-weight:bold;color:#2563eb' rowspan='" + filteredCRows.length + "'>C<br>公平性<br>快適性</td>";
        }
        h += "<td style='" + tdStyle + "'><span style='" + tagH + ";background:#2563eb'>" + cr[0] + "</span>" + cr[1] + "</td>";
        h += "<td style='" + tdStyle + "'>" + cr[2] + "</td>";
        h += "<td style='" + tdStyle + ";font-weight:bold;white-space:nowrap'>" + cr[3] + "</td></tr>";
    }

    h += "</table></div>";

    // ==== セクション5: 試行戦略 ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#059669;color:#059669'>試行戦略（4段階）</div>";
    h += "<p style='font-size:.85rem;color:var(--text2);margin-bottom:.8rem'>ソルバーは試行1から順に解を探し、解が見つかった時点で結果を返します。</p>";

    h += "<table style='" + tblStyle + "'>";
    h += "<tr><th style='" + thStyle + "'>試行</th><th style='" + thStyle + "'>希望</th><th style='" + thStyle + "'>人員</th><th style='" + thStyle + "'>その他</th><th style='" + thStyle + "'>説明</th></tr>";

    h += "<tr><td style='" + tdStyle + ";font-weight:bold'>1</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>全制約を完全に守る</td></tr>";
    h += "<tr><td style='" + tdStyle + ";font-weight:bold'>2</td><td style='" + tdStyle + ";color:#f59e0b'>希望休厳守<br>勤務指定ソフト化</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>希望休は厳守、希望勤務をペナルティ化</td></tr>";
    h += "<tr><td style='" + tdStyle + ";font-weight:bold'>3</td><td style='" + tdStyle + ";color:#f59e0b'>希望休厳守<br>勤務指定ソフト化</td><td style='" + tdStyle + ";color:#f59e0b'>平日-1</td><td style='" + tdStyle + "'>厳守</td><td style='" + tdStyle + "'>平日の日勤人数を1名減らして許容</td></tr>";
    h += "<tr><td style='" + tdStyle + ";font-weight:bold;color:#dc2626'>4</td><td style='" + tdStyle + ";color:#f59e0b'>希望休厳守<br>勤務指定ソフト化</td><td style='" + tdStyle + ";color:#dc2626'>不足許容</td><td style='" + tdStyle + ";color:#dc2626'>緩和</td><td style='" + tdStyle + "'>人員不足を許容 + 6連勤禁止等を解除（最終手段）</td></tr>";

    h += "</table></div>";

    // ==== セクション6: 現在の病棟職員構成 ====
    h += "<div style='" + secStyle + "'>";
    h += "<div style='" + headStyle + ";border-color:#6b7280;color:#6b7280'>現在の " + wardName + " 職員構成</div>";

    var counts = { day_only: 0, "2kohtai": 0, "3kohtai": 0, night_only: 0, fixed: 0 };
    var typeCounts = { nurse: 0, junkango: 0, nurseaide: 0 };
    for (var i = 0; i < wardStaff.length; i++) {
        var wt = wardStaff[i].workType || "2kohtai";
        if (counts[wt] !== undefined) counts[wt]++;
        var tp = wardStaff[i].type || "nurse";
        if (typeCounts[tp] !== undefined) typeCounts[tp]++;
    }

    h += "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;margin-bottom:1rem'>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold'>" + wardStaff.length + "</div><div style='font-size:.85rem;color:var(--text2)'>合計</div></div>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold;color:#ec4899'>" + counts["3kohtai"] + "</div><div style='font-size:.85rem;color:var(--text2)'>三交代</div></div>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold;color:#8b5cf6'>" + counts["2kohtai"] + "</div><div style='font-size:.85rem;color:var(--text2)'>二交代</div></div>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold;color:#1e40af'>" + counts.night_only + "</div><div style='font-size:.85rem;color:var(--text2)'>夜勤専従</div></div>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold;color:#6b7280'>" + counts.day_only + "</div><div style='font-size:.85rem;color:var(--text2)'>日勤のみ</div></div>";
    h += "<div style='padding:.6rem;background:var(--bg3);border-radius:6px;text-align:center'><div style='font-size:1.5rem;font-weight:bold;color:#6b7280'>" + counts.fixed + "</div><div style='font-size:.85rem;color:var(--text2)'>固定</div></div>";
    h += "</div>";

    h += "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem'>";
    h += "<div style='padding:.6rem;background:#dbeafe;border-radius:6px;text-align:center'><div style='font-size:1.2rem;font-weight:bold;color:#1e40af'>" + typeCounts.nurse + "</div><div style='font-size:.85rem'>看護師</div></div>";
    h += "<div style='padding:.6rem;background:#fef3c7;border-radius:6px;text-align:center'><div style='font-size:1.2rem;font-weight:bold;color:#92400e'>" + typeCounts.junkango + "</div><div style='font-size:.85rem'>准看護師</div></div>";
    h += "<div style='padding:.6rem;background:#f3e8ff;border-radius:6px;text-align:center'><div style='font-size:1.2rem;font-weight:bold;color:#7c3aed'>" + typeCounts.nurseaide + "</div><div style='font-size:.85rem'>NurseAide</div></div>";
    h += "</div></div>";

    body.innerHTML = h;
}

function render() {
    var t = document.getElementById("shiftTable");
    var days = new Date(Y, M, 0).getDate();
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    var sk = Y + "-" + M + "-" + W;
    var wk = Y + "-" + M; // wishes key
    var wishes = D.wishes[wk] || [];
    // Map wishes to faster lookup: { "staffId-day": "off"|"work" }
    var wishMap = {};
    for (var i = 0; i < wishes.length; i++) {
        var w = wishes[i];
        if (w.days) { // For assign type wishes
            for (var j = 0; j < w.days.length; j++) {
                wishMap[w.staffId + "-" + w.days[j]] = w.shift;
            }
        }
    }

    if (!D.shifts[sk]) D.shifts[sk] = {};

    // 前月末データを取得
    var prevY = Y, prevM = M - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var prevDays = new Date(prevY, prevM, 0).getDate();
    var prevSk = prevY + "-" + prevM + "-" + W;
    var prevShifts = D.shifts[prevSk] || {};
    // ローカルに前月データがない場合、サーバーの確定シフトを使用
    if (Object.keys(prevShifts).length === 0 && window.confirmedPrevShifts) {
        prevShifts = window.confirmedPrevShifts;
    }
    var hasPrevData = Object.keys(prevShifts).length > 0;

    // シフト作成番号の表示
    if (!D.shiftCreationNum) D.shiftCreationNum = {};
    var creationNum = D.shiftCreationNum[sk] || 0;
    var shiftLabel = creationNum > 0 ? "No." + creationNum : "";

    var html = "";
    if (shiftLabel) {
        html += "<caption style='caption-side:top;text-align:left;font-size:.85rem;font-weight:600;color:var(--blue);padding:.3rem 0'>" + Y + "年" + M + "月 勤務表 ［作成#" + creationNum + "］</caption>";
    }
    html += "<thead><tr><th class=\"staff-cell\">職員</th>";
    // 前月末2日間のヘッダー（データがある場合のみ）
    if (hasPrevData) {
        for (var pd = prevDays - 1; pd <= prevDays; pd++) {
            var pdt = new Date(prevY, prevM - 1, pd);
            var pdw = pdt.getDay();
            var pdn = ["日", "月", "火", "水", "木", "金", "土"][pdw];
            var pcls = pdw === 0 ? " sun" : (pdw === 6 ? " sat" : "");
            html += "<th class=\"" + pcls + "\" style=\"background:#e5e7eb;opacity:0.8\">" + pd + "<br>" + pdn + "</th>";
        }
    }
    for (var d = 1; d <= days; d++) {
        var dt = new Date(Y, M - 1, d);
        var dw = dt.getDay();
        var dn = ["日", "月", "火", "水", "木", "金", "土"][dw];
        var hol = isHoliday(Y, M, d);
        var cls = dw === 0 ? " sun" : (dw === 6 ? " sat" : "");
        if (hol && dw !== 0 && dw !== 6) cls = " sun";
        // 土曜日は薄赤背景不要（青文字のみ）
        var holCls = (hol && dw !== 6) ? " holiday" : "";
        html += "<th class=\"" + cls + holCls + "\" data-day=\"" + d + "\">" + d + "<br>" + dn + "</th>";
    }
    html += "<th>日</th><th>夜</th><th>休</th></tr></thead><tbody>";
    // 各日の集計を事前に1パスで計算（日勤/準夜/深夜/遅出/日勤換算）
    var dailyDayCount = [], dailyDayWeighted = [], dailyJunnya = [], dailyShinya = [], dailyLate = [];
    for (var d = 1; d <= days; d++) {
        var cDay = 0, cWeighted = 0, cJun = 0, cShin = 0, cLate = 0;
        for (var si2 = 0; si2 < staff.length; si2++) {
            var sh2 = D.shifts[sk][staff[si2].id + "-" + d] || "";
            if (sh2 === "day" || sh2 === "late") {
                cDay++;
                var dhKey2 = sk + "-" + staff[si2].id + "-" + d;
                var dh2 = D.dayHours && D.dayHours[dhKey2];
                cWeighted += (dh2 && dh2 < 7.5) ? dh2 / 7.5 : 1;
                if (sh2 === "late") cLate++;
            }
            if (sh2 === "night2" || sh2 === "junnya") cJun++;
            if (sh2 === "ake" || sh2 === "shinya") cShin++;
        }
        dailyDayCount[d] = cDay;
        dailyDayWeighted[d] = cWeighted;
        dailyJunnya[d] = cJun;
        dailyShinya[d] = cShin;
        dailyLate[d] = cLate;
    }
    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        var wt = s.workType || "2kohtai";
        var sType = s.type || "nurse";
        var bgColor = getStaffTypeColor(sType);

        // 個人負荷計算で問題日を取得（職員名表示前に計算）
        // 日勤のみ・固定シフト職員は除外
        var nightIntervalIssues = [];
        var hardPatternDays = [];
        var noConsecutiveRest = false;
        if (wt !== "day_only" && wt !== "fixed") {
            var loadResult = calculatePersonalLoad(s.id, D.shifts[sk], days, wt, Y, M, wishMap, getPrevMonthStaffData(s.id, Y, M, W));
            var issueDays = loadResult.issueDays || {};
            nightIntervalIssues = issueDays.nightInterval || [];
            hardPatternDays = issueDays.hardPatterns || [];
            noConsecutiveRest = issueDays.noConsecutiveRest || false;
        }

        var rowStyle = "";
        // 連休なしの場合、職員名に下線マーカー追加
        var nameStyle = "background:" + bgColor;
        var nameMarker = "";
        if (noConsecutiveRest) {
            nameMarker = "<span title=\"連休なし\" style=\"color:#dc2626;font-weight:bold;margin-left:2px\">*</span>";
        }
        html += "<tr style=\"" + rowStyle + "\"><td class=\"staff-cell\" style=\"" + nameStyle + "\">" + escHtml(s.name) + nameMarker + "</td>";
        // 前月末2日間のセル（参照用、編集不可）
        if (hasPrevData) {
            for (var pd = prevDays - 1; pd <= prevDays; pd++) {
                var psh = prevShifts[s.id + "-" + pd] || "";
                var pcls = psh ? " shift-" + psh : "";
                html += "<td class=\"shift-cell" + pcls + "\" style=\"opacity:0.6;cursor:default\">" + (ABBR[psh] || "") + "</td>";
            }
        }
        var dc = 0, nc = 0, oc = 0, wl = 0;

        // 5連勤検出：前月末からの連続勤務をチェック
        // 固定シフト職員（workType === "fixed"）は除外
        var consecutiveSpans = {};  // day -> true if part of 5+ streak
        var skipConsecutiveCheck = (s.workType === "fixed");
        var prevWork = 0;
        // 前月末からの連勤カウント（逸見以外）
        if (!skipConsecutiveCheck) {
            if (hasPrevData) {
                for (var pd = prevDays; pd >= 1; pd--) {
                    var psh = prevShifts[s.id + "-" + pd] || "";
                    if (!psh) continue;
                    if (psh === "off" || psh === "paid" || psh === "ake" || psh === "refresh") break;
                    prevWork++;
                }
            }
            // 当月の連勤検出
            var streakStart = 1;
            var currentStreak = prevWork;
            for (var d = 1; d <= days; d++) {
                var sh = D.shifts[sk][s.id + "-" + d] || "";
                var isWork = sh && sh !== "off" && sh !== "paid" && sh !== "ake" && sh !== "refresh";
                if (isWork) {
                    currentStreak++;
                } else {
                    // 連勤終了 - 5以上なら記録
                    if (currentStreak >= 5) {
                        for (var dd = streakStart; dd < d; dd++) {
                            consecutiveSpans[dd] = true;
                        }
                    }
                    currentStreak = 0;
                    streakStart = d + 1;
                }
            }
            // 月末で終わる連勤もチェック
            if (currentStreak >= 5) {
                for (var dd = streakStart; dd <= days; dd++) {
                    consecutiveSpans[dd] = true;
                }
            }
        }
        for (var d = 1; d <= days; d++) {
            var sh = D.shifts[sk][s.id + "-" + d] || "";

            // Highlight wishes
            var wishVal = wishMap[s.id + "-" + d];
            var style = "";
            if (wishVal) {
                if (wishVal === "off" || wishVal === "paid") style = "background:#bae6fd;border:2px solid #0ea5e9;"; // Blue
                else style = "background:#fed7aa;border:2px solid #f97316;"; // Orange
            }

            // 日勤カウント：日勤のみの人は遅出を除く
            if (wt === "day_only") {
                if (sh === "day") {
                    dc++;
                    wl += dailyDayCount[d] || 0;
                }
            } else {
                if (sh === "day" || sh === "late") {
                    dc++;
                    wl += dailyDayCount[d] || 0;  // 負荷ポイント：その日の日勤人数を加算
                }
            }
            // 夜勤カウント：夜勤入り回数（night2/junnya/shinya）。akeは明け（夜勤の翌日）なのでカウント外
            if (sh === "night2" || sh === "junnya" || sh === "shinya") nc++;
            if (sh === "off" || sh === "paid" || sh === "refresh") oc++;
            var cls = sh ? " shift-" + sh : "";
            var hol = isHoliday(Y, M, d);
            var cellDt = new Date(Y, M - 1, d);
            var cellDw = cellDt.getDay();
            // 5連勤ハイライト
            if (consecutiveSpans[d]) {
                if (style) style += "border-bottom:3px solid #ef4444;";
                else style = "border-bottom:3px solid #ef4444;";
            }
            // 問題日の下線マーキング
            var issueUnderline = "";
            // 夜勤間隔1日（オレンジ波線）
            if (nightIntervalIssues.indexOf(d) >= 0) {
                issueUnderline = "text-decoration:underline wavy #f59e0b;text-underline-offset:2px;";
            }
            // きつい連続パターン（赤破線）- 夜勤間隔より優先
            if (hardPatternDays.indexOf(d) >= 0) {
                issueUnderline = "text-decoration:underline dashed #ef4444;text-underline-offset:2px;";
            }
            if (issueUnderline) {
                if (style) style += issueUnderline;
                else style = issueUnderline;
            }
            var cellHolCls = (hol && cellDw !== 6) ? " holiday" : "";
            var cellContent = ABBR[sh] || "";
            if (sh === "day") {
                var dhKey = sk + "-" + s.id + "-" + d;
                var dh = D.dayHours ? D.dayHours[dhKey] : undefined;
                if (dh !== undefined && dh !== null && dh !== "" && parseFloat(dh) !== 7.5) {
                    cellContent += "<span class=\"day-hours-sub\">" + parseFloat(dh) + "</span>";
                }
            }
            // 比較差分ハイライト
            var diffCls = "";
            if (compareDraftShifts) {
                var compVal = compareDraftShifts[s.id + "-" + d] || "";
                if (compVal !== sh) diffCls = " cell-diff";
            }
            html += "<td class=\"shift-cell" + cls + cellHolCls + diffCls + "\" data-staff=\"" + s.id + "\" data-day=\"" + d + "\" style=\"" + style + "\">" + cellContent + "</td>";
        }
        html += "<td>" + dc + "</td><td>" + nc + "</td><td>" + oc + "</td></tr>";
    }
    // 集計行（事前計算済みキャッシュを使用）
    html += "<tr><td class=\"staff-cell\"><b>日勤計</b></td>";
    if (hasPrevData) html += "<td></td><td></td>";
    var rdw = parseInt(document.getElementById("reqDayWeekday").value) || 7;
    var rdh = parseInt(document.getElementById("reqDayHoliday").value) || 5;
    for (var d = 1; d <= days; d++) {
        var c = dailyDayWeighted[d];
        var ddt = new Date(Y, M - 1, d);
        var ddw = ddt.getDay();
        var dreq = rdw;
        if (ddw === 0 || HOLIDAYS[Y + "-" + M + "-" + d]) { dreq = rdh; }
        else if (W === "2") {
            if (ddw === 1 || ddw === 5) { /* 月金: 基準 */ }
            else if (ddw === 4) dreq += 1;
            else if (ddw === 2 || ddw === 3 || ddw === 6) dreq -= 1;
        }
        else if (W === "1") {
            if (ddw === 1 || ddw === 4) { /* 月木: 基準 */ }
            else if (ddw === 3 || ddw === 5) { dreq -= 1; }
            else if (ddw === 2) { dreq -= 2; }
            else if (ddw === 6) { dreq -= 2; }
        }
        else { if (ddw === 3) dreq -= 1; }
        var cDisp = (c % 1 === 0) ? c : c.toFixed(1);
        html += "<td class=\"" + (c >= dreq ? "check-ok" : "check-ng") + "\" data-day=\"" + d + "\">" + cDisp + "</td>";
    }
    html += "<td></td><td></td><td></td></tr>";
    // 準夜帯（事前計算済み）
    html += "<tr><td class=\"staff-cell\"><b>準夜帯</b></td>";
    if (hasPrevData) html += "<td></td><td></td>";
    var reqJun = parseInt(document.getElementById("reqJunnya").value) || 2;
    for (var d = 1; d <= days; d++) {
        var c = dailyJunnya[d];
        html += "<td class=\"" + (c === reqJun ? "check-ok" : "check-ng") + "\" data-day=\"" + d + "\">" + c + "</td>";
    }
    html += "<td></td><td></td><td></td></tr>";
    // 深夜帯（事前計算済み）
    html += "<tr><td class=\"staff-cell\"><b>深夜帯</b></td>";
    if (hasPrevData) html += "<td></td><td></td>";
    var reqShin = parseInt(document.getElementById("reqShinya").value) || 2;
    for (var d = 1; d <= days; d++) {
        var c = dailyShinya[d];
        html += "<td class=\"" + (c === reqShin ? "check-ok" : "check-ng") + "\" data-day=\"" + d + "\">" + c + "</td>";
    }
    html += "<td></td><td></td><td></td></tr>";
    // 遅出（二病棟のみ、事前計算済み）
    if (W === "2") {
        html += "<tr><td class=\"staff-cell\"><b>遅出</b></td>";
        if (hasPrevData) html += "<td></td><td></td>";
        var reqLate = parseInt(document.getElementById("reqLate").value) || 1;
        for (var d = 1; d <= days; d++) {
            var c = dailyLate[d];
            html += "<td class=\"" + (c >= reqLate ? "check-ok" : "check-ng") + "\" data-day=\"" + d + "\">" + c + "</td>";
        }
        html += "<td></td><td></td><td></td></tr>";
    }
    html += "</tbody>";
    t.innerHTML = html;

    // 比較中バナー表示
    var bannerEl = document.getElementById("compareBanner");
    if (!bannerEl) {
        bannerEl = document.createElement("div");
        bannerEl.id = "compareBanner";
        t.parentNode.insertBefore(bannerEl, t);
    }
    if (compareDraftName) {
        bannerEl.className = "compare-banner";
        bannerEl.innerHTML = "&#x1F4CA; <b>" + escHtml(compareDraftName) + "</b>と比較中 <button class='btn btn-secondary' onclick='clearCompareDraft()'>比較解除</button>";
    } else {
        bannerEl.className = "";
        bannerEl.innerHTML = "";
    }

    var cells = document.querySelectorAll(".shift-cell[data-staff]");
    for (var i = 0; i < cells.length; i++) {
        cells[i].addEventListener("click", function () {
            openShift(this.getAttribute("data-staff"), parseInt(this.getAttribute("data-day")));
        });
    }
    // クロスヘア: 行・列ハイライト
    for (var i = 0; i < cells.length; i++) {
        cells[i].addEventListener("mouseenter", function () {
            var day = this.getAttribute("data-day");
            var row = this.parentElement;
            // 行ハイライト
            row.classList.add("row-highlight");
            // 列ハイライト（同じ data-day のセルすべて）
            var colCells = t.querySelectorAll("td[data-day=\"" + day + "\"]");
            for (var j = 0; j < colCells.length; j++) colCells[j].classList.add("col-highlight");
            // ヘッダー列もハイライト
            var ths = t.querySelectorAll("th[data-day=\"" + day + "\"]");
            for (var j = 0; j < ths.length; j++) ths[j].classList.add("col-highlight");
            // 自身は強調
            this.classList.add("cell-highlight");
        });
        cells[i].addEventListener("mouseleave", function () {
            var day = this.getAttribute("data-day");
            var row = this.parentElement;
            row.classList.remove("row-highlight");
            var colCells = t.querySelectorAll("td[data-day=\"" + day + "\"]");
            for (var j = 0; j < colCells.length; j++) colCells[j].classList.remove("col-highlight");
            var ths = t.querySelectorAll("th[data-day=\"" + day + "\"]");
            for (var j = 0; j < ths.length; j++) ths[j].classList.remove("col-highlight");
            this.classList.remove("cell-highlight");
        });
    }
    // 希望入力画面のプルダウンを初期化
    var ww = document.getElementById("wishWard");
    if (ww && ww.options.length === 0) {
        for (var wi = 0; wi < WARDS.length; wi++) {
            var opt = document.createElement("option");
            opt.value = WARDS[wi].id;
            opt.textContent = WARDS[wi].id;
            ww.appendChild(opt);
        }
    }
    if (ww) ww.value = W;
    var wy = document.getElementById("wishYear");
    if (wy) wy.value = Y;
    var wm = document.getElementById("wishMonth");
    if (wm) wm.value = M;
    renderWishUI();
    renderWishes();
    renderVersions();
    checkFixedStaffComplete();

    // シフトがある場合のみ制約チェック・公平性評価を表示
    var sk = Y + "-" + M + "-" + W;
    var shifts = D.shifts[sk] || {};
    if (Object.keys(shifts).length > 0) {
        checkConstraints();
    } else {
        // シフトがない場合はパネルを非表示
        var panel = document.getElementById("fairnessMetrics");
        if (panel) panel.style.display = "none";
        var personalPanel = document.getElementById("personalLoadPanel");
        if (personalPanel) personalPanel.style.display = "none";
        var log = document.getElementById("checkLog");
        if (log) log.style.display = "none";
    }
}

function checkFixedStaffComplete() {
    // 固定シフトは希望データから読み取るためUIチェック不要
    var btn = document.getElementById("btnSolve");
    if (!btn) return;
    btn.disabled = false;
    btn.title = "";
    btn.textContent = "生成開始";
}

function openShift(id, d) {
    sel = { id: id, d: d };
    sel._actualMode = ACTUAL_MODE; // 実績モードかどうかを記録
    var s = null;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === id) { s = D.staff[i]; break; }
    }
    document.getElementById("shiftModalTitle").textContent = s.name + " - " + M + "/" + d + (ACTUAL_MODE ? " [実績]" : "");
    // 日勤時間数パネルを初期状態で非表示
    var dhWrap = document.getElementById("dayHoursWrap");
    if (dhWrap) {
        var sk = Y + "-" + M + "-" + (s ? s.ward : W);
        var currentShift = D.shifts[sk] ? (D.shifts[sk][id + "-" + d] || "") : "";
        if (currentShift === "day") {
            // 既に日勤の場合は時間数パネルを表示
            dhWrap.style.display = "block";
            var dhKey = sk + "-" + id + "-" + d;
            var existing = D.dayHours && D.dayHours[dhKey];
            document.getElementById("dayHoursInput").value = (existing !== undefined && existing !== null && existing !== "") ? existing : 7.5;
        } else {
            dhWrap.style.display = "none";
        }
    }
    document.getElementById("shiftModal").classList.add("active");
}

function setShift(sh, dayHours) {
    if (!sel) return;

    // 実績モードの場合は変更理由モーダルを表示
    if (sel._actualMode) {
        document.getElementById("shiftModal").classList.remove("active");
        openActualReasonModal(sel.id, sel.d, sh);
        return;
    }

    var s = null;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === sel.id) { s = D.staff[i]; break; }
    }
    var sk = Y + "-" + M + "-" + s.ward;
    if (!D.shifts[sk]) D.shifts[sk] = {};
    if (!D.dayHours) D.dayHours = {};
    var days = new Date(Y, M, 0).getDate();
    var dhKey = sk + "-" + sel.id + "-" + sel.d;
    if (sh) {
        D.shifts[sk][sel.id + "-" + sel.d] = sh;
        // 日勤の場合、時間数を保存
        if (sh === "day" && dayHours !== undefined) {
            D.dayHours[dhKey] = parseFloat(dayHours);
        } else if (sh !== "day") {
            // 日勤以外に変更された場合、時間数データを削除
            delete D.dayHours[dhKey];
        }
        // 夜勤の場合、翌日に明け、翌々日に休みを自動設定
        if (sh === "night2") {
            if (sel.d < days) {
                D.shifts[sk][sel.id + "-" + (sel.d + 1)] = "ake";
            }
            if (sel.d < days - 1) {
                D.shifts[sk][sel.id + "-" + (sel.d + 2)] = "off";
            }
        }
    } else {
        delete D.shifts[sk][sel.id + "-" + sel.d];
        delete D.dayHours[dhKey];
    }
    save();
    render();
    document.getElementById("shiftModal").classList.remove("active");
}

function solve(seed) {
    var log = document.getElementById("log");
    var btn = document.getElementById("btnSolve");
    var progress = document.getElementById("solveProgress");
    var solveLog = document.getElementById("solveLog");
    var solveStatus = document.getElementById("solveStatus");
    var solveElapsed = document.getElementById("solveElapsed");

    log.innerHTML = "";
    log.style.display = "none";
    solveLog.innerHTML = "";
    progress.style.display = "block";
    btn.disabled = true;
    btn.textContent = "生成中...";

    // チャートリセット
    solveChartData = [];
    solveAttemptNum = 0;
    var chart = document.getElementById("solveChart");
    if (chart) {
        chart.style.display = "none";
        var ctx = chart.getContext("2d");
        ctx.clearRect(0, 0, chart.width, chart.height);
    }

    // 再試行カウンタリセット
    _solveRetryCount = 0;

    // 前月の確定シフトをサーバーから取得
    loadConfirmedPrevShifts(function() {
        doSolve(seed, log, btn, progress, solveLog, solveStatus, solveElapsed);
    });
}

function loadConfirmedPrevShifts(callback) {
    fetch("/api/shift/prev-month?ward=" + W + "&year=" + Y + "&month=" + M)
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.status === "success" && res.hasData) {
                window.confirmedPrevShifts = res.shifts;
            } else {
                window.confirmedPrevShifts = null;
            }
            callback();
        })
        .catch(function(e) {
            window.confirmedPrevShifts = null;
            callback();
        });
}

// ========== 最適化過程グラフ描画（改善量を上向きに表示） ==========
function drawSolveChart() {
    var canvas = document.getElementById("solveChart");
    if (!canvas || solveChartData.length < 1) return;

    canvas.style.display = "block";
    var ctx = canvas.getContext("2d");
    var W = canvas.width;
    var H = canvas.height;
    var pad = { top: 14, right: 12, bottom: 20, left: 55 };
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;

    ctx.clearRect(0, 0, W, H);

    var data = solveChartData;
    var initialObj = data[0].obj;
    var maxTime = data[0].time;

    // 改善量データに変換（初期値からの減少量 = 上向きに増加）
    var improvements = [];
    for (var i = 0; i < data.length; i++) {
        improvements.push({ time: data[i].time, val: initialObj - data[i].obj });
        if (data[i].time > maxTime) maxTime = data[i].time;
    }

    var maxImprove = 0;
    for (var i = 0; i < improvements.length; i++) {
        if (improvements[i].val > maxImprove) maxImprove = improvements[i].val;
    }
    if (maxImprove === 0) maxImprove = 1;
    if (maxTime === 0) maxTime = 1;

    var yMax = maxImprove * 1.15;

    function toX(t) { return pad.left + (t / maxTime) * plotW; }
    function toY(v) { return pad.top + (1 - v / yMax) * plotH; }

    // グリッド線
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 0.5;
    for (var g = 0; g <= 4; g++) {
        var gy = pad.top + (g / 4) * plotH;
        ctx.beginPath();
        ctx.moveTo(pad.left, gy);
        ctx.lineTo(pad.left + plotW, gy);
        ctx.stroke();
    }

    // ベースライン（改善量0）
    ctx.strokeStyle = "rgba(255,255,255,0.2)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, toY(0));
    ctx.lineTo(pad.left + plotW, toY(0));
    ctx.stroke();

    // 改善量の塗りつぶし（グラデーション）
    var grad = ctx.createLinearGradient(0, toY(maxImprove), 0, toY(0));
    grad.addColorStop(0, "rgba(74,222,128,0.3)");
    grad.addColorStop(1, "rgba(74,222,128,0.02)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(toX(improvements[0].time), toY(0));
    ctx.lineTo(toX(improvements[0].time), toY(improvements[0].val));
    for (var i = 1; i < improvements.length; i++) {
        ctx.lineTo(toX(improvements[i].time), toY(improvements[i - 1].val));
        ctx.lineTo(toX(improvements[i].time), toY(improvements[i].val));
    }
    // 現在時刻まで延長
    var extendX = toX(improvements[improvements.length - 1].time);
    if (solveStartTime) {
        var elapsed = (Date.now() - solveStartTime) / 1000;
        if (elapsed > maxTime) {
            extendX = toX(elapsed > maxTime * 1.3 ? maxTime : elapsed);
        }
    }
    ctx.lineTo(extendX, toY(improvements[improvements.length - 1].val));
    ctx.lineTo(extendX, toY(0));
    ctx.closePath();
    ctx.fill();

    // ステップライン（改善量の階段状上昇）
    ctx.strokeStyle = "#4ade80";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(toX(improvements[0].time), toY(improvements[0].val));
    for (var i = 1; i < improvements.length; i++) {
        ctx.lineTo(toX(improvements[i].time), toY(improvements[i - 1].val));
        ctx.lineTo(toX(improvements[i].time), toY(improvements[i].val));
    }
    ctx.lineTo(extendX, toY(improvements[improvements.length - 1].val));
    ctx.stroke();

    // ポイント描画
    ctx.fillStyle = "#4ade80";
    for (var i = 0; i < improvements.length; i++) {
        ctx.beginPath();
        ctx.arc(toX(improvements[i].time), toY(improvements[i].val), 3, 0, Math.PI * 2);
        ctx.fill();
    }

    // Y軸ラベル（改善量）
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("+" + Math.round(maxImprove), pad.left - 4, pad.top + 9);
    ctx.fillText("0", pad.left - 4, toY(0) + 3);

    // X軸ラベル（時間）
    ctx.textAlign = "center";
    ctx.fillText("0s", pad.left, H - 2);
    ctx.fillText(maxTime.toFixed(0) + "s", pad.left + plotW, H - 2);

    // 情報ラベル（左上）
    ctx.fillStyle = "#4ade80";
    ctx.textAlign = "left";
    ctx.font = "bold 10px sans-serif";
    var bestObj = data[data.length - 1].obj;
    var totalImprove = initialObj - bestObj;
    ctx.fillText("改善: +" + totalImprove + " (残ペナルティ " + bestObj + ")", pad.left + 4, pad.top + 10);

    // 解の数（右上）
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.textAlign = "right";
    ctx.font = "9px sans-serif";
    ctx.fillText(data.length + "解", pad.left + plotW - 2, pad.top + 10);
}

var _solveRetryCount = 0;
var _solveMaxRetry = 3;

function doSolve(seed, log, btn, progress, solveLog, solveStatus, solveElapsed) {

    // 進捗ログ追加関数
    function addProgressLog(msg, style) {
        var line = document.createElement("div");
        line.textContent = "▸ " + msg;
        if (style === "dim") {
            line.style.color = "var(--text3, #888)";
            line.style.fontSize = "0.85em";
        }
        solveLog.appendChild(line);
        solveLog.scrollTop = solveLog.scrollHeight;
    }

    // 経過時間表示開始
    solveStartTime = Date.now();
    solveTimer = setInterval(function() {
        var elapsed = ((Date.now() - solveStartTime) / 1000).toFixed(1);
        solveElapsed.textContent = "経過時間: " + elapsed + "秒";
    }, 100);

    if (_solveRetryCount > 0) {
        addProgressLog("⟳ 自動再試行 " + _solveRetryCount + "/" + _solveMaxRetry + " (seed=" + seed + ")");
    }
    addProgressLog("データ準備中...");
    // 病棟のすべての職員
    var allStaff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) allStaff.push(D.staff[i]);
    }
    // 固定シフト職員を除外（ソルバー対象外）
    var staff = [];
    var fixedStaff = [];
    for (var i = 0; i < allStaff.length; i++) {
        if (allStaff[i].workType === "fixed") {
            fixedStaff.push(allStaff[i]);
        } else {
            staff.push(allStaff[i]);
        }
    }
    if (fixedStaff.length > 0) {
        addProgressLog("固定シフト職員: " + fixedStaff.length + "名 (対象外)");
    }
    addProgressLog("対象職員: " + staff.length + "名");
    var wk = Y + "-" + M;

    // 前月末データを取得
    var prevMonthData = {};
    var prevY = Y, prevM = M - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var prevDays = new Date(prevY, prevM, 0).getDate();
    var prevSk = prevY + "-" + prevM + "-" + W;
    var prevShifts = D.shifts[prevSk] || {};

    // ローカルに前月データがない場合、サーバーの確定シフトを使用
    if (Object.keys(prevShifts).length === 0 && window.confirmedPrevShifts) {
        prevShifts = window.confirmedPrevShifts;
        addProgressLog("前月データ読込(確定): " + Object.keys(prevShifts).length + "件");
    } else {
        addProgressLog("前月データ読込: " + Object.keys(prevShifts).length + "件");
    }
    for (var i = 0; i < staff.length; i++) {
        var sid = staff[i].id;
        var lastDay = prevShifts[sid + "-" + prevDays] || "";
        var secondLastDay = prevShifts[sid + "-" + (prevDays - 1)] || "";

        // 連続勤務数 (前月末基準) - 空欄は連続を途切れさせる
        var cWork = 0;
        for (var k = 0; k < 10; k++) {
            var d = prevDays - k;
            if (d < 1) break;
            var sh = prevShifts[sid + "-" + d] || "";
            if (!sh) break;  // 空欄は連続終了
            if (sh === "off" || sh === "paid" || sh === "ake" || sh === "refresh") break;  // 休みで終了
            cWork++;  // 勤務をカウント
        }

        // 連続準夜数 (前月末基準) - 空欄は連続を途切れさせる
        var cJun = 0;
        for (var k = 0; k < 10; k++) {
            var d = prevDays - k;
            if (d < 1) break;
            var sh = prevShifts[sid + "-" + d] || "";
            if (!sh) break;  // 空欄は連続終了
            if (sh === "junnya") cJun++;
            else break;
        }

        // 連続休み数 (前月末基準) - 空欄は連続を途切れさせる
        var cOff = 0;
        for (var k = 0; k < 10; k++) {
            var d = prevDays - k;
            if (d < 1) break;
            var sh = prevShifts[sid + "-" + d] || "";
            if (!sh) break;  // 空欄は連続終了
            if (sh === "off" || sh === "paid" || sh === "refresh") cOff++;
            else break;
        }

        if (lastDay || secondLastDay || cWork > 0 || cJun > 0 || cOff > 0) {
            prevMonthData[sid] = {
                lastDay: lastDay,
                secondLastDay: secondLastDay,
                consecutiveWork: cWork,
                consecutiveJunnya: cJun,
                consecutiveOff: cOff
            };
        }
    }
    if (Object.keys(prevMonthData).length > 0) {
        addProgressLog("引継ぎ情報: " + Object.keys(prevMonthData).length + "名分");
    }

    // 固定シフト職員のシフトデータを収集
    var sk = Y + "-" + M + "-" + W;
    var fixedShifts = {};
    for (var fi = 0; fi < fixedStaff.length; fi++) {
        var fs = fixedStaff[fi];
        fixedShifts[fs.id] = {};
        for (var fd = 1; fd <= new Date(Y, M, 0).getDate(); fd++) {
            var fsh = D.shifts[sk] ? D.shifts[sk][fs.id + "-" + fd] : null;
            if (fsh) {
                fixedShifts[fs.id][fd] = fsh;
            }
        }
    }

    var payload = {
        year: Y,
        month: M,
        staff: staff.concat(fixedStaff).map(function (s) {
            return {
                id: s.id,
                name: s.name,
                type: s.type || "nurse",
                workType: s.workType || "2kohtai",
                maxNight: s.maxNight !== undefined ? s.maxNight : 5,
                minNight: s.minNight !== undefined ? s.minNight : undefined,
                nightRestriction: s.nightRestriction || null,
                fixedPattern: s.fixedPattern || null
            };
        }),
        config: {
            ward: W,
            reqDayWeekday: parseInt(document.getElementById("reqDayWeekday").value) || 7,
            reqDayHoliday: parseInt(document.getElementById("reqDayHoliday").value) || 5,
            reqJunnya: parseInt(document.getElementById("reqJunnya").value) || 2,
            reqShinya: parseInt(document.getElementById("reqShinya").value) || 2,
            reqLate: (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("reqLate").value) || 1),
            maxLate: (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("maxLate").value) || 4),
            monthlyOff: getMonthlyOff(M),
            seed: seed
        },
        wishes: D.wishes[wk] || [],
        prevMonthData: prevMonthData,
        fixedShifts: fixedShifts
    };
    addProgressLog("ソルバーに送信中... (公休=" + payload.config.monthlyOff + "日, 月=" + M + ")");
    solveStatus.textContent = "最適化計算中...";

    // SSEストリーミングでソルバー進捗を取得
    fetch("/solve-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function processStream() {
            return reader.read().then(function(result) {
                if (result.done) return;

                buffer += decoder.decode(result.value, { stream: true });
                var lines = buffer.split("\n");
                buffer = lines.pop(); // 未完了の行を保持

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.startsWith("data: ")) {
                        try {
                            var data = JSON.parse(line.substring(6));
                            handleSolverEvent(data);
                        } catch (e) {}
                    }
                }
                return processStream();
            });
        }

        function handleSolverEvent(data) {
            if (data.type === "info") {
                addProgressLog(data.msg);
            } else if (data.type === "attempt") {
                solveStatus.textContent = data.msg;
                addProgressLog(data.msg);
                // 新しい試行ではチャートデータをリセット
                solveChartData = [];
                solveAttemptNum = data.num || 0;
            } else if (data.type === "progress") {
                // ソルバーが改善解を発見（グラフのみ更新、ログ不要）
                // debugキー付きはデバッグメッセージなのでグラフに含めない
                if (!data.debug && data.obj !== undefined && data.obj > 0) {
                    solveChartData.push({ time: data.time, obj: data.obj });
                    drawSolveChart();
                }
            } else if (data.type === "log") {
                addProgressLog(data.msg, "dim");
            } else if (data.type === "success") {
                addProgressLog("✓ " + data.msg);
            } else if (data.type === "fail") {
                addProgressLog("✗ " + data.msg);
            } else if (data.type === "error") {
                addProgressLog("❌ " + data.msg);
            } else if (data.type === "result") {
                finishSolve(data.data);
            }
        }

        return processStream();
    })
    .catch(function(e) {
        if (solveTimer) { clearInterval(solveTimer); solveTimer = null; }
        var finalTime = ((Date.now() - solveStartTime) / 1000).toFixed(1);
        progress.style.display = "none";
        log.style.display = "flex";
        addLog("エラー: " + e.message + " (" + finalTime + "秒)", "error");
        btn.disabled = false;
        btn.textContent = "生成開始";
    });

    function finishSolve(r) {
        if (solveTimer) { clearInterval(solveTimer); solveTimer = null; }
        var finalTime = ((Date.now() - solveStartTime) / 1000).toFixed(1);

        if (r.status && r.status.toLowerCase() in { optimal: 1, feasible: 1 }) {
            progress.style.display = "none";
            log.style.display = "flex";

            addLog("完了: " + r.status + " (" + finalTime + "秒)", "success");
            if (r.attempt) {
                if (r.attempt === 4) {
                    addLog("⚠ 試行4: 勤務間インターバル違反の可能性あり", "error");
                } else if (r.attempt > 1) {
                    addLog("試行" + r.attempt + "で解決", "info");
                }
            }

            if (r.violations && r.violations.length > 0) {
                addLog("⚠ 希望逸脱 " + r.violations.length + "件", "error");
            } else {
                addLog("希望はすべて反映", "success");
            }

            // 公休デバッグ情報（コンソールのみ、UIには非表示）
            if (r.offDebug && r.offDebug.length > 0) {
            }

            var sk = Y + "-" + M + "-" + W;
            // シフト作成番号をインクリメント
            if (!D.shiftCreationNum) D.shiftCreationNum = {};
            if (!D.shiftCreationNum[sk]) D.shiftCreationNum[sk] = 0;
            D.shiftCreationNum[sk]++;

            var existingShifts = D.shifts[sk] || {};
            var fixedStaffIds = {};
            for (var fi = 0; fi < fixedStaff.length; fi++) {
                fixedStaffIds[fixedStaff[fi].id] = true;
            }
            D.shifts[sk] = {};
            for (var k in existingShifts) {
                var parts = k.split("-");
                var sid = parts.slice(0, -1).join("-");
                if (parts.length >= 2 && fixedStaffIds[sid]) {
                    D.shifts[sk][k] = existingShifts[k];
                }
            }
            for (var k in r.shifts) D.shifts[sk][k] = r.shifts[k];
            save();
            render();

            // 自動保存（サーバーに保存）
            autoSaveDraft(D.shifts[sk]);

            var metrics = calculateVersionMetrics(D.shifts[sk]);
            var scoreType = metrics.totalScore >= 90 ? "success" : metrics.totalScore >= 70 ? "info" : "error";
            addLog("評価: " + metrics.totalScore + "点 " + metrics.stars, scoreType);
            if (metrics.errors > 0 || metrics.warnings > 0) {
                addLog("❌" + metrics.errors + " ⚠" + metrics.warnings, metrics.errors > 0 ? "error" : "info");
            }
            renderVersions();

            // ハード制約違反チェック → 自動再試行
            // render() 内の checkConstraints() が window._lastCheckResult に結果を保存済み
            var checkResult = window._lastCheckResult;
            if (checkResult && checkResult.errors.length > 0 && _solveRetryCount < _solveMaxRetry) {
                _solveRetryCount++;
                var newSeed = Math.floor(Math.random() * 10000) + 1;
                addLog("⟳ ハード制約違反あり → 自動再試行 " + _solveRetryCount + "/" + _solveMaxRetry + " (seed=" + newSeed + ")", "error");

                // UIをリセットして再実行
                log.innerHTML = "";
                log.style.display = "none";
                solveLog.innerHTML = "";
                progress.style.display = "block";
                btn.disabled = true;
                btn.textContent = "再試行中...(" + _solveRetryCount + "/" + _solveMaxRetry + ")";
                solveChartData = [];
                solveAttemptNum = 0;

                // 少し待ってから再試行（UIの更新を反映）
                setTimeout(function() {
                    doSolve(newSeed, log, btn, progress, solveLog, solveStatus, solveElapsed);
                }, 500);
                return;
            }
        } else {
            progress.style.display = "none";
            var msg = r.message || "解なし";
            if (msg.indexOf("\n") >= 0) {
                // 複数行メッセージ（診断付き）→ ブロック表示
                log.style.display = "block";
                var div = document.createElement("div");
                div.className = "log-error";
                div.style.whiteSpace = "pre-wrap";
                div.style.lineHeight = "1.6";
                div.textContent = "失敗: " + msg + " (" + finalTime + "秒)";
                log.appendChild(div);
            } else {
                log.style.display = "flex";
                addLog("失敗: " + msg + " (" + finalTime + "秒)", "error");
            }
        }
        btn.disabled = false;
        btn.textContent = "生成開始";
    }
}

function addLog(m, t) {
    var log = document.getElementById("log");
    if (log.children.length > 0) {
        var sep = document.createElement("span");
        sep.textContent = " | ";
        sep.style.color = "#6b7280";
        log.appendChild(sep);
    }
    var e = document.createElement("span");
    e.className = "log-" + t;
    e.textContent = m;
    log.appendChild(e);
}

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
                shifts: shifts,
                dayHours: hours
            };
        }),
        wishMap: wishMap // Add wishMap to payload
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

function parseWishNatural() {
    var text = document.getElementById("wishNatural").value.trim();
    if (!text) {
        document.getElementById("parseResult").textContent = "入力がありません";
        return;
    }

    var targetWard = document.getElementById("wishWard").value;
    var targetYear = parseInt(document.getElementById("wishYear").value);
    var targetMonth = parseInt(document.getElementById("wishMonth").value);

    // 対象病棟の職員リスト
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === targetWard) staff.push(D.staff[i]);
    }

    // シフトマッピング
    var shiftMap = {
        "休": "off", "休み": "off", "オフ": "off", "公": "off",
        "出": "day", "出勤": "day", "日": "day", "日勤": "day",
        "リ": "refresh", "リフ": "refresh", "リフレ": "refresh",
        "有": "paid", "有休": "paid", "有給": "paid",
        "夜": "night2", "夜勤": "night2",
        "準": "junnya", "準夜": "junnya",
        "深": "shinya", "深夜": "shinya",

        "遅": "late", "遅出": "late"
    };

    var lines = text.split(/[\n,，、]+/);
    var wishes = [];
    var parsed = 0;
    var errors = [];

    for (var li = 0; li < lines.length; li++) {
        var line = lines[li].trim();
        if (!line) continue;

        // 全休パターン: 名前+全+区分 (例: 内田全休, 内田全有給)
        var allDayMatch = line.match(/^(.+?)全(.+)$/);
        if (allDayMatch) {
            var adName = allDayMatch[1].trim();
            var adShiftKey = allDayMatch[2].trim();
            var adShift = shiftMap[adShiftKey];
            if (!adShift) { errors.push(adShiftKey + " (区分不明)"); continue; }
            var adStaff = null;
            for (var si = 0; si < staff.length; si++) {
                if (staff[si].name.indexOf(adName) >= 0 || adName.indexOf(staff[si].name) >= 0) {
                    adStaff = staff[si]; break;
                }
            }
            if (!adStaff) { errors.push(adName + " (職員不明)"); continue; }
            var daysInMonth = new Date(targetYear, targetMonth, 0).getDate();
            var allDaysArr = [];
            for (var ad = 1; ad <= daysInMonth; ad++) allDaysArr.push(ad);
            wishes.push({ staffId: adStaff.id, type: "assign", days: allDaysArr, shift: adShift });
            parsed += daysInMonth;
            continue;
        }

        // パターン: 名前 + 日付 + 区分 (例: 内田5休, 西川14休み)
        var match = line.match(/^(.+?)(\d+)(.+)$/);
        if (!match) {
            errors.push(line + " (形式不明)");
            continue;
        }

        var name = match[1].trim();
        var day = parseInt(match[2]);
        var shiftKey = match[3].trim();

        // 職員検索
        var foundStaff = null;
        for (var si = 0; si < staff.length; si++) {
            if (staff[si].name.indexOf(name) >= 0 || name.indexOf(staff[si].name) >= 0) {
                foundStaff = staff[si];
                break;
            }
        }

        if (!foundStaff) {
            errors.push(name + " (職員不明)");
            continue;
        }

        // シフト変換
        var shift = shiftMap[shiftKey];
        if (!shift) {
            errors.push(shiftKey + " (区分不明)");
            continue;
        }

        wishes.push({
            staffId: foundStaff.id,
            type: "assign",
            days: [day],
            shift: shift
        });
        parsed++;
    }

    // JSON出力
    if (wishes.length > 0) {
        var result = { year: targetYear, month: targetMonth, wishes: wishes };
        document.getElementById("wishJson").value = JSON.stringify(result, null, 2);
        document.getElementById("parseResult").textContent = "✅ " + parsed + "件変換" + (errors.length > 0 ? " / ⚠️ " + errors.length + "件エラー" : "");
    } else {
        document.getElementById("parseResult").textContent = "❌ 変換できませんでした";
    }
}

function showWishSample() {
    var wy = parseInt(document.getElementById("wishYear").value);
    var wm = parseInt(document.getElementById("wishMonth").value);
    var sample = { year: wy, month: wm, wishes: [{ staffId: "10060766", type: "assign", days: [5], shift: "off" }] };
    document.getElementById("wishJson").value = JSON.stringify(sample, null, 2);
}

function importWish() {
    try {
        var targetWard = document.getElementById("wishWard").value;
        var targetYear = parseInt(document.getElementById("wishYear").value);
        var targetMonth = parseInt(document.getElementById("wishMonth").value);

        var d = JSON.parse(document.getElementById("wishJson").value);
        var wk = targetYear + "-" + targetMonth;
        D.wishes[wk] = d.wishes || [];
        save();
        alert(targetWard + "病棟 " + targetYear + "年" + targetMonth + "月の希望を保存しました");
    } catch (e) {
        alert("エラー: " + e.message);
    }
}

function importWishNatural() {
    var text = document.getElementById("wishNatural").value.trim();
    if (!text) {
        document.getElementById("parseResult").textContent = "入力がありません";
        return;
    }

    // 全角数字を半角に変換
    text = text.replace(/[０-９]/g, function(s) {
        return String.fromCharCode(s.charCodeAt(0) - 0xFEE0);
    });

    var targetWard = W;
    var targetYear = Y;
    var targetMonth = M;

    // 対象病棟の職員リスト
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === targetWard) staff.push(D.staff[i]);
    }

    // シフトマッピング
    var shiftMap = {
        "休": "off", "休み": "off", "オフ": "off", "公": "off",
        "出": "day", "出勤": "day", "日": "day", "日勤": "day",
        "リ": "refresh", "リフ": "refresh", "リフレ": "refresh",
        "有": "paid", "有休": "paid", "有給": "paid",
        "夜": "night2", "夜勤": "night2",
        "準": "junnya", "準夜": "junnya",
        "深": "shinya", "深夜": "shinya",

        "遅": "late", "遅出": "late"
    };

    // 曜日マッピング
    var dayOfWeekMap = { "日": 0, "月": 1, "火": 2, "水": 3, "木": 4, "金": 5, "土": 6 };

    // 該当月の特定曜日の日付リストを取得
    function getDaysForWeekday(weekdayNum) {
        var days = [];
        var daysInMonth = new Date(targetYear, targetMonth, 0).getDate();
        for (var d = 1; d <= daysInMonth; d++) {
            var dt = new Date(targetYear, targetMonth - 1, d);
            if (dt.getDay() === weekdayNum) {
                days.push(d);
            }
        }
        return days;
    }

    var lines = text.split(/\n+/);
    var wishes = [];
    var parsed = 0;
    var errors = [];

    for (var li = 0; li < lines.length; li++) {
        var line = lines[li].trim();
        if (!line) continue;

        var entries = line.split(/[,，、]+/);
        var currentStaff = null;

        for (var ei = 0; ei < entries.length; ei++) {
            var entry = entries[ei].trim();
            if (!entry) continue;

            // 全休パターン: 名前+全+区分 (例: 内田全休, 内田全有給)
            var allDayMatch = entry.match(/^(.+?)全(.+)$/);
            if (allDayMatch) {
                var adName = allDayMatch[1].trim();
                var adShiftKey = allDayMatch[2].trim();
                var adShift = shiftMap[adShiftKey];
                if (!adShift) {
                    errors.push(adShiftKey + " (区分不明)");
                    continue;
                }
                var adStaff = null;
                if (adName) {
                    for (var si = 0; si < staff.length; si++) {
                        if (staff[si].name.indexOf(adName) >= 0 || adName.indexOf(staff[si].name) >= 0) {
                            adStaff = staff[si];
                            break;
                        }
                    }
                }
                if (!adStaff && currentStaff) adStaff = currentStaff;
                if (!adStaff) {
                    errors.push((adName || entry) + " (職員不明)");
                    continue;
                }
                currentStaff = adStaff;
                var daysInMonth = new Date(targetYear, targetMonth, 0).getDate();
                var allDaysArr = [];
                for (var ad = 1; ad <= daysInMonth; ad++) allDaysArr.push(ad);
                wishes.push({
                    staffId: adStaff.id,
                    type: "assign",
                    days: allDaysArr,
                    shift: adShift
                });
                parsed += daysInMonth;
                continue;
            }

            var hasDigit = /\d/.test(entry);

            if (!hasDigit) {
                // 曜日指定パターン: 名前+曜日+区分
                var shiftKeys = ["休み", "休", "オフ", "公", "出勤", "出", "日勤", "リフレ", "リフ", "リ", "有休", "有給", "有", "深夜", "準夜", "夜勤", "夜", "準", "深", "早出", "早", "遅出", "遅"];
                var foundShiftKey = null;
                var restEntry = entry;
                for (var ski = 0; ski < shiftKeys.length; ski++) {
                    if (entry.endsWith(shiftKeys[ski])) {
                        foundShiftKey = shiftKeys[ski];
                        restEntry = entry.slice(0, -shiftKeys[ski].length);
                        break;
                    }
                }

                if (foundShiftKey && restEntry.length > 0) {
                    // restEntryが全て曜日かチェック
                    var allWeekdays = /^[月火水木金土日]+$/.test(restEntry);
                    var wdNamePart = "";
                    var weekdayStr = "";

                    if (allWeekdays) {
                        // 曜日のみ（名前なし）→ 前の職員を引き継ぐ
                        weekdayStr = restEntry;
                    } else {
                        var weekdayMatch = restEntry.match(/^(.+?)([月火水木金土日]+)$/);
                        if (weekdayMatch) {
                            wdNamePart = weekdayMatch[1].trim();
                            weekdayStr = weekdayMatch[2];
                        }
                    }

                    if (weekdayStr) {
                        var wdStaff = null;
                        if (wdNamePart) {
                            for (var si = 0; si < staff.length; si++) {
                                if (staff[si].name.indexOf(wdNamePart) >= 0 || wdNamePart.indexOf(staff[si].name) >= 0) {
                                    wdStaff = staff[si];
                                    break;
                                }
                            }
                        }

                        if (!wdStaff && currentStaff) {
                            wdStaff = currentStaff;
                        }

                        if (!wdStaff) {
                            errors.push((wdNamePart || entry) + " (職員不明)");
                            continue;
                        }

                        currentStaff = wdStaff;

                        var wdShift = shiftMap[foundShiftKey];
                        if (!wdShift) {
                            errors.push(foundShiftKey + " (区分不明)");
                            continue;
                        }

                        var allDays = [];
                        for (var ci = 0; ci < weekdayStr.length; ci++) {
                            var charDay = weekdayStr[ci];
                            if (dayOfWeekMap[charDay] !== undefined) {
                                var daysForThisWeekday = getDaysForWeekday(dayOfWeekMap[charDay]);
                                for (var di = 0; di < daysForThisWeekday.length; di++) {
                                    allDays.push(daysForThisWeekday[di]);
                                }
                            }
                        }

                        if (allDays.length > 0) {
                            wishes.push({
                                staffId: wdStaff.id,
                                type: "assign",
                                days: allDays,
                                shift: wdShift
                            });
                            parsed += allDays.length;
                        }
                        continue;
                    }
                }

                errors.push(entry + " (形式不明)");
                continue;
            }

            // 日付指定パターン: 名前+日付(複数可)+区分
            // 例: 平松5休, 平松5 6 7休, 平松5,6,7深夜
            var match = entry.match(/^(.+?)([\d\s,、]+)(.+)$/);
            if (!match) {
                errors.push(entry + " (形式不明)");
                continue;
            }

            var namePart = match[1].trim();
            var daysStr = match[2].trim();
            var shiftKey = match[3].trim();

            // 日付を抽出（スペース、カンマ、読点で区切り）
            var dayNumbers = daysStr.split(/[\s,、]+/).map(function(d) { return parseInt(d); }).filter(function(d) { return !isNaN(d) && d >= 1 && d <= 31; });

            if (dayNumbers.length === 0) {
                errors.push(entry + " (日付不明)");
                continue;
            }

            if (namePart) {
                var foundStaff = null;
                for (var si = 0; si < staff.length; si++) {
                    if (staff[si].name.indexOf(namePart) >= 0 || namePart.indexOf(staff[si].name) >= 0) {
                        foundStaff = staff[si];
                        break;
                    }
                }
                if (foundStaff) {
                    currentStaff = foundStaff;
                }
            }

            if (!currentStaff) {
                errors.push((namePart || entry) + " (職員不明)");
                continue;
            }

            var shift = shiftMap[shiftKey];
            if (!shift) {
                errors.push(shiftKey + " (区分不明)");
                continue;
            }

            wishes.push({
                staffId: currentStaff.id,
                type: "assign",
                days: dayNumbers,
                shift: shift
            });
            parsed += dayNumbers.length;
        }
    }

    if (wishes.length > 0) {
        var wk = targetYear + "-" + targetMonth;
        var sk = targetYear + "-" + targetMonth + "-" + targetWard;
        if (!D.wishes[wk]) D.wishes[wk] = [];
        if (!D.shifts[sk]) D.shifts[sk] = {};

        // 固定シフト職員のIDを取得
        var fixedStaffIds = {};
        for (var fi = 0; fi < staff.length; fi++) {
            if (staff[fi].workType === "fixed") {
                fixedStaffIds[staff[fi].id] = true;
            }
        }

        var fixedCount = 0;
        for (var wi = 0; wi < wishes.length; wi++) {
            var w = wishes[wi];
            // 固定シフト職員の場合はD.shiftsにも直接反映
            if (fixedStaffIds[w.staffId]) {
                for (var di = 0; di < w.days.length; di++) {
                    D.shifts[sk][w.staffId + "-" + w.days[di]] = w.shift;
                }
                fixedCount += w.days.length;
                w.isFixed = true;  // 固定シフトフラグ
            }
            // 全職員D.wishesに追加（表示用）
            D.wishes[wk].push(w);
        }

        save();
        var msg = "✅ " + parsed + "件追加";
        if (fixedCount > 0) msg += " (固定" + fixedCount + "件直接反映)";
        if (errors.length > 0) msg += " / ⚠️ " + errors.join(", ");
        document.getElementById("parseResult").textContent = msg;
        document.getElementById("wishNatural").value = "";
        render();
    } else {
        document.getElementById("parseResult").textContent = "❌ 保存できませんでした: " + errors.join(", ");
    }
}

function renderWishUI() {
    // 職員プルダウン
    var sel = document.getElementById("wishStaffSelect");
    if (!sel) return;
    var prevVal = sel.value;
    sel.innerHTML = "<option value=''>-- 職員 --</option>";
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    for (var i = 0; i < staff.length; i++) {
        var opt = document.createElement("option");
        opt.value = staff[i].id;
        opt.textContent = staff[i].name;
        sel.appendChild(opt);
    }
    if (prevVal) sel.value = prevVal;

    // 日付チップ（ドラッグ選択対応）
    var chipBox = document.getElementById("wishDayChips");
    if (!chipBox) return;
    var days = new Date(Y, M, 0).getDate();
    var chipStyle = "padding:4px 0;font-size:.85rem;min-width:34px;height:30px;border-radius:5px;border:1px solid var(--border);cursor:pointer;text-align:center;user-select:none;-webkit-user-select:none";
    var html = "<button class='wish-day-chip wish-day-all' data-day='all' onmousedown='wishDayMouseDown(this,event)' ontouchstart='wishDayMouseDown(this,event)' style='" + chipStyle + ";background:var(--bg3);font-weight:700'>全</button>";
    for (var d = 1; d <= days; d++) {
        var dt = new Date(Y, M - 1, d);
        var dw = dt.getDay();
        var cls = dw === 0 ? "color:var(--red)" : (dw === 6 ? "color:var(--blue)" : "");
        html += "<button class='wish-day-chip' data-day='" + d + "' onmousedown='wishDayMouseDown(this,event)' onmouseenter='wishDayMouseEnter(this)' ontouchstart='wishDayMouseDown(this,event)' style='" + chipStyle + ";background:var(--bg2);" + cls + "'>" + d + "</button>";
    }
    chipBox.innerHTML = html;

    // シフトボタン
    var btnBox = document.getElementById("wishShiftBtns");
    if (!btnBox) return;
    var WISH_BTNS = [
        { shift: "off", label: "休", cls: "shift-off" },
        { shift: "paid", label: "有給", cls: "shift-paid" },
        { shift: "day", label: "日勤", cls: "shift-day" },
        { shift: "late", label: "遅出", cls: "shift-late" },
        { shift: "night2", label: "夜勤", cls: "shift-night2" },
        { shift: "junnya", label: "準夜", cls: "shift-junnya" },
        { shift: "shinya", label: "深夜", cls: "shift-shinya" },
        { shift: "refresh", label: "リフレ", cls: "shift-refresh" }
    ];
    var bhtml = "";
    var hideLate = (W === "1" || W === "3");
    for (var i = 0; i < WISH_BTNS.length; i++) {
        var b = WISH_BTNS[i];
        if (hideLate && b.shift === "late") continue;
        bhtml += "<button class='btn " + b.cls + "' data-shift='" + b.shift + "' onclick='addWishFromUI(this)' style='padding:.25rem .5rem;font-size:.8rem;font-weight:600'>" + b.label + "</button>";
    }
    btnBox.innerHTML = bhtml;
}

// --- ドラッグ選択対応 ---
var wishDragState = { active: false, mode: null }; // mode: "select" or "deselect"

function selectWishChip(el) {
    el.classList.add("wish-day-selected");
    el.style.background = "var(--blue)";
    el.style.color = "#fff";
    el.style.fontWeight = "bold";
}

function deselectWishChip(el) {
    el.classList.remove("wish-day-selected");
    el.style.background = el.classList.contains("wish-day-all") ? "var(--bg3)" : "var(--bg2)";
    el.style.fontWeight = el.classList.contains("wish-day-all") ? "600" : "";
    el.style.color = "";
    var day = parseInt(el.getAttribute("data-day"));
    if (!isNaN(day)) {
        var dt = new Date(Y, M - 1, day);
        var dw = dt.getDay();
        if (dw === 0) el.style.color = "var(--red)";
        else if (dw === 6) el.style.color = "var(--blue)";
    }
}

function syncWishAllButton() {
    var box = document.getElementById("wishDayChips");
    if (!box) return;
    var allBtn = box.querySelector(".wish-day-all");
    if (!allBtn) return;
    var chips = box.querySelectorAll(".wish-day-chip:not(.wish-day-all)");
    var selectedCount = 0;
    for (var i = 0; i < chips.length; i++) {
        if (chips[i].classList.contains("wish-day-selected")) selectedCount++;
    }
    if (selectedCount === chips.length) {
        allBtn.classList.add("wish-day-selected");
        allBtn.style.background = "var(--blue)";
        allBtn.style.color = "#fff";
    } else {
        allBtn.classList.remove("wish-day-selected");
        allBtn.style.background = "var(--bg3)";
        allBtn.style.color = "";
    }
}

function wishDayMouseDown(el, e) {
    if (e) e.preventDefault();
    if (el.getAttribute("data-day") === "all") {
        // 全選択/全解除（ドラッグなし）
        var chips = el.parentElement.querySelectorAll(".wish-day-chip:not(.wish-day-all)");
        var allSelected = el.classList.contains("wish-day-selected");
        for (var i = 0; i < chips.length; i++) {
            if (allSelected) deselectWishChip(chips[i]);
            else selectWishChip(chips[i]);
        }
        if (allSelected) deselectWishChip(el);
        else selectWishChip(el);
        return;
    }
    // ドラッグ開始: 最初のチップの状態で選択/解除モードを決定
    var wasSelected = el.classList.contains("wish-day-selected");
    wishDragState.active = true;
    wishDragState.mode = wasSelected ? "deselect" : "select";
    if (wasSelected) deselectWishChip(el);
    else selectWishChip(el);
    syncWishAllButton();
}

function wishDayMouseEnter(el) {
    if (!wishDragState.active) return;
    if (el.getAttribute("data-day") === "all") return;
    if (wishDragState.mode === "select") selectWishChip(el);
    else deselectWishChip(el);
    syncWishAllButton();
}

function wishDayMouseUp() {
    wishDragState.active = false;
    wishDragState.mode = null;
}

// グローバルmouseup/touchendでドラッグ終了
document.addEventListener("mouseup", wishDayMouseUp);
document.addEventListener("touchend", wishDayMouseUp);

// タッチドラッグ対応: touchmoveで指の下の要素を検出
document.addEventListener("touchmove", function(e) {
    if (!wishDragState.active) return;
    var touch = e.touches[0];
    var el = document.elementFromPoint(touch.clientX, touch.clientY);
    if (el && el.classList && el.classList.contains("wish-day-chip") && !el.classList.contains("wish-day-all")) {
        wishDayMouseEnter(el);
    }
    e.preventDefault();
}, { passive: false });

var wishQueue = [];

function addWishFromUI(btn) {
    var staffId = document.getElementById("wishStaffSelect").value;
    if (!staffId) {
        document.getElementById("parseResult").textContent = "⚠️ 職員を選択してください";
        return;
    }
    var shift = btn.getAttribute("data-shift");
    var chips = document.querySelectorAll("#wishDayChips .wish-day-chip.wish-day-selected:not(.wish-day-all)");
    if (chips.length === 0) {
        document.getElementById("parseResult").textContent = "⚠️ 日付を選択してください";
        return;
    }
    var selectedDays = [];
    for (var i = 0; i < chips.length; i++) {
        selectedDays.push(parseInt(chips[i].getAttribute("data-day")));
    }
    selectedDays.sort(function(a, b) { return a - b; });

    // 職員名取得
    var staffName = document.getElementById("wishStaffSelect").selectedOptions[0].textContent;

    wishQueue.push({ staffId: staffId, staffName: staffName, days: selectedDays, shift: shift });

    // 日付選択・シフトボタン選択をリセット（職員はそのまま）
    resetWishDayChips();
    clearWishShiftBtnSelection();

    document.getElementById("parseResult").textContent = "";
    renderWishQueue();
}

function clearWishShiftBtnSelection() {
    var btnBox = document.getElementById("wishShiftBtns");
    if (!btnBox) return;
    var btns = btnBox.querySelectorAll("button[data-shift]");
    for (var i = 0; i < btns.length; i++) {
        btns[i].style.outline = "";
        btns[i].style.outlineOffset = "";
        btns[i].style.boxShadow = "";
    }
}

function resetWishDayChips() {
    var allChips = document.querySelectorAll("#wishDayChips .wish-day-chip");
    for (var i = 0; i < allChips.length; i++) {
        allChips[i].classList.remove("wish-day-selected");
        allChips[i].style.background = allChips[i].classList.contains("wish-day-all") ? "var(--bg3)" : "var(--bg2)";
        allChips[i].style.color = "";
        allChips[i].style.fontWeight = allChips[i].classList.contains("wish-day-all") ? "600" : "";
        var day = parseInt(allChips[i].getAttribute("data-day"));
        if (!isNaN(day)) {
            var dt = new Date(Y, M - 1, day);
            var dw = dt.getDay();
            if (dw === 0) allChips[i].style.color = "var(--red)";
            else if (dw === 6) allChips[i].style.color = "var(--blue)";
        }
    }
}

function renderWishQueue() {
    var box = document.getElementById("wishQueue");
    var commitBtn = document.getElementById("wishCommitBtn");
    if (!box) return;
    if (wishQueue.length === 0) {
        box.innerHTML = "";
        if (commitBtn) commitBtn.style.display = "none";
        return;
    }
    if (commitBtn) commitBtn.style.display = "";

    var shiftNames = {
        "off": "休", "day": "日勤", "refresh": "リフレ", "paid": "有給",
        "night2": "夜勤", "junnya": "準夜", "shinya": "深夜", "late": "遅出"
    };
    var shiftClasses = {
        "off": "shift-off", "day": "shift-day", "refresh": "shift-refresh", "paid": "shift-paid",
        "night2": "shift-night2", "junnya": "shift-junnya", "shinya": "shift-shinya", "late": "shift-late"
    };
    var daysInMonth = new Date(Y, M, 0).getDate();
    var html = "";
    for (var i = 0; i < wishQueue.length; i++) {
        var q = wishQueue[i];
        var daysLabel = q.days.length >= daysInMonth ? "全日" : q.days.join(",");
        var cls = shiftClasses[q.shift] || "";
        html += "<span class='" + cls + "' style='display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .5rem;border-radius:4px;font-size:.8rem'>";
        html += "<b>" + escHtml(q.staffName) + "</b> " + daysLabel + " " + (shiftNames[q.shift] || escHtml(q.shift));
        html += "<button onclick='removeFromWishQueue(" + i + ")' style='background:none;border:none;color:var(--red);cursor:pointer;padding:0 .2rem;font-size:1rem'>×</button>";
        html += "</span>";
    }
    box.innerHTML = html;
}

function removeFromWishQueue(idx) {
    wishQueue.splice(idx, 1);
    renderWishQueue();
}

function commitWishQueue() {
    if (wishQueue.length === 0) return;

    var wk = Y + "-" + M;
    var sk = Y + "-" + M + "-" + W;
    if (!D.wishes[wk]) D.wishes[wk] = [];
    if (!D.shifts[sk]) D.shifts[sk] = {};

    // 固定シフト職員チェック
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    var fixedStaffIds = {};
    for (var i = 0; i < staff.length; i++) {
        if (staff[i].workType === "fixed") fixedStaffIds[staff[i].id] = true;
    }

    var total = 0;
    var fixedCount = 0;
    for (var qi = 0; qi < wishQueue.length; qi++) {
        var q = wishQueue[qi];
        var w = { staffId: q.staffId, type: "assign", days: q.days, shift: q.shift };
        if (fixedStaffIds[q.staffId]) {
            for (var di = 0; di < q.days.length; di++) {
                D.shifts[sk][q.staffId + "-" + q.days[di]] = q.shift;
            }
            fixedCount += q.days.length;
            w.isFixed = true;
        }
        D.wishes[wk].push(w);
        total += q.days.length;
    }

    save();
    var msg = "✅ " + wishQueue.length + "件 (" + total + "日分) 保存";
    if (fixedCount > 0) msg += " (固定" + fixedCount + "件直接反映)";
    document.getElementById("parseResult").textContent = msg;
    wishQueue = [];
    renderWishQueue();
    clearWishShiftBtnSelection();
    render();
}

function renderWishes() {
    var wk = Y + "-" + M;
    var allWishes = D.wishes[wk] || [];
    var list = document.getElementById("wishList");
    if (!list) return;

    // 現在の病棟の職員IDを取得
    var wardStaffIds = {};
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) {
            wardStaffIds[D.staff[i].id] = D.staff[i].name;
        }
    }

    // 現在の病棟の職員の希望のみをフィルタリング
    var wishes = [];
    var wishIndices = []; // 元のインデックスを保持（削除用）
    for (var i = 0; i < allWishes.length; i++) {
        if (wardStaffIds[allWishes[i].staffId]) {
            wishes.push(allWishes[i]);
            wishIndices.push(i);
        }
    }

    if (wishes.length === 0) {
        list.innerHTML = "<span style='color:var(--text2)'>希望なし</span>";
        return;
    }

    var shiftNames = {
        "off": "休", "day": "出", "refresh": "リ", "paid": "有",
        "night2": "夜", "junnya": "準", "shinya": "深", "late": "遅"
    };

    var shiftClasses = {
        "off": "shift-off", "day": "shift-day", "refresh": "shift-refresh", "paid": "shift-paid",
        "night2": "shift-night2", "junnya": "shift-junnya", "shinya": "shift-shinya", "late": "shift-late"
    };
    var daysInMonth = new Date(Y, M, 0).getDate();
    var html = "";
    for (var i = 0; i < wishes.length; i++) {
        var w = wishes[i];
        var name = wardStaffIds[w.staffId] || w.staffId;
        var daysLabel = "?";
        if (w.days) {
            if (w.days.length >= daysInMonth) {
                daysLabel = "全日";
            } else {
                daysLabel = w.days.join(",");
            }
        }
        var shift = shiftNames[w.shift] || w.shift;
        var sCls = shiftClasses[w.shift] || "";
        var daysJson = JSON.stringify(w.days || []).replace(/"/g, "&quot;");
        var origIdx = wishIndices[i];
        html += "<span draggable='true' data-wish-idx='" + origIdx + "' style='display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .5rem;border-radius:4px;margin:.1rem;cursor:grab;user-select:none;-webkit-user-select:none' class='" + sCls + " wish-chip-draggable' onclick='editWish(\"" + w.staffId + "\",\"" + w.shift + "\",\"" + daysJson + "\")' title='ドラッグで並替 / クリックで編集'>";
        html += "<b>" + name + "</b> " + daysLabel + " " + shift;
        html += "<button onclick='event.stopPropagation();deleteWish(\"" + w.staffId + "\",\"" + w.shift + "\",\"" + (w.days || []).join(",") + "\")' style='background:none;border:none;color:var(--red);cursor:pointer;padding:0 .2rem;font-size:1rem'>×</button>";
        html += "</span>";
    }
    list.innerHTML = html;
    setupWishDragAndDrop(list);
}

// --- 希望チップ ドラッグ&ドロップ並替 ---
var wishDragChip = null;
var wishDragMoved = false;

function setupWishDragAndDrop(container) {
    var chips = container.querySelectorAll(".wish-chip-draggable");
    for (var i = 0; i < chips.length; i++) {
        chips[i].addEventListener("dragstart", function(e) {
            wishDragChip = this;
            wishDragMoved = false;
            this.style.opacity = "0.4";
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", this.getAttribute("data-wish-idx"));
        });
        chips[i].addEventListener("dragend", function() {
            this.style.opacity = "";
            // ドロップインジケータを全て除去
            var all = container.querySelectorAll(".wish-chip-draggable");
            for (var j = 0; j < all.length; j++) {
                all[j].style.borderLeft = "";
                all[j].style.borderRight = "";
            }
            if (!wishDragMoved) wishDragChip = null;
        });
        chips[i].addEventListener("dragover", function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            // ドロップ位置のインジケータ表示
            var all = container.querySelectorAll(".wish-chip-draggable");
            for (var j = 0; j < all.length; j++) {
                all[j].style.borderLeft = "";
                all[j].style.borderRight = "";
            }
            if (this !== wishDragChip) {
                var rect = this.getBoundingClientRect();
                var mid = rect.left + rect.width / 2;
                if (e.clientX < mid) {
                    this.style.borderLeft = "3px solid var(--blue)";
                } else {
                    this.style.borderRight = "3px solid var(--blue)";
                }
            }
        });
        chips[i].addEventListener("drop", function(e) {
            e.preventDefault();
            if (!wishDragChip || wishDragChip === this) return;
            wishDragMoved = true;
            var fromIdx = parseInt(wishDragChip.getAttribute("data-wish-idx"));
            var toIdx = parseInt(this.getAttribute("data-wish-idx"));
            // マウス位置で前後を判定
            var rect = this.getBoundingClientRect();
            var insertBefore = e.clientX < (rect.left + rect.width / 2);
            reorderWish(fromIdx, toIdx, insertBefore);
            wishDragChip = null;
        });
        // クリック抑制: ドラッグ後はonclickを発火させない
        chips[i].addEventListener("click", function(e) {
            if (wishDragMoved) {
                e.stopImmediatePropagation();
                e.preventDefault();
                wishDragMoved = false;
            }
        }, true);
    }
}

function reorderWish(fromOrigIdx, toOrigIdx, insertBefore) {
    var wk = Y + "-" + M;
    var allWishes = D.wishes[wk];
    if (!allWishes) return;

    // 元の位置から取り出す
    var item = allWishes.splice(fromOrigIdx, 1)[0];
    // fromを抜いた後のtoの位置を補正
    var newToIdx = toOrigIdx;
    if (fromOrigIdx < toOrigIdx) newToIdx--;
    // 挿入位置
    var insertIdx = insertBefore ? newToIdx : newToIdx + 1;
    allWishes.splice(insertIdx, 0, item);

    save();
    renderWishes();
}

function editWish(staffId, shift, daysJson) {
    var days = JSON.parse(daysJson.replace(/&quot;/g, '"'));

    // 職員選択を復元
    var sel = document.getElementById("wishStaffSelect");
    if (sel) sel.value = staffId;

    // 日付チップを復元: まずリセットしてから該当日を選択
    resetWishDayChips();
    var chipBox = document.getElementById("wishDayChips");
    if (chipBox) {
        for (var di = 0; di < days.length; di++) {
            var chip = chipBox.querySelector(".wish-day-chip[data-day='" + days[di] + "']");
            if (chip) selectWishChip(chip);
        }
        syncWishAllButton();
    }

    // シフトボタンの選択状態を復元
    selectWishShiftBtn(shift);

    // 職員名を取得
    var staffName = "";
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === staffId) { staffName = D.staff[i].name; break; }
    }

    document.getElementById("parseResult").textContent = "✏️ " + staffName + " の希望を選択中（追加入力して確定）";

    // 元の希望を削除
    var wk = Y + "-" + M;
    if (D.wishes[wk]) {
        var isFixed = false;
        var staffWard = W;
        for (var i = 0; i < D.staff.length; i++) {
            if (D.staff[i].id === staffId) {
                isFixed = D.staff[i].workType === "fixed";
                staffWard = D.staff[i].ward;
                break;
            }
        }
        if (isFixed) {
            var sk = Y + "-" + M + "-" + staffWard;
            if (D.shifts[sk]) {
                for (var di = 0; di < days.length; di++) {
                    delete D.shifts[sk][staffId + "-" + days[di]];
                }
            }
        }
        D.wishes[wk] = D.wishes[wk].filter(function(w) {
            if (w.staffId !== staffId || w.shift !== shift) return true;
            if (!w.days || w.days.length !== days.length) return true;
            for (var i = 0; i < days.length; i++) {
                if (w.days[i] !== days[i]) return true;
            }
            return false;
        });
        save();
    }

    renderWishes();

    // 確定ボタンを表示（シフトボタンクリックでキューに入り確定できるように）
    var commitBtn = document.getElementById("wishCommitBtn");
    if (commitBtn) commitBtn.style.display = "";
}

function selectWishShiftBtn(shift) {
    var btnBox = document.getElementById("wishShiftBtns");
    if (!btnBox) return;
    var btns = btnBox.querySelectorAll("button[data-shift]");
    for (var i = 0; i < btns.length; i++) {
        btns[i].style.outline = "";
        btns[i].style.outlineOffset = "";
        btns[i].style.boxShadow = "";
    }
    var target = btnBox.querySelector("button[data-shift='" + shift + "']");
    if (target) {
        target.style.outline = "3px solid var(--blue)";
        target.style.outlineOffset = "1px";
        target.style.boxShadow = "0 0 6px rgba(37,99,235,0.5)";
    }
}

function deleteWish(staffId, shift, daysStr) {
    var wk = Y + "-" + M;
    if (!D.wishes[wk]) return;
    var targetDays = daysStr.split(",").map(Number);

    // 固定シフト職員かどうか確認
    var isFixed = false;
    var staffWard = W;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === staffId) {
            isFixed = D.staff[i].workType === "fixed";
            staffWard = D.staff[i].ward;
            break;
        }
    }

    // 固定シフト職員の場合はD.shiftsからも削除
    if (isFixed) {
        var sk = Y + "-" + M + "-" + staffWard;
        if (D.shifts[sk]) {
            for (var di = 0; di < targetDays.length; di++) {
                delete D.shifts[sk][staffId + "-" + targetDays[di]];
            }
        }
    }

    D.wishes[wk] = D.wishes[wk].filter(function (w) {
        if (w.staffId !== staffId || w.shift !== shift) return true;
        if (!w.days || w.days.length !== targetDays.length) return true;
        for (var i = 0; i < targetDays.length; i++) {
            if (w.days[i] !== targetDays[i]) return true;
        }
        return false;
    });
    save();
    render();
}

function getWorkTypeBadge(wt) {
    var baseStyle = "display:inline-block;width:60px;text-align:center;padding:.2rem 0;border-radius:4px;font-size:.75rem;color:#fff;font-weight:bold";
    if (wt === "day_only") return "<span style=\"" + baseStyle + ";background:#6b7280\">日勤のみ</span>";
    if (wt === "2kohtai") return "<span style=\"" + baseStyle + ";background:#8b5cf6\">二交代</span>";
    if (wt === "3kohtai") return "<span style=\"" + baseStyle + ";background:#ec4899\">三交代</span>";
    if (wt === "night_only") return "<span style=\"" + baseStyle + ";background:#1e40af\">夜専従</span>";
    if (wt === "fixed") return "<span style=\"" + baseStyle + ";background:#6b7280\">固定</span>";
    return "";
}

function getStaffTypeBadge(t) {
    var baseStyle = "font-size:.7rem;display:inline-block;width:60px;text-align:center;padding:2px 0;border-radius:4px";
    if (t === "nurse") return "<span style=\"" + baseStyle + ";background:#dbeafe;color:#1e40af\">看護師</span>";
    if (t === "junkango") return "<span style=\"" + baseStyle + ";background:#fef3c7;color:#92400e\">准看護師</span>";
    if (t === "nurseaide") return "<span style=\"" + baseStyle + ";background:#f3e8ff;color:#7c3aed\">NurseAide</span>";
    return "";
}

function getStaffTypeColor(t) {
    if (t === "nurse") return "#dbeafe";       // 青 - 看護師
    if (t === "junkango") return "#fef3c7";    // 黄 - 准看護師
    if (t === "nurseaide") return "#f3e8ff";   // 紫 - NurseAide
    return "#f3f4f6";                          // グレー - デフォルト
}


function renderStaff() {
    var list = document.getElementById("staffList");
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    var html = "";
    for (var i = 0; i < staff.length; i++) {
        var s = staff[i];
        var wt = s.workType || "2kohtai";
        var maxN = s.maxNight !== undefined ? s.maxNight : 5;
        var sType = s.type || "nurse";
        var typeBadge = getStaffTypeBadge(sType);
        var bgColor = getStaffTypeColor(sType);
        html += "<div class=\"staff-item\" draggable=\"true\" data-id=\"" + s.id + "\" ondragstart=\"drag(event)\" ondrop=\"drop(event)\" ondragover=\"allowDrop(event)\">";
        html += "<div class=\"staff-info\" style=\"pointer-events:none;flex-wrap:nowrap\">";
        html += "<span style=\"cursor:grab;margin-right:8px;opacity:0.5\">☰</span>";
        html += "<span style=\"display:inline-block;min-width:100px;background:" + bgColor + ";padding:2px 8px;border-radius:4px;white-space:nowrap\">" + escHtml(s.name) + "</span>";
        html += "<span style=\"display:inline-block;min-width:75px;margin-left:8px;white-space:nowrap\">" + typeBadge + "</span>";
        html += "<span style=\"display:inline-block;min-width:70px;white-space:nowrap\">" + getWorkTypeBadge(wt) + "</span>";
        if (wt !== "day_only") {
            html += "<span style=\"font-size:.8rem;color:var(--text2);white-space:nowrap\">上限" + maxN + "</span>";
        }
        html += "</div>";
        html += "<span>";
        html += "<button class=\"btn btn-secondary\" style=\"font-size:.7rem;padding:.2rem .4rem\" onclick=\"editStaff('" + s.id + "')\">編集</button> ";
        html += "<button class=\"btn btn-danger\" style=\"font-size:.7rem;padding:.2rem .4rem\" onclick=\"deleteStaff('" + s.id + "')\">削除</button>";
        html += "</span></div>";
    }
    if (staff.length === 0) {
        html = "<div style=\"color:var(--text2);font-size:.9rem;padding:1rem\">職員がいません</div>";
    }
    list.innerHTML = html;
}

var draggedId = null;
function drag(ev) {
    draggedId = ev.target.getAttribute("data-id");
    ev.dataTransfer.setData("text", draggedId);
    ev.target.style.opacity = "0.4";
}

function allowDrop(ev) {
    ev.preventDefault();
}

function drop(ev) {
    ev.preventDefault();
    var target = ev.target;
    while (!target.classList.contains("staff-item") && target.parentElement) {
        target = target.parentElement;
    }
    var targetId = target.getAttribute("data-id");
    if (draggedId && targetId && draggedId !== targetId) {
        // Reorder D.staff
        var staffInWard = [];
        var indices = [];
        for (var i = 0; i < D.staff.length; i++) {
            if (D.staff[i].ward === W) {
                staffInWard.push(D.staff[i]);
                indices.push(i);
            }
        }

        var fromIdx = -1, toIdx = -1;
        for (var i = 0; i < staffInWard.length; i++) {
            if (staffInWard[i].id === draggedId) fromIdx = i;
            if (staffInWard[i].id === targetId) toIdx = i;
        }

        if (fromIdx >= 0 && toIdx >= 0) {
            // move element in D.staff
            var movedItem = D.staff[indices[fromIdx]];
            D.staff.splice(indices[fromIdx], 1);

            // Recalculate insertion index because splice shifted indices
            var newTargetGlobalIdx = -1;
            // Find target again in D.staff to get fresh index
            for (var i = 0; i < D.staff.length; i++) {
                if (D.staff[i].id === targetId) {
                    newTargetGlobalIdx = i;
                    break;
                }
            }

            // If we dropped ON 'target', we usually insert BEFORE it.
            // EXCEPT if we came from above, inserting before puts it back where it was? No.
            // Let's simply insert at currentTargetIdx.
            D.staff.splice(newTargetGlobalIdx, 0, movedItem);

            save();
            render();
            renderStaff();
        }
    }

    // Reset opacity
    var items = document.querySelectorAll(".staff-item");
    for (var i = 0; i < items.length; i++) items[i].style.opacity = "1";
    draggedId = null;
}

function handleWishDrop(e) {
    e.preventDefault();
    var file = e.dataTransfer.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function (e) {
            document.getElementById("wishJson").value = e.target.result;
        };
        reader.readAsText(file);
    }
}


function updateMaxNightHint() {
    var wt = document.getElementById("staffWorkType").value;
    var el = document.getElementById("maxNightHint");
    if (!el) return;
    if (wt === "2kohtai") {
        el.textContent = "二交代: night2の回数上限（1回=翌日ake込みで2日拘束）";
    } else if (wt === "3kohtai") {
        el.textContent = "三交代: junnya+shinyaの合計回数上限";
    } else if (wt === "night_only") {
        el.textContent = "夜勤専従: night2の回数上限";
    } else {
        el.textContent = "";
    }
}

function openStaffModal() {
    document.getElementById("staffModalTitle").textContent = "新規";
    document.getElementById("staffForm").reset();
    document.getElementById("editStaffId").value = "";
    document.getElementById("staffIdDisplay").style.display = "none";
    document.getElementById("staffWard").value = W;
    document.getElementById("staffWorkType").value = "2kohtai";
    document.getElementById("staffMaxNight").value = "5";
    document.getElementById("staffNightRestriction").value = "";
    document.getElementById("fixedPatternSection").style.display = "none";
    updateMaxNightHint();
    document.getElementById("staffModal").classList.add("active");
}

function editStaff(id) {
    var s = null;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === id) { s = D.staff[i]; break; }
    }
    document.getElementById("staffModalTitle").textContent = "編集";
    document.getElementById("editStaffId").value = s.id;
    document.getElementById("staffIdDisplay").style.display = "block";
    document.getElementById("staffIdReadonly").value = s.id;
    document.getElementById("staffName").value = s.name;
    document.getElementById("staffWard").value = s.ward;
    document.getElementById("staffWorkType").value = s.workType || "2kohtai";
    updateMaxNightHint();
    document.getElementById("staffMaxNight").value = s.maxNight !== undefined ? s.maxNight : 5;
    document.getElementById("staffMinNight").value = s.minNight !== undefined ? s.minNight : 0;
    document.getElementById("staffType").value = s.type || "nurse";
    document.getElementById("staffNightRestriction").value = s.nightRestriction || "";
    // 固定シフトパターンは希望シフトで対応するため非表示
    document.getElementById("fixedPatternSection").style.display = "none";
    document.getElementById("staffModal").classList.add("active");
}

function saveStaff(e) {
    e.preventDefault();
    var id = document.getElementById("editStaffId").value || Date.now().toString();
    var nr = document.getElementById("staffNightRestriction").value;
    var wt = document.getElementById("staffWorkType").value;
    var fp = null;
    if (wt === "fixed") {
        fp = {};
        for (var i = 0; i < 7; i++) {
            fp[String(i)] = document.getElementById("fp" + i).value;
        }
    }
    var data = {
        id: id,
        name: document.getElementById("staffName").value,
        ward: document.getElementById("staffWard").value,
        workType: wt,
        maxNight: parseInt(document.getElementById("staffMaxNight").value) || 5,
        minNight: parseInt(document.getElementById("staffMinNight").value) || 0,
        type: document.getElementById("staffType").value,
        nightRestriction: nr || null,
        fixedPattern: fp
    };
    var idx = -1;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === id) { idx = i; break; }
    }
    if (idx >= 0) D.staff[idx] = data;
    else D.staff.push(data);
    save();
    syncStaffToBackend();
    renderStaff();
    render();
    document.getElementById("staffModal").classList.remove("active");
}

function deleteStaff(id) {
    if (!confirm("削除?")) return;
    var newStaff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id !== id) newStaff.push(D.staff[i]);
    }
    D.staff = newStaff;
    save();
    syncStaffToBackend();
    renderStaff();
    render();
}

function syncStaffToBackend() {
    fetch("/api/staff/migrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staff: D.staff })
    })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
            } else {
                console.error("職員データ同期エラー:", res.message);
            }
        })
        .catch(function (e) {
            console.error("職員データ同期エラー:", e);
        });
}

function openImportModal() {
    document.getElementById("importWard").value = W;
    document.getElementById("importStaffJson").value = "";
    document.getElementById("importPreview").style.display = "none";
    document.getElementById("importModal").classList.add("active");
}

function showImportSample() {
    var sample = [
        { id: "10060766", name: "内田ゆき", workType: "day_only", maxNight: 0 },
        { id: "10060952", name: "赤井一之", workType: "2kohtai", maxNight: 5 },
        { id: "10060993", name: "橋本昌樹", workType: "3kohtai", maxNight: 10 }
    ];
    document.getElementById("importStaffJson").value = JSON.stringify(sample, null, 2);
}

function previewImport() {
    try {
        var json = document.getElementById("importStaffJson").value;
        var arr = JSON.parse(json);
        var preview = document.getElementById("importPreview");
        var html = "<b>" + arr.length + "名</b><br>";
        for (var i = 0; i < arr.length; i++) {
            var e = arr[i];
            var name = e.name ? e.name.replace(/\s+/g, "") : "不明";
            var wt = WORK_TYPES[e.workType] || e.workType || "二交代";
            html += "<div class=\"import-item\">" + escHtml(e.id) + " | " + escHtml(name) + " | " + escHtml(wt) + "</div>";
        }
        preview.innerHTML = html;
        preview.style.display = "block";
    } catch (e) {
        alert("JSONエラー: " + e.message);
    }
}

function execImport() {
    try {
        var json = document.getElementById("importStaffJson").value;
        var arr = JSON.parse(json);
        var ward = document.getElementById("importWard").value;
        var addCount = 0;
        var updateCount = 0;
        for (var i = 0; i < arr.length; i++) {
            var e = arr[i];
            var id = e.id || Date.now().toString() + i;
            var name = e.name ? e.name.replace(/\s+/g, "") : "不明";
            var existIdx = -1;
            for (var j = 0; j < D.staff.length; j++) {
                if (D.staff[j].id === id) { existIdx = j; break; }
            }
            var staffData = {
                id: id,
                name: name,
                ward: ward,
                workType: e.workType || "2kohtai",
                maxNight: e.maxNight !== undefined ? e.maxNight : 5,
                minNight: e.minNight !== undefined ? e.minNight : 0,
                type: e.type || "nurse",
                nightRestriction: e.nightRestriction || null,
                fixedPattern: e.fixedPattern || null
            };
            if (existIdx >= 0) {
                D.staff[existIdx] = staffData;
                updateCount++;
            } else {
                D.staff.push(staffData);
                addCount++;
            }
        }
        save();
        syncStaffToBackend();
        renderStaff();
        render();
        document.getElementById("importModal").classList.remove("active");
        alert("新規 " + addCount + "名、更新 " + updateCount + "名");
    } catch (e) {
        alert("エラー: " + e.message);
    }
}

function checkConstraints() {
    var log = document.getElementById("checkLog");
    log.style.display = "block";
    log.innerHTML = "";
    var errors = [];
    var softWarnings = []; // ソフト制約違反（ペナルティpt付き）
    var warnings = []; // スタッフの希望未反映
    var policyWarnings = []; // 企業側ルール確認

    var days = new Date(Y, M, 0).getDate();
    var sk = Y + "-" + M + "-" + W;
    var shifts = D.shifts[sk] || {};
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }

    // 希望を取得
    var wk = Y + "-" + M;
    var wishes = D.wishes[wk] || [];

    // スタッフ別リフレッシュ日数を計算（ソルバーと同じロジック）
    var staffRefreshDays = {}; // {staffId: count}
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (w.shift === "refresh" && w.type === "assign") {
            var sid = w.staffId;
            if (!staffRefreshDays[sid]) staffRefreshDays[sid] = 0;
            staffRefreshDays[sid] += (w.days || []).length;
        }
    }

    // リフレッシュ日数→ペナルティ重み変換関数（ソルバーと一致）
    function shinyaOffPt(rc) { return rc === 0 ? 20 : rc === 1 ? 12 : rc === 2 ? 7 : 3; }
    function scatteredPt(rc) { return rc === 0 ? 15 : rc === 1 ? 10 : rc === 2 ? 6 : 3; }
    function junnyaOffShinyaPt(rc) { return rc === 0 ? 50 : rc === 1 ? 35 : rc === 2 ? 25 : 12; }

    // 前月データを取得
    var prevY = Y, prevM = M - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var prevDays = new Date(prevY, prevM, 0).getDate();
    var prevSk = prevY + "-" + prevM + "-" + W;
    var prevShifts = D.shifts[prevSk] || {};

    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        // 固定シフト者は全チェック対象外
        if (s.workType === "fixed") continue;
        var wt = s.workType || "2kohtai";
        var maxNight = s.maxNight !== undefined ? s.maxNight : 5;

        // 連続勤務数 (前月)
        var initConsecutive = 0;
        for (var k = 0; k < 10; k++) {
            var pd = prevDays - k;
            if (pd < 1) break;
            var psh = prevShifts[s.id + "-" + pd] || "";
            if (psh && psh !== "off" && psh !== "paid" && psh !== "ake" && psh !== "refresh") initConsecutive++;
            else break;
        }

        // 連続準夜数 (前月)
        var initConsJun = 0;
        for (var k = 0; k < 10; k++) {
            var pd = prevDays - k;
            if (pd < 1) break;
            var psh = prevShifts[s.id + "-" + pd] || "";
            if (psh === "junnya") initConsJun++;
            else break;
        }

        // シフト配列を作成
        var shArr = [];
        for (var d = 1; d <= days; d++) {
            shArr.push(shifts[s.id + "-" + d] || "");
        }

        // 公休日数チェック（off のみ = monthlyOff。paid/refresh は追加休みで別枠）
        // 夜勤専従は独自の公休制約のためスキップ
        if (wt !== "night_only") {
            var offCount = 0;
            for (var d = 0; d < days; d++) {
                if (shArr[d] === "off") offCount++;
            }
            var reqOff = parseInt(document.getElementById("monthlyOff").value) || 9;
            if (offCount !== reqOff) {
                errors.push(s.name + ": 公休" + offCount + "日(" + reqOff + "日必要)");
            }
        }

        // 夜勤回数チェック
        var nightCount = 0;
        for (var d = 0; d < days; d++) {
            if (wt === "2kohtai" && shArr[d] === "night2") nightCount++;
            if (wt === "3kohtai" && (shArr[d] === "junnya" || shArr[d] === "shinya")) nightCount++;
            if (wt === "night_only" && shArr[d] === "night2") nightCount++;
        }
        if (nightCount > maxNight) {
            errors.push(s.name + ": 夜勤" + nightCount + "回(上限" + maxNight + ") [ハード制約]");
        }
        var minNight = s.minNight !== undefined ? s.minNight : 0;
        if (minNight > 0 && nightCount < minNight) {
            errors.push(s.name + ": 夜勤" + nightCount + "回(下限" + minNight + ") [ハード制約]");
        }


        // 連続勤務チェック（6日連続禁止）
        var consecutive = initConsecutive;
        for (var d = 0; d < days; d++) {
            var sh = shArr[d];
            if (sh && sh !== "off" && sh !== "paid" && sh !== "ake" && sh !== "refresh") {
                consecutive++;
                if (consecutive >= 6) {
                    var startDay = (d + 1) - 5;  // 6連勤の開始日（当月）
                    softWarnings.push(s.name + ": " + (startDay < 1 ? "前月" : startDay + "日") + "～" + (d + 1) + "日 6日連続勤務 [300pt]");
                    break;
                }
            } else {
                consecutive = 0;
            }
        }


        // 連続休みチェック廃止（連休は減点不要）


        // 準夜連続3回以上チェック
        var consJun = initConsJun;
        for (var d = 0; d < days; d++) {
            if (shArr[d] === "junnya") {
                consJun++;
                if (consJun >= 3) {
                    var startDay = (d + 1) - 2;  // 3連続の開始日（当月）
                    errors.push(s.name + ": " + (startDay < 1 ? "前月" : startDay + "日") + "～" + (d + 1) + "日 準夜3連続(上限2) [ハード制約]");
                    break;
                }
            } else {
                consJun = 0;
            }
        }

        // 二交代ルール
        if (wt === "2kohtai") {
            for (var d = 0; d < days - 1; d++) {
                if (shArr[d] === "night2" && shArr[d + 1] !== "ake") {
                    errors.push(s.name + ": " + (d + 1) + "日夜勤の翌日が明けでない [ハード制約]");
                }
                if (shArr[d] === "ake" && d < days - 1 && shArr[d + 1] !== "off" && shArr[d + 1] !== "paid" && shArr[d + 1] !== "refresh") {
                    errors.push(s.name + ": " + (d + 1) + "日明けの翌日が休みでない [ハード制約]");
                }
            }
        }

        // 三交代ルール
        if (wt === "3kohtai") {
            for (var d = 0; d < days - 1; d++) {
                // 準夜の翌日は準夜か休み（refresh含む）
                if (shArr[d] === "junnya" && shArr[d + 1] !== "junnya" && shArr[d + 1] !== "off" && shArr[d + 1] !== "paid" && shArr[d + 1] !== "refresh") {
                    errors.push(s.name + ": " + (d + 1) + "日準夜の翌日が準夜/休みでない [ハード制約]");
                }
                // 準夜→深夜は禁止 (16:30終了→00:30開始 = 8時間 < 11時間)
                if (shArr[d] === "junnya" && shArr[d + 1] === "shinya") {
                    errors.push(s.name + ": " + (d + 1) + "日準夜→深夜は禁止 [ハード制約]");
                }
                // 遅出→深夜は禁止 (21:00終了→00:30開始 = 3.5時間 < 11時間)
                if (shArr[d] === "late" && shArr[d + 1] === "shinya") {
                    errors.push(s.name + ": " + (d + 1) + "日遅出→深夜は禁止(インターバル不足) [ハード制約]");
                }
                // 深夜→深夜（ソフト制約: night_interval_penalty 20pt）
                if (shArr[d] === "shinya" && shArr[d + 1] === "shinya") {
                    softWarnings.push(s.name + ": " + (d + 1) + "～" + (d + 2) + "日 深夜連続 [20pt]");
                }
                // 準夜の翌日に日勤/早出（準夜翌日ハード制約の一部）
                if (shArr[d] === "junnya" && shArr[d + 1] === "day") {
                    errors.push(s.name + ": " + (d + 1) + "日準夜の翌日に日勤 [ハード制約]");
                }
                // 深夜の翌日に準夜/日勤/遅出（ソフト制約: shinya_off_penalty）
                if (shArr[d] === "shinya" && (shArr[d + 1] === "junnya" || shArr[d + 1] === "day" || shArr[d + 1] === "late")) {
                    var rc = staffRefreshDays[s.id] || 0;
                    var pt = shinyaOffPt(rc);
                    softWarnings.push(s.name + ": " + (d + 2) + "日深夜の翌日に" + (ABBR[shArr[d+1]] || shArr[d+1]) + " [" + pt + "pt]");
                }
                // 日勤→深夜（ソフト制約: day_shinya_penalty 25pt、インターバル約7時間）
                // ※遅出→深夜はハード制約で既に検出済み
                if (shArr[d] === "day" && shArr[d + 1] === "shinya") {
                    softWarnings.push(s.name + ": " + (d + 1) + "→" + (d + 2) + "日 " + (ABBR[shArr[d]] || shArr[d]) + "→深夜(インターバル短) [25pt]");
                }
                // 準夜→休→深夜パターン（ソフト制約: junnya_off_shinya_penalty）
                if (d < days - 2 && shArr[d] === "junnya"
                    && (shArr[d + 1] === "off" || shArr[d + 1] === "paid" || shArr[d + 1] === "refresh")
                    && shArr[d + 2] === "shinya") {
                    var rc = staffRefreshDays[s.id] || 0;
                    var basePt = junnyaOffShinyaPt(rc);
                    softWarnings.push(s.name + ": " + (d + 1) + "～" + (d + 3) + "日 準夜→休→深夜(体内リズム切替) [" + basePt + "pt]");
                }
            }
            // 夜勤3連続禁止
            for (var d = 0; d < days - 2; d++) {
                var n1 = shArr[d] === "junnya" || shArr[d] === "shinya";
                var n2 = shArr[d + 1] === "junnya" || shArr[d + 1] === "shinya";
                var n3 = shArr[d + 2] === "junnya" || shArr[d + 2] === "shinya";
                if (n1 && n2 && n3) {
                    errors.push(s.name + ": " + (d + 1) + "日～ 夜勤3連続 [ハード制約]");
                    break;
                }
            }
        }

        // 準深バランスチェック（三交代のみ: ソルバーC6準拠）
        if (wt === "3kohtai") {
            var pJun = 0, pShin = 0;
            for (var d = 0; d < days; d++) {
                if (shArr[d] === "junnya") pJun++;
                if (shArr[d] === "shinya") pShin++;
            }
            var jsDiff = Math.abs(pJun - pShin);
            if (jsDiff >= 3) {
                softWarnings.push(s.name + ": 準夜" + pJun + "回/深夜" + pShin + "回 (差" + jsDiff + ") 準深バランス [" + (jsDiff * 10) + "pt]");
            }
        }

        // 希望チェック（off/refresh希望と競合する非off希望はスキップ - solver側と同じoff優先ロジック）
        var offWishDays = {};
        for (var wi = 0; wi < wishes.length; wi++) {
            var w = wishes[wi];
            if (w.staffId !== s.id) continue;
            if (w.type === "assign" && (w.shift === "off" || w.shift === "refresh")) {
                var wdays = w.days || [];
                for (var wdi = 0; wdi < wdays.length; wdi++) offWishDays[wdays[wdi]] = true;
            }
        }
        for (var wi = 0; wi < wishes.length; wi++) {
            var w = wishes[wi];
            if (w.staffId !== s.id) continue;
            var wdays = w.days || [];
            for (var wdi = 0; wdi < wdays.length; wdi++) {
                var wd = wdays[wdi];
                if (wd < 1 || wd > days) continue;
                // 同じ日にoff/refresh希望がある場合、非off希望はスキップ
                if (w.type === "assign" && w.shift !== "off" && w.shift !== "refresh" && offWishDays[wd]) continue;
                var actual = shArr[wd - 1];
                if (w.type === "assign" && actual !== w.shift) {
                    warnings.push(s.name + ": " + wd + "日 希望(" + (ABBR[w.shift] || w.shift) + ")→実際(" + (ABBR[actual] || actual || "未") + ")");
                }
            }
        }
    }

    // 日別の人員チェック
    for (var d = 1; d <= days; d++) {
        var dayCount = 0, junnyaCount = 0, shinyaCount = 0, lateCount = 0;
        for (var si = 0; si < staff.length; si++) {
            var sh = shifts[staff[si].id + "-" + d] || "";
            if (sh === "day" || sh === "late") dayCount++;
            if (sh === "night2" || sh === "junnya") junnyaCount++;
            if (sh === "ake" || sh === "shinya") shinyaCount++;
            if (sh === "late") lateCount++;
        }
        var dt = new Date(Y, M - 1, d);
        var weekday = dt.getDay(); // 0=Sun,1=Mon,...6=Sat
        var isHol = weekday === 0 || weekday === 6 || HOLIDAYS[Y + "-" + M + "-" + d];
        var cfgDayWeekday = parseInt(document.getElementById("reqDayWeekday").value) || 7;
        var cfgDayHoliday = parseInt(document.getElementById("reqDayHoliday").value) || 5;
        var reqDay = cfgDayWeekday;
        if (weekday === 0 || HOLIDAYS[Y + "-" + M + "-" + d]) {
            reqDay = cfgDayHoliday;
        } else if (W === "2") {
            // 二病棟: 月金=基準, 木=基準+1, 火水土=基準-1
            var jsDay = weekday; // 0=Sun,1=Mon,2=Tue,3=Wed,4=Thu,5=Fri,6=Sat
            if (jsDay === 1 || jsDay === 5) { /* 月金: 基準 */ }
            else if (jsDay === 4) reqDay += 1; // 木: 基準+1
            else if (jsDay === 2 || jsDay === 3 || jsDay === 6) reqDay -= 1; // 火水土: 基準-1
        } else if (W === "1") {
            // 一病棟: 月木=基準, 水金=基準-1, 火土=基準-2
            var jsDay = weekday;
            if (jsDay === 1 || jsDay === 4) { /* 月木: 基準 */ }
            else if (jsDay === 3 || jsDay === 5) reqDay -= 1; // 水金: -1
            else if (jsDay === 2 || jsDay === 6) reqDay -= 2; // 火土: -2
        } else {
            // 他病棟: 水=-1
            if (weekday === 3) reqDay -= 1; // Wed
        }
        var cfgJunnya = parseInt(document.getElementById("reqJunnya").value) || 2;
        var cfgShinya = parseInt(document.getElementById("reqShinya").value) || 2;
        var cfgLate = (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("reqLate").value) || 1);
        if (dayCount < reqDay) softWarnings.push(d + "日: 日勤" + dayCount + "名(目標" + reqDay + ") [人員不足]");
        if (junnyaCount < cfgJunnya) errors.push(d + "日: 準夜帯" + junnyaCount + "名(必要" + cfgJunnya + ") [ハード制約]");
        if (shinyaCount < cfgShinya) errors.push(d + "日: 深夜帯" + shinyaCount + "名(必要" + cfgShinya + ") [ハード制約]");
        if (cfgLate > 0 && lateCount < cfgLate) errors.push(d + "日: 遅出" + lateCount + "名(必要" + cfgLate + ") [ハード制約]");
    }

    // 結果表示
    if (errors.length === 0 && softWarnings.length === 0 && warnings.length === 0 && policyWarnings.length === 0) {
        log.innerHTML = "<div class='log-success'>✓ すべての制約を満たしています</div>";
    } else {
        var html = "";
        if (errors.length > 0) {
            html += "<div class='log-error'>✗ ハード制約違反 " + errors.length + "件:</div>";
            for (var i = 0; i < errors.length; i++) {
                html += "<div class='log-error'>  " + errors[i] + "</div>";
            }
        }
        if (softWarnings.length > 0) {
            var totalPenalty = 0;
            for (var i = 0; i < softWarnings.length; i++) {
                var m = softWarnings[i].match(/\[(\d+)pt\]/);
                if (m) totalPenalty += parseInt(m[1], 10);
            }
            html += "<div style='color:#b45309'>⚠ ソフト制約違反 " + softWarnings.length + "件（総ペナルティ: " + totalPenalty + "pt）:</div>";
            for (var i = 0; i < softWarnings.length; i++) {
                html += "<div style='color:#b45309'>  " + softWarnings[i] + "</div>";
            }
        }
        if (warnings.length > 0) {
            html += "<div class='log-info'>⚠ 希望未反映 " + warnings.length + "件:</div>";
            for (var i = 0; i < warnings.length; i++) {
                html += "<div class='log-info'>  " + warnings[i] + "</div>";
            }
        }
        if (policyWarnings.length > 0) {
            html += "<div style='color:var(--orange)'>📋 ルール確認 " + policyWarnings.length + "件:</div>";
            for (var i = 0; i < policyWarnings.length; i++) {
                html += "<div style='color:var(--orange)'>  " + policyWarnings[i] + "</div>";
            }
        }
        log.innerHTML = html;
    }

    // ========== 公平性メトリクス計算・表示 ==========
    calculateFairnessMetrics(staff, shifts, days, Y, M);

    var result = { errors: errors, softWarnings: softWarnings, warnings: warnings };
    window._lastCheckResult = result;
    return result;
}

function calculateFairnessMetrics(staff, shifts, days, year, month) {
    // ジニ係数計算
    function gini(arr) {
        if (!arr || arr.length < 2) return 0;
        arr = arr.slice().sort(function (a, b) { return a - b; });
        var n = arr.length;
        var total = arr.reduce(function (a, b) { return a + b; }, 0);
        if (total === 0) return 0;
        var sum = 0;
        for (var i = 0; i < n; i++) {
            sum += (2 * (i + 1) - n - 1) * arr[i];
        }
        return sum / (n * total);
    }

    // 変動係数計算
    function cv(arr) {
        if (!arr || arr.length < 2) return 0;
        var mean = arr.reduce(function (a, b) { return a + b; }, 0) / arr.length;
        if (mean === 0) return 0;
        var variance = arr.reduce(function (a, b) { return a + (b - mean) * (b - mean); }, 0) / arr.length;
        return Math.sqrt(variance) / mean;
    }

    var nightCounts = [], weekendCounts = [], lateCounts = [], consMaxes = [];
    var nightIntervals = [], weekendOffRatios = [], consNightMaxes = [];
    var burdenScores = [];

    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        if (s.workType === "fixed") continue;
        var wt = s.workType || "2kohtai";
        var nightCount = 0, akeCount = 0, lateCount = 0, weekendWork = 0, weekendTotal = 0;
        var consMax = 0, cons = 0, consNightMax = 0, consNight = 0;
        var lastNightDay = -99;
        var nightDays = [];

        for (var d = 1; d <= days; d++) {
            var sh = shifts[s.id + "-" + d] || "";
            var dt = new Date(year, month - 1, d);
            var wd = dt.getDay();
            var isWeekend = (wd === 0 || wd === 6 || HOLIDAYS[year + "-" + month + "-" + d]);

            // 夜勤カウント（night2/junnya/shinyaを夜勤入りとしてカウント）
            if (["night2", "junnya", "shinya"].indexOf(sh) >= 0) {
                nightCount++;
                nightDays.push(d);
                consNight++;
                if (consNight > consNightMax) consNightMax = consNight;
            } else {
                consNight = 0;
            }
            // akeカウント（当月内のake日数を別途カウント）
            if (sh === "ake") akeCount++;

            // 遅出カウント
            if (sh === "late") lateCount++;

            // 週末
            if (isWeekend) {
                weekendTotal++;
                if (sh && ["off", "paid", "refresh"].indexOf(sh) < 0) weekendWork++;
            }

            // 連続勤務（akeは夜勤の一部であり連勤を途切れさせない）
            if (sh && ["off", "paid", "refresh"].indexOf(sh) < 0) {
                cons++;
                if (cons > consMax) consMax = cons;
            } else {
                cons = 0;
            }
        }

        // 夜勤pt（二交代: night2+ake実日数, 三交代: junnya+shinya実日数）
        // ×2ではなく実際のake日数を使用（月末night2のakeは翌月のため）
        var nightPt = (wt === "2kohtai" || wt === "night_only") ? nightCount + akeCount : nightCount;

        // 夜勤間隔計算
        var avgInterval = 0;
        if (nightDays.length >= 2) {
            var intervals = [];
            for (var i = 1; i < nightDays.length; i++) {
                intervals.push(nightDays[i] - nightDays[i - 1]);
            }
            avgInterval = intervals.reduce(function (a, b) { return a + b; }, 0) / intervals.length;
        }

        // 週末休み率
        var weekendOffRate = weekendTotal > 0 ? (weekendTotal - weekendWork) / weekendTotal : 1;

        // 身体的負担スコア (0-100, 低いほど良い)
        var burdenScore = 0;
        burdenScore += consMax * 8;           // 連続勤務 (5日→40点)
        burdenScore += nightPt * 2;           // 夜勤pt (二交代5回=10pt→20点, 三交代10回=10pt→20点)
        burdenScore += consNightMax * 15;     // 連続夜勤 (2連続→30点)
        burdenScore += (1 - weekendOffRate) * 20; // 週末出勤率
        burdenScore = Math.min(100, burdenScore);

        if (wt !== "day_only" && wt !== "fixed" && wt !== "night_only") {
            nightCounts.push(nightPt);
            lateCounts.push(lateCount);
            nightIntervals.push(avgInterval);
            consNightMaxes.push(consNightMax);
            weekendCounts.push(weekendWork);
            consMaxes.push(consMax);
        }
        weekendOffRatios.push(weekendOffRate);
        burdenScores.push(burdenScore);
    }

    // 希望達成率（現在病棟の職員のみ、off/refresh優先で競合する非off希望はスキップ）
    var wishTotal = 0, wishViolated = 0;
    var wk = year + "-" + month;
    var wishes = D.wishes[wk] || [];
    // 現在病棟の職員IDセットを作成
    var staffIds = new Set();
    for (var si = 0; si < staff.length; si++) {
        staffIds.add(staff[si].id);
    }
    // 職員別off/refresh希望日マップ
    var staffOffDays1 = {};
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (!staffIds.has(w.staffId)) continue;
        if (w.type === "assign" && (w.shift === "off" || w.shift === "refresh")) {
            if (!staffOffDays1[w.staffId]) staffOffDays1[w.staffId] = {};
            var wds = w.days || [];
            for (var wdi = 0; wdi < wds.length; wdi++) staffOffDays1[w.staffId][wds[wdi]] = true;
        }
    }
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (!staffIds.has(w.staffId)) continue;
        var wdays = w.days || [];
        for (var wdi = 0; wdi < wdays.length; wdi++) {
            var wd = wdays[wdi];
            if (wd < 1 || wd > days) continue;
            if (w.type === "assign" && w.shift !== "off" && w.shift !== "refresh" && staffOffDays1[w.staffId] && staffOffDays1[w.staffId][wd]) continue;
            wishTotal++;
            var actual = shifts[w.staffId + "-" + wd] || "";
            if (w.type === "assign" && actual !== w.shift) wishViolated++;
            if (w.type === "avoid" && actual === w.shift) wishViolated++;
        }
    }
    var wishSatisfaction = wishTotal > 0 ? ((wishTotal - wishViolated) / wishTotal * 100) : 100;

    // メトリクス計算
    var nightGini = gini(nightCounts) || 0;
    var weekendGini = gini(weekendCounts) || 0;
    var lateGini = gini(lateCounts) || 0;
    var avgConsMax = consMaxes.length ? consMaxes.reduce(function (a, b) { return a + b; }, 0) / consMaxes.length : 0;
    var maxConsNight = consNightMaxes.length ? Math.max.apply(null, consNightMaxes) : 0;
    var avgNightInterval = nightIntervals.length ? nightIntervals.reduce(function (a, b) { return a + b; }, 0) / nightIntervals.length : 0;
    var avgWeekendOff = weekendOffRatios.length ? weekendOffRatios.reduce(function (a, b) { return a + b; }, 0) / weekendOffRatios.length * 100 : 100;

    // 夜勤ptの範囲（二交代night2×2, 三交代junnya/shinya×1）
    var nightMin = nightCounts.length ? Math.min.apply(null, nightCounts) : 0;
    var nightMax = nightCounts.length ? Math.max.apply(null, nightCounts) : 0;
    var lateMin = lateCounts.length ? Math.min.apply(null, lateCounts) : 0;
    var lateMax = lateCounts.length ? Math.max.apply(null, lateCounts) : 0;

    // 評価関数
    function evalGini(g) {
        g = parseFloat(g);
        if (g < 0.1) return '<span style="color:#10b981">優秀</span>';
        if (g < 0.2) return '<span style="color:#3b82f6">良好</span>';
        if (g < 0.3) return '<span style="color:#f59e0b">普通</span>';
        return '<span style="color:#ef4444">要改善</span>';
    }

    // 表示
    var panel = document.getElementById("fairnessMetrics");
    var grid = document.getElementById("metricsGrid");
    var contextEl = document.getElementById("metricsContext");
    if (panel && grid) {
        panel.style.display = "block";

        // コンテキスト情報（対象月・病棟・案名）
        if (contextEl) {
            var wardName = W === "1" ? "一病棟" : W === "2" ? "二病棟" : "三病棟";
            var statusDetail = document.getElementById("shiftStatusDetail");
            var draftInfo = statusDetail ? statusDetail.textContent : "";
            contextEl.textContent = year + "年" + month + "月 / " + wardName + " / " + draftInfo;
        }

        var html = '';

        // 公平性指標（ジニ係数）
        html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #8b5cf6"><b>🎯 夜勤</b><br>Gini: ' + nightGini.toFixed(4) + ' ' + evalGini(nightGini) + '<br>範囲: ' + nightMin + '~' + nightMax + 'pt</div>';
        html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #3b82f6"><b>📅 週末</b><br>Gini: ' + weekendGini.toFixed(4) + ' ' + evalGini(weekendGini) + '<br>休率: ' + avgWeekendOff.toFixed(0) + '%</div>';
        if (W === "2") {
            html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #f59e0b"><b>🌙 遅出</b><br>Gini: ' + lateGini.toFixed(4) + ' ' + evalGini(lateGini) + '<br>範囲: ' + lateMin + '~' + lateMax + '回</div>';
        }

        // 負担指標
        html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #ec4899"><b>📆 連勤</b><br>平均: ' + avgConsMax.toFixed(1) + '日<br>最大: ' + Math.max.apply(null, consMaxes) + '日</div>';
        html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #14b8a6"><b>🌃 夜勤間隔</b><br>平均: ' + avgNightInterval.toFixed(1) + '日<br>連続夜勤: ' + maxConsNight + '回</div>';

        // 希望達成
        var wishMet = wishTotal - wishViolated;
        html += '<div style="background:var(--card);padding:.6rem;border-radius:6px;border-left:3px solid #6366f1"><b>✨ 希望</b><br>達成率: ' + wishSatisfaction.toFixed(0) + '%<br><span style="font-size:.75rem">達成' + wishMet + '件 / 登録' + wishTotal + '件</span></div>';

        grid.innerHTML = html;

        // ===== 個人負荷スコア計算・表示 (v2カテゴリ対応) =====
        // 希望データをキー形式に変換
        var wishMap = {};
        var currentWardStaff = new Set();
        for (var si = 0; si < staff.length; si++) {
            currentWardStaff.add(staff[si].id);
        }
        for (var wi = 0; wi < wishes.length; wi++) {
            var w = wishes[wi];
            if (!currentWardStaff.has(w.staffId)) continue;
            var wdays = w.days || [];
            for (var wdi = 0; wdi < wdays.length; wdi++) {
                var wd = wdays[wdi];
                if (w.type === "assign") {
                    wishMap[w.staffId + "-" + wd] = w.shift;
                }
            }
        }

        var personalScores = {};
        var personalScoreValues = [];
        for (var si = 0; si < staff.length; si++) {
            var s = staff[si];
            var wt = s.workType || "2kohtai";
            if (wt === "fixed" || wt === "day_only") continue;

            var ps = calculatePersonalLoad(s.id, shifts, days, wt, year, month, wishMap, getPrevMonthStaffData(s.id, year, month, W));
            personalScores[s.id] = {
                name: s.name,
                score: ps.score,
                penalties: ps.penalties,
                issues: getPersonalIssues(ps)
            };
            personalScoreValues.push(ps.score);
        }

        // 個人負荷スコアを別パネルに表示
        var personalPanel = document.getElementById("personalLoadPanel");
        var personalContent = document.getElementById("personalLoadContent");
        var personalContext = document.getElementById("personalLoadContext");

        if (personalScoreValues.length > 0 && personalPanel && personalContent) {
            personalPanel.style.display = "block";

            // コンテキスト情報
            if (personalContext) {
                var wardName = W === "1" ? "一病棟" : W === "2" ? "二病棟" : "三病棟";
                var statusDetail = document.getElementById("shiftStatusDetail");
                var draftInfo = statusDetail ? statusDetail.textContent : "";
                personalContext.textContent = year + "年" + month + "月 / " + wardName + " / " + draftInfo;
            }

            var maxPersonal = Math.max.apply(null, personalScoreValues);
            var avgPersonal = personalScoreValues.reduce(function(a, b) { return a + b; }, 0) / personalScoreValues.length;

            // ワースト3（ペナルティ多い順）
            var worstStaff = Object.keys(personalScores)
                .map(function(id) { return { id: id, name: personalScores[id].name, score: personalScores[id].score, penalties: personalScores[id].penalties, issues: personalScores[id].issues }; })
                .sort(function(a, b) { return b.score - a.score; })
                .slice(0, 3);

            var personalHtml = '';

            // サマリー
            personalHtml += '<div style="display:flex;gap:1.5rem;margin-bottom:1rem;flex-wrap:wrap">';
            personalHtml += '<div style="background:rgba(255,255,255,0.1);padding:.6rem 1rem;border-radius:6px"><span style="font-size:.8rem;opacity:.7">平均ペナルティ</span><br><strong style="font-size:1.3rem">' + avgPersonal.toFixed(1) + '</strong><span style="font-size:.8rem">件</span></div>';
            personalHtml += '<div style="background:rgba(239,68,68,0.2);padding:.6rem 1rem;border-radius:6px"><span style="font-size:.8rem;opacity:.7">最多ペナルティ</span><br><strong style="font-size:1.3rem;color:#fca5a5">' + maxPersonal + '</strong><span style="font-size:.8rem">件</span></div>';
            personalHtml += '</div>';

            // ワースト3（要注意者）— ペナルティ0のスタッフは除外
            var worstWithPenalties = worstStaff.filter(function(ws) { return ws.score > 0; });
            if (worstWithPenalties.length > 0) {
                personalHtml += '<div style="margin-bottom:1rem"><div style="font-weight:600;color:#fca5a5;margin-bottom:.5rem">要注意スタッフ</div>';
                personalHtml += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.5rem">';
                for (var wi = 0; wi < worstWithPenalties.length; wi++) {
                    var ws = worstWithPenalties[wi];
                    var color = ws.score <= 3 ? "#fbbf24" : "#f87171";
                    var bgColor = ws.score <= 3 ? "rgba(251,191,36,0.15)" : "rgba(248,113,113,0.15)";
                    personalHtml += '<div style="border-left:3px solid ' + color + ';padding:.5rem .8rem;background:' + bgColor + ';border-radius:4px">';
                    personalHtml += '<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem">';
                    personalHtml += '<strong>' + ws.name + '</strong> <span style="color:' + color + ';font-weight:bold;font-size:1.1rem">' + ws.score + '件</span>';
                    personalHtml += ' ' + renderPenaltySummary(ws.penalties);
                    personalHtml += '</div>';
                    if (ws.issues.length > 0) {
                        personalHtml += '<div style="font-size:.8rem;color:#fca5a5">' + ws.issues.join(" / ") + '</div>';
                    }
                    personalHtml += '</div>';
                }
                personalHtml += '</div></div>';
            }

            // 全員のスコア一覧（ペナルティ多い順）
            personalHtml += '<div><div style="font-weight:600;margin-bottom:.5rem;opacity:.8">全スタッフ</div>';
            personalHtml += '<div style="display:flex;flex-wrap:wrap;gap:.4rem;font-size:.8rem">';
            var sortedPersonal = Object.keys(personalScores)
                .map(function(id) { return { name: personalScores[id].name, score: personalScores[id].score, penalties: personalScores[id].penalties }; })
                .sort(function(a, b) { return b.score - a.score; });
            for (var pi = 0; pi < sortedPersonal.length; pi++) {
                var sp = sortedPersonal[pi];
                var bgColor = sp.score === 0 ? "rgba(16,185,129,0.25)" : sp.score <= 3 ? "rgba(251,191,36,0.25)" : "rgba(248,113,113,0.25)";
                var textColor = sp.score === 0 ? "#6ee7b7" : sp.score <= 3 ? "#fcd34d" : "#fca5a5";
                personalHtml += '<div style="background:' + bgColor + ';padding:.3rem .6rem;border-radius:4px;display:flex;align-items:center;gap:.4rem">';
                personalHtml += '<span style="color:' + textColor + '">' + sp.name + ' <strong>' + sp.score + '</strong></span>';
                personalHtml += ' ' + renderPenaltySummary(sp.penalties);
                personalHtml += '</div>';
            }
            personalHtml += '</div></div>';

            personalContent.innerHTML = personalHtml;
        } else if (personalPanel) {
            personalPanel.style.display = "none";
        }
    }
}

// ========== シフト案バージョン管理 ==========
function saveCurrentVersion() {
    var sk = Y + "-" + M + "-" + W;
    var shifts = D.shifts[sk] || {};
    if (Object.keys(shifts).length === 0) {
        alert("シフトがありません");
        return;
    }

    if (!D.shiftVersions) D.shiftVersions = {};
    if (!D.shiftVersions[sk]) D.shiftVersions[sk] = { versions: [], nextId: 1 };

    var vk = D.shiftVersions[sk];
    var metrics = calculateVersionMetrics(shifts);

    var version = {
        id: vk.nextId++,
        name: "案" + (vk.versions.length + 1),
        timestamp: new Date().toISOString().slice(0, 19),
        shifts: JSON.parse(JSON.stringify(shifts)),
        metrics: metrics
    };

    vk.versions.push(version);
    save();
    renderVersions();
}

// Wrapper function for calculateVersionMetrics (uses global Y, M, W)
function calculateMetrics(year, month, shifts) {
    return calculateVersionMetrics(shifts);
}

// ========== 個人負荷スコア計算（obj準拠・Python shift_quality.py と同一ロジック） ==========
// ペナルティ項目（shift_quality.py の PENALTY_KEYS と同一、good_rotation除外）
var PENALTY_KEYS = [
    "consec_5", "consec_6", "night_interval_close",
    "shinya_no_rest", "scattered_night", "junnya_off_shinya",
    "day_to_shinya", "kibou_night", "junnya_shinya_balance"
];

// 前月データからスタッフ別の引き継ぎ情報を取得
function getPrevMonthStaffData(staffId, year, month, wardId) {
    var prevY = year, prevM = month - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var prevDays = new Date(prevY, prevM, 0).getDate();
    var prevSk = prevY + "-" + prevM + "-" + wardId;
    var prevShifts = D.shifts[prevSk] || {};

    var lastDay = prevShifts[staffId + "-" + prevDays] || "";
    var secondLastDay = prevDays >= 2 ? (prevShifts[staffId + "-" + (prevDays - 1)] || "") : "";

    // 前月末からの連勤数
    var consecutiveWork = 0;
    for (var k = 0; k < 10; k++) {
        var pd = prevDays - k;
        if (pd < 1) break;
        var psh = prevShifts[staffId + "-" + pd] || "";
        if (psh && psh !== "off" && psh !== "paid" && psh !== "ake" && psh !== "refresh") consecutiveWork++;
        else break;
    }

    return { lastDay: lastDay, secondLastDay: secondLastDay, consecutiveWork: consecutiveWork };
}

function calculatePersonalLoad(staffId, shifts, numDays, workType, year, month, wishes, prevData) {
    var REST_TYPES = ["off", "paid", "refresh"];
    var NIGHT_TYPES = ["night2", "junnya", "shinya"];

    var shiftList = [];
    var junyaCount = 0, shinyaCount = 0;
    var nightDays = [];  // 0-indexed

    for (var d = 1; d <= numDays; d++) {
        var sh = shifts[staffId + "-" + d] || "";
        shiftList.push(sh);
        if (NIGHT_TYPES.indexOf(sh) >= 0) {
            nightDays.push(d - 1);
            if (sh === "junnya") junyaCount++;
            if (sh === "shinya") shinyaCount++;
        }
    }

    // ペナルティ件数
    var p = {
        consec_5: 0, consec_6: 0, night_interval_close: 0,
        shinya_no_rest: 0, scattered_night: 0, junnya_off_shinya: 0,
        day_to_shinya: 0, kibou_night: 0, junnya_shinya_balance: 0,
        good_rotation: 0
    };

    // 前月データ
    var prevLast = (prevData && prevData.lastDay) || "";
    var prevSecond = (prevData && prevData.secondLastDay) || "";
    var prevWork = (prevData && prevData.consecutiveWork) || 0;

    // 5連勤/6連勤を窓で検出
    for (var d = 0; d <= numDays - 5; d++) {
        var all5 = true;
        for (var i = 0; i < 5; i++) {
            if (!shiftList[d+i] || REST_TYPES.indexOf(shiftList[d+i]) >= 0) { all5 = false; break; }
        }
        if (all5) p.consec_5++;
    }
    for (var d = 0; d <= numDays - 6; d++) {
        var all6 = true;
        for (var i = 0; i < 6; i++) {
            if (!shiftList[d+i] || REST_TYPES.indexOf(shiftList[d+i]) >= 0) { all6 = false; break; }
        }
        if (all6) p.consec_6++;
    }
    // 月またぎ: 前月連勤 + 当月冒頭で5連勤/6連勤に達するケース
    if (prevWork >= 1) {
        var dn5 = 5 - prevWork;
        if (dn5 > 0 && dn5 <= numDays) {
            var ok5 = true;
            for (var i = 0; i < dn5; i++) { if (!shiftList[i] || REST_TYPES.indexOf(shiftList[i]) >= 0) { ok5 = false; break; } }
            if (ok5) p.consec_5++;
        }
        var dn6 = 6 - prevWork;
        if (dn6 > 0 && dn6 <= numDays) {
            var ok6 = true;
            for (var i = 0; i < dn6; i++) { if (!shiftList[i] || REST_TYPES.indexOf(shiftList[i]) >= 0) { ok6 = false; break; } }
            if (ok6) p.consec_6++;
        }
    }

    // 三交代専用
    if (workType === "3kohtai") {
        for (var d = 0; d < numDays - 1; d++) {
            // 深夜後無休
            if (shiftList[d] === "shinya") {
                var next = shiftList[d + 1];
                if (REST_TYPES.indexOf(next) < 0 && next !== "shinya") p.shinya_no_rest++;
            }
            // 日深転換
            if ((shiftList[d] === "day" || shiftList[d] === "late") && shiftList[d + 1] === "shinya") p.day_to_shinya++;
        }
        // 月またぎ: day/late(前月末)→shinya(day0)
        if ((prevLast === "day" || prevLast === "late") && shiftList[0] === "shinya") p.day_to_shinya++;

        for (var d = 0; d < numDays - 2; d++) {
            // 散発夜勤: 深夜→休→深夜
            if (shiftList[d] === "shinya" && REST_TYPES.indexOf(shiftList[d+1]) >= 0 && shiftList[d+2] === "shinya") p.scattered_night++;
            // 準深切替: 準夜→休→深夜
            if (shiftList[d] === "junnya" && REST_TYPES.indexOf(shiftList[d+1]) >= 0 && shiftList[d+2] === "shinya") p.junnya_off_shinya++;
            // 好ローテ: 深夜→休→準夜, 深夜→準夜→休
            if (shiftList[d] === "shinya" && REST_TYPES.indexOf(shiftList[d+1]) >= 0 && shiftList[d+2] === "junnya") p.good_rotation++;
            if (shiftList[d] === "shinya" && shiftList[d+1] === "junnya" && REST_TYPES.indexOf(shiftList[d+2]) >= 0) p.good_rotation++;
        }
        // 月またぎ: shinya(前月末)→rest(day0)→shinya(day1)
        if (prevLast === "shinya" && numDays >= 2 && REST_TYPES.indexOf(shiftList[0]) >= 0 && shiftList[1] === "shinya") p.scattered_night++;
        // 月またぎ: junnya(前月末)→rest(day0)→shinya(day1)
        if (prevLast === "junnya" && numDays >= 2 && REST_TYPES.indexOf(shiftList[0]) >= 0 && shiftList[1] === "shinya") p.junnya_off_shinya++;
        // 月またぎ: shinya(前月末)→rest(day0)→junnya(day1) 好ローテ
        if (prevLast === "shinya" && numDays >= 2 && REST_TYPES.indexOf(shiftList[0]) >= 0 && shiftList[1] === "junnya") p.good_rotation++;

        // 準深バランス
        p.junnya_shinya_balance = Math.abs(junyaCount - shinyaCount);
    }

    // 夜勤間隔（2交代/3交代共通）
    // 月またぎ: 前月末の夜勤との間隔チェック
    if (workType === "2kohtai") {
        if (prevLast === "night2") {
            for (var ni = 0; ni < nightDays.length; ni++) {
                var gap = nightDays[ni] + 1;
                if (gap >= 2 && gap <= 3) p.night_interval_close++;
            }
        } else if (prevSecond === "night2") {
            for (var ni = 0; ni < nightDays.length; ni++) {
                var gap = nightDays[ni] + 2;
                if (gap >= 2 && gap <= 3) p.night_interval_close++;
            }
        }
    } else if (workType === "3kohtai") {
        if (prevLast === "shinya" && shiftList[0] === "shinya") p.night_interval_close++;
    }
    // 当月内の間隔チェック
    for (var i = 1; i < nightDays.length; i++) {
        var gap = nightDays[i] - nightDays[i - 1];
        if (gap >= 2 && gap <= 3) p.night_interval_close++;
    }

    // 希望休前後の夜勤
    if (wishes && typeof wishes === "object") {
        for (var key in wishes) {
            if (key.indexOf(staffId + "-") !== 0) continue;
            var wType = wishes[key];
            if (wType !== "off" && wType !== "paid" && wType !== "refresh") continue;
            var offDay = parseInt(key.split("-")[1]);
            var dIdx = offDay - 1;
            // 月またぎ: day0が希望休で前月末がjunnya
            if (dIdx === 0 && prevLast === "junnya") p.kibou_night++;
            else if (dIdx > 0 && shiftList[dIdx - 1] === "junnya") p.kibou_night++;
            if (dIdx < numDays - 1 && shiftList[dIdx + 1] === "shinya") p.kibou_night++;
        }
    }

    // スコア計算（ペナルティ件数合計、0=最良、Python側と同一）
    var score = 0;
    for (var ki = 0; ki < PENALTY_KEYS.length; ki++) {
        score += p[PENALTY_KEYS[ki]] || 0;
    }

    // 問題日の収集（シフト表のアンダーライン表示用）
    var nightIntervalIssueDays = [];
    // 月またぎ: 前月末の夜勤が近い場合、当月冒頭をマーク
    if (workType === "2kohtai" && prevLast === "night2") {
        for (var ni = 0; ni < nightDays.length; ni++) {
            if (nightDays[ni] + 1 >= 2 && nightDays[ni] + 1 <= 3) nightIntervalIssueDays.push(nightDays[ni] + 1);
        }
    } else if (workType === "3kohtai" && prevLast === "shinya" && shiftList[0] === "shinya") {
        nightIntervalIssueDays.push(1);
    }
    for (var i = 1; i < nightDays.length; i++) {
        var gap = nightDays[i] - nightDays[i - 1];
        if (gap >= 2 && gap <= 3) {
            nightIntervalIssueDays.push(nightDays[i - 1] + 1);  // 1-indexed
            nightIntervalIssueDays.push(nightDays[i] + 1);
        }
    }

    return {
        score: score,
        penalties: p,
        issueDays: {
            nightInterval: nightIntervalIssueDays,
            hardPatterns: [],
            noConsecutiveRest: false
        }
    };
}

function getPersonalIssues(result) {
    var issues = [];
    var p = result.penalties || {};

    if (p.consec_6 > 0) issues.push("6連勤" + p.consec_6);
    else if (p.consec_5 > 0) issues.push("5連勤" + p.consec_5);
    if (p.night_interval_close > 0) issues.push("夜勤近接" + p.night_interval_close);
    if (p.shinya_no_rest > 0) issues.push("深夜後無休" + p.shinya_no_rest);
    if (p.scattered_night > 0) issues.push("散発夜勤" + p.scattered_night);
    if (p.day_to_shinya > 0) issues.push("日深転換" + p.day_to_shinya);
    if (p.junnya_off_shinya > 0) issues.push("準深切替" + p.junnya_off_shinya);
    if (p.kibou_night > 0) issues.push("希望前後夜勤" + p.kibou_night);
    if (p.junnya_shinya_balance >= 3) issues.push("準深差" + p.junnya_shinya_balance);

    return issues;
}

// ペナルティ件数のコンパクト表示
function renderPenaltySummary(penalties) {
    var items = [];
    if (penalties.consec_5) items.push("5連" + penalties.consec_5);
    if (penalties.consec_6) items.push("6連" + penalties.consec_6);
    if (penalties.night_interval_close) items.push("近接" + penalties.night_interval_close);
    if (penalties.shinya_no_rest) items.push("無休" + penalties.shinya_no_rest);
    if (penalties.scattered_night) items.push("散発" + penalties.scattered_night);
    if (penalties.junnya_off_shinya) items.push("準深" + penalties.junnya_off_shinya);
    if (penalties.day_to_shinya) items.push("日深" + penalties.day_to_shinya);
    if (penalties.kibou_night) items.push("希望" + penalties.kibou_night);
    if (penalties.junnya_shinya_balance) items.push("差" + penalties.junnya_shinya_balance);
    if (penalties.good_rotation) items.push("好" + penalties.good_rotation);
    if (items.length === 0) return '<span style="color:#6ee7b7;font-size:.7rem">問題なし</span>';
    return '<span style="font-size:.7rem;color:#94a3b8">' + items.join(" ") + '</span>';
}

// ドラフトのshifts（職員別形式）からペナルティ合計を軽量集計してバッジHTMLを返す
function getDraftPenaltySummary(draftShifts) {
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    var days = new Date(Y, M, 0).getDate();

    // 希望マップ構築
    var wk = Y + "-" + M;
    var wishes = D.wishes[wk] || [];
    var wishMap = {};
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        var wdays = w.days || [];
        for (var wdi = 0; wdi < wdays.length; wdi++) {
            if (w.type === "assign") wishMap[w.staffId + "-" + wdays[wdi]] = w.shift;
        }
    }

    // フラット形式に変換
    var flatShifts = {};
    for (var staffId in draftShifts) {
        var daysMap = draftShifts[staffId];
        for (var day in daysMap) {
            flatShifts[staffId + "-" + day] = daysMap[day];
        }
    }

    // 全スタッフのペナルティを合算
    var totals = {
        consec_5: 0, consec_6: 0, night_interval_close: 0,
        shinya_no_rest: 0, scattered_night: 0, junnya_off_shinya: 0,
        day_to_shinya: 0, kibou_night: 0, junnya_shinya_balance: 0,
        good_rotation: 0
    };
    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        var wt = s.workType || "2kohtai";
        if (wt === "fixed" || wt === "day_only") continue;
        var prevData = getPrevMonthStaffData(s.id, Y, M, W);
        var ps = calculatePersonalLoad(s.id, flatShifts, days, wt, Y, M, wishMap, prevData);
        for (var k in totals) totals[k] += (ps.penalties[k] || 0);
    }
    return renderPenaltySummary(totals);
}

// 比較対象ドラフトを設定
function setCompareDraft(name) {
    // loadDraftListのキャッシュからデータ取得
    if (!window._lastDraftData || !window._lastDraftData.drafts[name]) return;
    var draftShifts = window._lastDraftData.drafts[name].shifts;
    compareDraftShifts = {};
    for (var staffId in draftShifts) {
        var daysMap = draftShifts[staffId];
        for (var day in daysMap) {
            compareDraftShifts[staffId + "-" + day] = daysMap[day];
        }
    }
    compareDraftName = name;
    render();
}

function clearCompareDraft() {
    compareDraftShifts = null;
    compareDraftName = null;
    render();
}

function calculateVersionMetrics(shifts) {
    var staff = [];
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].ward === W) staff.push(D.staff[i]);
    }
    var days = new Date(Y, M, 0).getDate();

    function gini(arr) {
        if (!arr || arr.length < 2) return 0;
        arr = arr.slice().sort(function (a, b) { return a - b; });
        var n = arr.length, total = arr.reduce(function (a, b) { return a + b; }, 0);
        if (total === 0) return 0;
        var sum = 0;
        for (var i = 0; i < n; i++) sum += (2 * (i + 1) - n - 1) * arr[i];
        return sum / (n * total);
    }

    var nightCounts = [], weekendCounts = [], lateCounts = [], consMaxes = [];
    var wishTotal = 0, wishViolated = 0;

    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        var wt = s.workType || "2kohtai";
        var nightCount = 0, akeCount = 0, lateCount = 0, weekendWork = 0, consMax = 0, cons = 0;

        for (var d = 1; d <= days; d++) {
            var sh = shifts[s.id + "-" + d] || "";
            var dt = new Date(Y, M - 1, d);
            var wd = dt.getDay();
            var isWeekend = (wd === 0 || wd === 6 || HOLIDAYS[Y + "-" + M + "-" + d]);

            if (["night2", "junnya", "shinya"].indexOf(sh) >= 0) nightCount++;
            if (sh === "ake") akeCount++;
            if (sh === "late") lateCount++;
            if (isWeekend && sh && ["off", "paid", "refresh"].indexOf(sh) < 0) weekendWork++;
            if (sh && ["off", "paid", "refresh"].indexOf(sh) < 0) { cons++; if (cons > consMax) consMax = cons; }
            else cons = 0;
        }

        // 夜勤pt（二交代: night2+ake実日数, 三交代: junnya+shinya実日数）
        var nightPt = (wt === "2kohtai" || wt === "night_only") ? nightCount + akeCount : nightCount;

        if (wt !== "day_only" && wt !== "fixed" && wt !== "night_only") {
            nightCounts.push(nightPt);
            lateCounts.push(lateCount);
            weekendCounts.push(weekendWork);
            consMaxes.push(consMax);
        }
    }

    // 希望達成率（現在の病棟の職員のみ）
    var wk = Y + "-" + M;
    var wishes = D.wishes[wk] || [];
    // 現在病棟の職員IDセットを作成
    var staffIds = new Set();
    for (var si = 0; si < staff.length; si++) {
        staffIds.add(staff[si].id);
    }
    // 職員別off/refresh希望日マップ（off優先で競合する非off希望をスキップ）
    var staffOffDays2 = {};
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (!staffIds.has(w.staffId)) continue;
        if (w.type === "assign" && (w.shift === "off" || w.shift === "refresh")) {
            if (!staffOffDays2[w.staffId]) staffOffDays2[w.staffId] = {};
            var wds = w.days || [];
            for (var wdi = 0; wdi < wds.length; wdi++) staffOffDays2[w.staffId][wds[wdi]] = true;
        }
    }
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (!staffIds.has(w.staffId)) continue;
        var wdays = w.days || [];
        for (var wdi = 0; wdi < wdays.length; wdi++) {
            var wd = wdays[wdi];
            if (wd < 1 || wd > days) continue;
            if (w.type === "assign" && w.shift !== "off" && w.shift !== "refresh" && staffOffDays2[w.staffId] && staffOffDays2[w.staffId][wd]) continue;
            wishTotal++;
            var actual = shifts[w.staffId + "-" + wd] || "";
            if (w.type === "assign" && actual !== w.shift) wishViolated++;
            if (w.type === "avoid" && actual === w.shift) wishViolated++;
        }
    }
    // 制約チェック
    var errors = 0, warnings = 0, issues = [];

    // 前月末データを取得（月またぎチェック用）
    var prevY = Y, prevM = M - 1;
    if (prevM < 1) { prevM = 12; prevY--; }
    var prevDays = new Date(prevY, prevM, 0).getDate();
    var prevSk = prevY + "-" + prevM + "-" + W;
    var prevShifts = D.shifts[prevSk] || {};

    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        var wt = s.workType || "2kohtai";
        var prevSh = "", prev2Sh = "";
        var consWork = 0, consJunnya = 0;

        // 月またぎ：前月末の連続準夜を計算
        if (wt === "3kohtai") {
            for (var pd = prevDays; pd >= 1; pd--) {
                var psh = prevShifts[s.id + "-" + pd] || "";
                if (psh === "junnya") consJunnya++;
                else break;
            }
        }

        for (var d = 1; d <= days; d++) {
            var sh = shifts[s.id + "-" + d] || "";

            // 連勤チェック（固定シフトは除外、akeは夜勤の一部）
            if (sh && ["off", "paid", "refresh"].indexOf(sh) < 0) {
                consWork++;
                if (wt !== "fixed") {  // 固定シフト職員は連勤チェック除外
                    if (consWork > 5) {
                        errors++;
                        if (issues.length < 5) issues.push("❌" + s.name + ": 6連勤(" + d + "日)");
                    } else if (consWork === 5) {
                        warnings++;
                        if (issues.length < 5) issues.push("⚠" + s.name + ": 5連勤(" + d + "日)");
                    }
                }
            } else { consWork = 0; }

            // 準夜連続チェック (3kohtai) - 3連続以上
            if (wt === "3kohtai") {
                if (sh === "junnya") {
                    consJunnya++;
                    if (consJunnya >= 3) {
                        errors++;
                        if (issues.length < 5) issues.push("❌" + s.name + ": 準夜3連(" + d + "日)");
                    }
                } else { consJunnya = 0; }
            }

            // 遅出→深夜チェック (3kohtai)
            if (wt === "3kohtai" && prevSh === "late" && sh === "shinya") {
                errors++;
                if (issues.length < 5) issues.push("❌" + s.name + ": 遅出→深夜(" + d + "日)");
            }

            // 準夜→深夜チェック (3kohtai)
            if (wt === "3kohtai" && prevSh === "junnya" && sh === "shinya") {
                errors++;
                if (issues.length < 5) issues.push("❌" + s.name + ": 準夜→深夜(" + d + "日)");
            }

            // 夜勤→明けなしチェック (2kohtai)
            if (wt === "2kohtai" && prevSh === "night2" && sh !== "ake") {
                errors++;
                if (issues.length < 5) issues.push("❌" + s.name + ": 夜勤後明けなし(" + d + "日)");
            }

            // 明け→勤務チェック (2kohtai) - 明けの翌日は休みが望ましい
            if (wt === "2kohtai" && prevSh === "ake" && sh && ["off", "paid", "refresh"].indexOf(sh) < 0) {
                warnings++;
                if (issues.length < 5) issues.push("⚠" + s.name + ": 明け後出勤(" + d + "日)");
            }

            prev2Sh = prevSh;
            prevSh = sh;
        }

        // 準深バランスチェック（三交代のみ）
        if (wt === "3kohtai") {
            var vJun = 0, vShin = 0;
            for (var d = 1; d <= days; d++) {
                var vsh = shifts[s.id + "-" + d] || "";
                if (vsh === "junnya") vJun++;
                if (vsh === "shinya") vShin++;
            }
            var vDiff = Math.abs(vJun - vShin);
            if (vDiff >= 3) {
                warnings++;
                if (issues.length < 5) issues.push("⚠" + s.name + ": 準深差" + vDiff + "(準" + vJun + "/深" + vShin + ")");
            }
        }
    }

    // ===== 個人負荷スコア計算 =====
    // 希望データをキー形式に変換 (staffId-day -> wishType)
    var wishMap = {};
    for (var wi = 0; wi < wishes.length; wi++) {
        var w = wishes[wi];
        if (!staffIds.has(w.staffId)) continue;
        var wdays = w.days || [];
        for (var wdi = 0; wdi < wdays.length; wdi++) {
            var wd = wdays[wdi];
            if (w.type === "assign") {
                wishMap[w.staffId + "-" + wd] = w.shift;
            }
        }
    }

    var personalScores = {};
    var personalScoreValues = [];
    for (var si = 0; si < staff.length; si++) {
        var s = staff[si];
        var wt = s.workType || "2kohtai";
        if (wt === "fixed" || wt === "day_only") continue; // 固定・日勤のみは除外

        var ps = calculatePersonalLoad(s.id, shifts, days, wt, Y, M, wishMap, getPrevMonthStaffData(s.id, Y, M, W));
        personalScores[s.id] = {
            name: s.name,
            score: ps.score,
            penalties: ps.penalties,
            issues: getPersonalIssues(ps)
        };
        personalScoreValues.push(ps.score);
    }

    // 個人スコア統計（ペナルティ件数: 0=最良、多いほど悪い）
    var maxPersonal = personalScoreValues.length ? Math.max.apply(null, personalScoreValues) : 0;
    var avgPersonal = personalScoreValues.length ? personalScoreValues.reduce(function(a, b) { return a + b; }, 0) / personalScoreValues.length : 0;
    var personalStd = 0;
    if (personalScoreValues.length >= 2) {
        var variance = personalScoreValues.reduce(function(sum, v) { return sum + Math.pow(v - avgPersonal, 2); }, 0) / personalScoreValues.length;
        personalStd = Math.sqrt(variance);
    }

    // ワースト3（ペナルティ多い順）
    var worstStaff = Object.keys(personalScores)
        .map(function(id) { return { id: id, name: personalScores[id].name, score: personalScores[id].score, issues: personalScores[id].issues }; })
        .sort(function(a, b) { return b.score - a.score; })
        .slice(0, 3);

    var m = {
        nightGini: gini(nightCounts),
        weekendGini: gini(weekendCounts),
        lateGini: gini(lateCounts),
        consWorkAvg: consMaxes.length ? consMaxes.reduce(function (a, b) { return a + b; }, 0) / consMaxes.length : 0,
        consWorkMax: consMaxes.length ? Math.max.apply(null, consMaxes) : 0,
        wishSatisfaction: wishTotal > 0 ? (wishTotal - wishViolated) / wishTotal * 100 : 100,
        errors: errors,
        warnings: warnings,
        issues: issues,
        // 個人負荷スコア（ペナルティ件数合計）
        personalScores: personalScores,
        maxPersonal: maxPersonal,
        avgPersonal: Math.round(avgPersonal * 10) / 10,
        personalStd: Math.round(personalStd * 10) / 10,
        worstStaff: worstStaff
    };

    // 総合スコア計算 (100点満点) - ペナルティ件数ベース
    var score = 100;
    score -= maxPersonal * 3;             // 最悪ケース
    score -= avgPersonal * 2;             // 平均ペナルティ
    score -= personalStd * 2;             // ばらつき
    // 従来の減点要素
    score -= m.errors * 15;
    score -= m.warnings * 5;
    score -= (100 - m.wishSatisfaction) * 0.5;

    m.totalScore = Math.max(0, Math.min(100, Math.round(score)));

    // 星評価
    if (m.totalScore >= 90) m.stars = "⭐⭐⭐";
    else if (m.totalScore >= 70) m.stars = "⭐⭐";
    else if (m.totalScore >= 50) m.stars = "⭐";
    else m.stars = "要改善";

    return m;
}

function loadVersion(id) {
    var sk = Y + "-" + M + "-" + W;
    var vk = D.shiftVersions[sk];
    if (!vk) return;

    for (var i = 0; i < vk.versions.length; i++) {
        if (vk.versions[i].id === id) {
            D.shifts[sk] = JSON.parse(JSON.stringify(vk.versions[i].shifts));
            save();
            render();
            return;
        }
    }
}

function deleteVersion(id) {
    var sk = Y + "-" + M + "-" + W;
    var vk = D.shiftVersions[sk];
    if (!vk) return;

    vk.versions = vk.versions.filter(function (v) { return v.id !== id; });
    save();
    renderVersions();
}

function renderVersions() {
    var sk = Y + "-" + M + "-" + W;
    var vk = D.shiftVersions ? D.shiftVersions[sk] : null;
    var table = document.getElementById("versionCompareTable");
    var list = document.getElementById("versionList");
    var quickList = document.getElementById("versionQuickList");

    // 下部セクションを非表示
    if (table) table.innerHTML = '';
    if (list) list.innerHTML = '';

    if (!quickList) return;

    if (!vk || vk.versions.length === 0) {
        quickList.innerHTML = '<span style="color:#9ca3af;font-size:.85rem">シフト生成後、自動的に保存されます</span>';
        return;
    }

    var versions = vk.versions;

    // 旧形式の案のメトリクスを再計算
    var needsSave = false;
    for (var vi = 0; vi < versions.length; vi++) {
        if (versions[vi].metrics.totalScore === undefined) {
            versions[vi].metrics = calculateVersionMetrics(versions[vi].shifts);
            needsSave = true;
        }
    }
    if (needsSave) save();

    // シフト表上部のクイックリスト with ツールチップ
    var qHtml = '<span style="font-weight:bold;color:var(--blue);margin-right:.5rem">📁 保存済み:</span>';
    for (var vi = 0; vi < versions.length; vi++) {
        var v = versions[vi];
        var m = v.metrics;
        var score = m.totalScore || 0;
        var stars = m.stars || "";

        // スコアに応じた色
        var borderColor = score >= 90 ? "#10b981" : score >= 70 ? "#3b82f6" : score >= 50 ? "#f59e0b" : "#ef4444";
        var bgColor = score >= 90 ? "rgba(16,185,129,0.1)" : score >= 70 ? "rgba(59,130,246,0.1)" : score >= 50 ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)";

        // ツールチップ内容
        var nl = String.fromCharCode(10);
        var tooltip = v.name + " (" + v.timestamp.slice(11, 16) + ")" + nl;
        tooltip += "総合スコア: " + score + "点 " + stars + nl;
        tooltip += "─────────" + nl;
        tooltip += "エラー: " + (m.errors || 0) + " / 警告: " + (m.warnings || 0) + nl;
        tooltip += "夜勤Gini: " + (m.nightGini || 0).toFixed(3) + nl;
        tooltip += "週末Gini: " + (m.weekendGini || 0).toFixed(3) + nl;
        if (W === "2") tooltip += "遅出Gini: " + (m.lateGini || 0).toFixed(3) + nl;
        tooltip += "連勤最大: " + (m.consWorkMax || 0) + "日" + nl;
        tooltip += "希望達成: " + (m.wishSatisfaction || 100).toFixed(0) + "%";

        qHtml += '<div style="display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .7rem;background:' + bgColor + ';border:2px solid ' + borderColor + ';border-radius:8px;font-size:.85rem;cursor:default" title="' + tooltip + '">';
        qHtml += '<span style="font-weight:bold">' + v.name + '</span>';
        qHtml += '<span style="font-size:.8rem;color:' + borderColor + '">' + score + '点</span>';
        qHtml += '<button class="btn btn-primary" style="padding:.15rem .5rem;font-size:.7rem" onclick="loadVersion(' + v.id + ')">適用</button>';
        qHtml += '<button style="padding:.1rem .3rem;font-size:.75rem;color:#ef4444;background:none;border:none;cursor:pointer;font-weight:bold" onclick="deleteVersion(' + v.id + ')">×</button>';
        qHtml += '</div>';
    }
    quickList.innerHTML = qHtml;
}

// ========== 実績管理モード ==========
var ACTUAL_MODE = false;
var actualData = {};      // { staffId: { "1": "day", ... } }
var confirmedData = {};   // 比較用
var pendingActualChange = null; // { staffId, day, newShift }

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
            ACTUAL_MODE = true;
        } else {
            alert(res.message || "エラー");
        }
    }).catch(function(e) { alert("通信エラー: " + e); });
}

function toggleActualMode() {
    ACTUAL_MODE = !ACTUAL_MODE;
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
            actualData = res.actual.shifts || {};
            confirmedData = (res.confirmed && res.confirmed.shifts) || {};
            renderActual();
        } else {
            alert("実績データがありません");
            ACTUAL_MODE = false;
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
    pendingActualChange = { staffId: staffId, day: day, newShift: newShift };
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
    pendingActualChange = null;
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

// loadShiftFile を拡張してシフトファイルデータをキャッシュ
if (!D._shiftFiles) D._shiftFiles = {};

var _origLoadShiftFile = typeof loadShiftFile === "function" ? loadShiftFile : null;

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
