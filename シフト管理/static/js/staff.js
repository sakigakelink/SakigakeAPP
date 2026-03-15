import { D, W, draggedId, setDraggedId } from './state.js';
import { escHtml, getWorkTypeBadge, getStaffTypeBadge, getStaffTypeColor } from './util.js';
import { WORK_TYPES } from './constants.js';
import { save } from './api.js';
import { render } from './render.js';

export function renderStaff() {
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

export function drag(ev) {
    setDraggedId(ev.target.getAttribute("data-id"));
    ev.dataTransfer.setData("text", draggedId);
    ev.target.style.opacity = "0.4";
}

export function allowDrop(ev) {
    ev.preventDefault();
}

export function drop(ev) {
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
    setDraggedId(null);
}

export function handleWishDrop(e) {
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

export function updateMaxNightHint() {
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

export function openStaffModal() {
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

export function editStaff(id) {
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

export function saveStaff(e) {
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

export function deleteStaff(id) {
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

export function syncStaffToBackend() {
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

export function openImportModal() {
    document.getElementById("importWard").value = W;
    document.getElementById("importStaffJson").value = "";
    document.getElementById("importPreview").style.display = "none";
    document.getElementById("importModal").classList.add("active");
}

export function showImportSample() {
    var sample = [
        { id: "10060766", name: "内田ゆき", workType: "day_only", maxNight: 0 },
        { id: "10060952", name: "赤井一之", workType: "2kohtai", maxNight: 5 },
        { id: "10060993", name: "橋本昌樹", workType: "3kohtai", maxNight: 10 }
    ];
    document.getElementById("importStaffJson").value = JSON.stringify(sample, null, 2);
}

export function previewImport() {
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

export function execImport() {
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

// Window assignments for HTML onclick/ondragstart/ondrop/ondragover attributes
window.editStaff = editStaff;
window.deleteStaff = deleteStaff;
window.drag = drag;
window.allowDrop = allowDrop;
window.drop = drop;
window.handleWishDrop = handleWishDrop;
