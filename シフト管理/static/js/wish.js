import { D, W, Y, M, wishDragState, setWishDragState, wishDragChip, setWishDragChip, wishDragMoved, setWishDragMoved, wishQueue, setWishQueue } from './state.js';
import { ABBR, SHIFT_BTNS } from './constants.js';
import { escHtml, isHoliday } from './util.js';
import { save } from './api.js';
import { render } from './render.js';

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

// 希望入力バリデーション
function validateWish(staffId, days, shift) {
    // 職員情報取得
    var staff = null;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === staffId) { staff = D.staff[i]; break; }
    }
    if (!staff) return { ok: false, message: "⚠ 職員が見つかりません" };

    var wt = staff.workType || "2kohtai";
    var name = staff.name || staffId;
    var restShifts = { off: 1, paid: 1, refresh: 1 };
    var shiftNames = { day: "日勤", late: "遅出", night2: "夜勤", junnya: "準夜", shinya: "深夜", off: "休み", paid: "有給", ake: "明け", refresh: "リフレ" };

    // 1. workType不整合
    var blocked = {};
    if (wt === "day_only") blocked = { night2: 1, junnya: 1, shinya: 1, ake: 1, late: 1 };
    else if (wt === "2kohtai") blocked = { junnya: 1, shinya: 1 };
    else if (wt === "3kohtai") blocked = { night2: 1, ake: 1 };
    else if (wt === "night_only") blocked = { day: 1, late: 1, junnya: 1, shinya: 1 };
    if (blocked[shift]) {
        var wtName = WORK_TYPES[wt] || wt;
        return { ok: false, message: "⚠ " + name + "は" + wtName + "のため" + (shiftNames[shift] || shift) + "は割当不可" };
    }

    // 2. 同日矛盾チェック（既存wishes + wishQueue）
    var wk = Y + "-" + M;
    var existing = D.wishes[wk] || [];
    var isNewRest = !!restShifts[shift];
    // 既存wishesから同スタッフの日別シフト種別を収集
    var dayKinds = {}; // {day: {rest: bool, work: bool}}
    for (var wi = 0; wi < existing.length; wi++) {
        var ew = existing[wi];
        if (ew.staffId !== staffId || ew.type !== "assign") continue;
        var ewDays = ew.days || [];
        for (var di = 0; di < ewDays.length; di++) {
            if (!dayKinds[ewDays[di]]) dayKinds[ewDays[di]] = { rest: false, work: false };
            if (restShifts[ew.shift]) dayKinds[ewDays[di]].rest = true;
            else dayKinds[ewDays[di]].work = true;
        }
    }
    // wishQueueからも
    for (var qi = 0; qi < wishQueue.length; qi++) {
        var qw = wishQueue[qi];
        if (qw.staffId !== staffId) continue;
        var qwDays = qw.days || [];
        for (var di = 0; di < qwDays.length; di++) {
            if (!dayKinds[qwDays[di]]) dayKinds[qwDays[di]] = { rest: false, work: false };
            if (restShifts[qw.shift]) dayKinds[qwDays[di]].rest = true;
            else dayKinds[qwDays[di]].work = true;
        }
    }
    // 新しい希望との矛盾チェック
    var conflictDays = [];
    for (var di = 0; di < days.length; di++) {
        var d = days[di];
        var dk = dayKinds[d] || { rest: false, work: false };
        if ((isNewRest && dk.work) || (!isNewRest && dk.rest)) {
            conflictDays.push(d);
        }
    }
    if (conflictDays.length > 0) {
        return { ok: false, message: "⚠ " + name + "の" + conflictDays.join(",") + "日に休みと勤務の希望が重複します" };
    }

    // 3. 前月引継ぎ競合
    if (wt === "2kohtai" || wt === "night_only") {
        var prevData = getPrevMonthStaffData(staffId, Y, M, W);
        var lastDay = prevData.lastDay;
        var forced = {}; // {day: forced_shift}
        if (lastDay === "night2") {
            forced[1] = "ake";
            if (wt === "2kohtai") forced[2] = "off";
        } else if (lastDay === "ake") {
            forced[1] = "off";
        }
        var carryConflicts = [];
        for (var di = 0; di < days.length; di++) {
            var d = days[di];
            var fsh = forced[d];
            if (!fsh) continue;
            // off強制日にrefresh/paidはOK
            if (fsh === "off" && (shift === "refresh" || shift === "paid")) continue;
            if (shift !== fsh) {
                carryConflicts.push(d + "日は前月引継ぎで" + (shiftNames[fsh] || fsh));
            }
        }
        if (carryConflicts.length > 0) {
            return { ok: false, message: "⚠ " + name + ": " + carryConflicts.join("、") + "のため" + (shiftNames[shift] || shift) + "不可" };
        }
    }

    // 4. off希望上限（警告のみ）
    if (shift === "off") {
        var monthlyOff = parseInt(document.getElementById("monthlyOff").value) || 9;
        var offCount = 0;
        for (var wi = 0; wi < existing.length; wi++) {
            var ew = existing[wi];
            if (ew.staffId === staffId && ew.type === "assign" && ew.shift === "off") {
                offCount += (ew.days || []).length;
            }
        }
        for (var qi = 0; qi < wishQueue.length; qi++) {
            if (wishQueue[qi].staffId === staffId && wishQueue[qi].shift === "off") {
                offCount += (wishQueue[qi].days || []).length;
            }
        }
        offCount += days.length;
        if (offCount > monthlyOff) {
            return { ok: true, message: "⚠ " + name + "のoff希望が" + offCount + "日 → 上限" + monthlyOff + "日を超過（生成時にエラーになる可能性あり）" };
        }
    }

    return { ok: true, message: "" };
}

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

    // バリデーション
    var v = validateWish(staffId, selectedDays, shift);
    if (!v.ok) {
        document.getElementById("parseResult").textContent = v.message;
        document.getElementById("parseResult").style.color = "var(--red)";
        return;
    }

    wishQueue.push({ staffId: staffId, staffName: staffName, days: selectedDays, shift: shift });

    // 日付選択・シフトボタン選択をリセット（職員はそのまま）
    resetWishDayChips();
    clearWishShiftBtnSelection();

    if (v.message) {
        // 警告あり（off上限超過など）だがキューには追加
        document.getElementById("parseResult").textContent = v.message;
        document.getElementById("parseResult").style.color = "#eab308";
    } else {
        document.getElementById("parseResult").textContent = "";
        document.getElementById("parseResult").style.color = "";
    }
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
    wishQueue.length = 0;
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

