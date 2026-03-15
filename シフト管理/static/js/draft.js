import { D, W, Y, M, currentViewDraft, setCurrentViewDraft, compareDraftName } from './state.js';
import { escHtml } from './util.js';
import { save } from './api.js';
import { render } from './render.js';
import { calculateMetrics, getDraftPenaltySummary } from './metrics.js';
import { updateActualButtons } from './actual.js';

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
                setCurrentViewDraft(data.selectedDraft);
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
                setCurrentViewDraft(name);  // 保存した案を表示中に設定
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
                setCurrentViewDraft(name);
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
                setCurrentViewDraft(name);  // 選択した案を表示中に設定
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

            setCurrentViewDraft(name);
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

export {
    loadDraftList,
    saveDraft,
    autoSaveDraft,
    selectDraft,
    loadDraft,
    deleteDraft,
    confirmShift,
    checkConfirmStatus,
    migrateShiftsToFiles
};

window.loadDraft = loadDraft;
window.selectDraft = selectDraft;
window.deleteDraft = deleteDraft;
window.checkConfirmStatus = checkConfirmStatus;
window.loadDraftList = loadDraftList;
window.saveDraft = saveDraft;
window.confirmShift = confirmShift;