function setupWishDragAndDrop(container) {
    var chips = container.querySelectorAll(".wish-chip-draggable");
    for (var i = 0; i < chips.length; i++) {
        chips[i].addEventListener("dragstart", function(e) {
            setWishDragChip(this);
            setWishDragMoved(false);
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
            if (!wishDragMoved) setWishDragChip(null);
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
            setWishDragMoved(true);
            var fromIdx = parseInt(wishDragChip.getAttribute("data-wish-idx"));
            var toIdx = parseInt(this.getAttribute("data-wish-idx"));
            // マウス位置で前後を判定
            var rect = this.getBoundingClientRect();
            var insertBefore = e.clientX < (rect.left + rect.width / 2);
            reorderWish(fromIdx, toIdx, insertBefore);
            setWishDragChip(null);
        });
        // クリック抑制: ドラッグ後はonclickを発火させない
        chips[i].addEventListener("click", function(e) {
            if (wishDragMoved) {
                e.stopImmediatePropagation();
                e.preventDefault();
                setWishDragMoved(false);
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

// --- Global document-level event listeners for wish drag ---
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

// Window assignments for HTML onclick handlers
window.renderWishCalendar = renderWishCalendar;
window.wishCycleShift = wishCycleShift;
window.wishHandleKey = wishHandleKey;
window.wishStartDrag = wishStartDrag;
window.wishMoveDrag = wishMoveDrag;
window.wishEndDrag = wishEndDrag;
window.wishTouchStart = wishTouchStart;
window.wishTouchMove = wishTouchMove;
window.wishTouchEnd = wishTouchEnd;
window.wishStartMulti = wishStartMulti;
window.wishMoveMulti = wishMoveMulti;
window.wishEndMulti = wishEndMulti;
window.wishUndo = wishUndo;
window.wishRedo = wishRedo;
window.wishClear = wishClear;
window.wishSave = wishSave;
window.openWishModal = openWishModal;
window.closeWishModal = closeWishModal;
window.wishModalSelectAll = wishModalSelectAll;
window.wishModalDeselectAll = wishModalDeselectAll;
window.wishApplyModal = wishApplyModal;
window.showWishSummary = showWishSummary;
window.renderWishes = renderWishes;
window.renderWishUI = renderWishUI;
window.deleteWish = deleteWish;

export {
    parseWishNatural,
    showWishSample,
    importWish,
    importWishNatural,
    renderWishUI,
    selectWishChip,
    deselectWishChip,
    syncWishAllButton,
    wishDayMouseDown,
    wishDayMouseEnter,
    wishDayMouseUp,
    validateWish,
    addWishFromUI,
    clearWishShiftBtnSelection,
    resetWishDayChips,
    renderWishQueue,
    removeFromWishQueue,
    commitWishQueue,
    renderWishes,
    setupWishDragAndDrop,
    reorderWish,
    editWish,
    selectWishShiftBtn,
    deleteWish
};
