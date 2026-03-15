import { D, W, Y, M, compareDraftShifts, compareDraftName, setCompareDraftShifts, setCompareDraftName, currentViewDraft, HOLIDAYS } from './state.js';
import { ABBR, WARDS, PENALTY_KEYS } from './constants.js';
import { escHtml, isHoliday, getMonthlyOff, getWorkTypeBadge, getStaffTypeBadge } from './util.js';
import { save } from './api.js';

export function checkConstraints() {
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
        var defaultMax = (wt === "2kohtai" || wt === "night_only") ? 10 : 5;
        var maxNight = s.maxNight !== undefined ? s.maxNight : defaultMax;

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

        // 夜勤スロット数チェック（night2+ake / junnya+shinya で統一）
        var nightCount = 0;
        for (var d = 0; d < days; d++) {
            if (wt === "2kohtai" && (shArr[d] === "night2" || shArr[d] === "ake")) nightCount++;
            if (wt === "3kohtai" && (shArr[d] === "junnya" || shArr[d] === "shinya")) nightCount++;
            if (wt === "night_only" && (shArr[d] === "night2" || shArr[d] === "ake")) nightCount++;
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

export function calculateFairnessMetrics(staff, shifts, days, year, month) {
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

        // 夜勤スロット数（nightCountが既にnight2+ake / junnya+shinyaで統一済み）
        var nightPt = nightCount;

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

        // ===== 公平性バーチャート =====
        var chartEl = document.getElementById("metricsChart");
        if (chartEl) {
            var ch = "";
            // 夜勤分布バー
            var maxNight = Math.max.apply(null, nightCounts.concat([1]));
            ch += "<div style='margin-bottom:.8rem'><b style='font-size:.8rem'>🌙 夜勤回数分布</b>";
            for (var ci = 0; ci < staff.length; ci++) {
                var cs = staff[ci];
                if (cs.workType === "fixed" || cs.workType === "day_only") continue;
                var nc = nightCounts[ci] || 0;
                var pct = (nc / maxNight * 100).toFixed(0);
                ch += "<div style='display:flex;align-items:center;gap:.3rem;font-size:.75rem'>"
                    + "<span style='width:4.5em;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>" + escHtml(cs.name) + "</span>"
                    + "<div style='flex:1;background:var(--bg3);border-radius:3px;height:14px'>"
                    + "<div style='width:" + pct + "%;background:#8b5cf6;border-radius:3px;height:100%;min-width:1px'></div></div>"
                    + "<span style='width:2em;text-align:right'>" + nc + "</span></div>";
            }
            ch += "</div>";
            // 週末休み率分布バー
            ch += "<div style='margin-bottom:.8rem'><b style='font-size:.8rem'>📅 週末休み率分布</b>";
            for (var ci = 0; ci < staff.length; ci++) {
                var cs = staff[ci];
                if (cs.workType === "fixed") continue;
                var wr = weekendOffRatios[ci] || 0;
                ch += "<div style='display:flex;align-items:center;gap:.3rem;font-size:.75rem'>"
                    + "<span style='width:4.5em;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>" + escHtml(cs.name) + "</span>"
                    + "<div style='flex:1;background:var(--bg3);border-radius:3px;height:14px'>"
                    + "<div style='width:" + wr.toFixed(0) + "%;background:#3b82f6;border-radius:3px;height:100%;min-width:1px'></div></div>"
                    + "<span style='width:3em;text-align:right'>" + wr.toFixed(0) + "%</span></div>";
            }
            ch += "</div>";
            // 遅出分布バー（2病棟のみ）
            if (W === "2") {
                var maxLate = Math.max.apply(null, lateCounts.concat([1]));
                ch += "<div><b style='font-size:.8rem'>🌆 遅出回数分布</b>";
                for (var ci = 0; ci < staff.length; ci++) {
                    var cs = staff[ci];
                    if (cs.workType === "fixed" || cs.workType === "day_only") continue;
                    var lc = lateCounts[ci] || 0;
                    var lpct = (lc / maxLate * 100).toFixed(0);
                    ch += "<div style='display:flex;align-items:center;gap:.3rem;font-size:.75rem'>"
                        + "<span style='width:4.5em;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>" + escHtml(cs.name) + "</span>"
                        + "<div style='flex:1;background:var(--bg3);border-radius:3px;height:14px'>"
                        + "<div style='width:" + lpct + "%;background:#f59e0b;border-radius:3px;height:100%;min-width:1px'></div></div>"
                        + "<span style='width:2em;text-align:right'>" + lc + "</span></div>";
                }
                ch += "</div>";
            }
            chartEl.innerHTML = ch;
        }

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
export function saveCurrentVersion() {
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
export function calculateMetrics(year, month, shifts) {
    return calculateVersionMetrics(shifts);
}

// ========== 個人負荷スコア計算（obj準拠・Python shift_quality.py と同一ロジック） ==========
// PENALTY_KEYS is imported from constants.js

// 前月データからスタッフ別の引き継ぎ情報を取得
export function getPrevMonthStaffData(staffId, year, month, wardId) {
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

export function calculatePersonalLoad(staffId, shifts, numDays, workType, year, month, wishes, prevData) {
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

export function getPersonalIssues(result) {
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
export function renderPenaltySummary(penalties) {
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
export function getDraftPenaltySummary(draftShifts) {
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
export function setCompareDraft(name) {
    // loadDraftListのキャッシュからデータ取得
    if (!window._lastDraftData || !window._lastDraftData.drafts[name]) return;
    var draftShifts = window._lastDraftData.drafts[name].shifts;
    var newCompareDraftShifts = {};
    for (var staffId in draftShifts) {
        var daysMap = draftShifts[staffId];
        for (var day in daysMap) {
            newCompareDraftShifts[staffId + "-" + day] = daysMap[day];
        }
    }
    setCompareDraftShifts(newCompareDraftShifts);
    setCompareDraftName(name);
    window.render();
}

export function clearCompareDraft() {
    setCompareDraftShifts(null);
    setCompareDraftName(null);
    window.render();
}

export function calculateVersionMetrics(shifts) {
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

            if (["night2", "junnya", "shinya", "ake"].indexOf(sh) >= 0) nightCount++;
            if (sh === "late") lateCount++;
            if (isWeekend && sh && ["off", "paid", "refresh"].indexOf(sh) < 0) weekendWork++;
            if (sh && ["off", "paid", "refresh"].indexOf(sh) < 0) { cons++; if (cons > consMax) consMax = cons; }
            else cons = 0;
        }

        // 夜勤スロット数（night2+ake / junnya+shinya 統一済み）
        var nightPt = nightCount;

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

export function loadVersion(id) {
    var sk = Y + "-" + M + "-" + W;
    var vk = D.shiftVersions[sk];
    if (!vk) return;

    for (var i = 0; i < vk.versions.length; i++) {
        if (vk.versions[i].id === id) {
            D.shifts[sk] = JSON.parse(JSON.stringify(vk.versions[i].shifts));
            save();
            window.render();
            return;
        }
    }
}

export function deleteVersion(id) {
    var sk = Y + "-" + M + "-" + W;
    var vk = D.shiftVersions[sk];
    if (!vk) return;

    vk.versions = vk.versions.filter(function (v) { return v.id !== id; });
    save();
    renderVersions();
}

export function renderVersions() {
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

// ========== window assignments for HTML onclick and cross-module access ==========
window.checkConstraints = checkConstraints;
window.calculateFairnessMetrics = calculateFairnessMetrics;
window.calculatePersonalLoad = calculatePersonalLoad;
window.getPersonalIssues = getPersonalIssues;
window.renderPenaltySummary = renderPenaltySummary;
window.getDraftPenaltySummary = getDraftPenaltySummary;
window.getPrevMonthStaffData = getPrevMonthStaffData;
window.setCompareDraft = setCompareDraft;
window.clearCompareDraft = clearCompareDraft;
window.calculateVersionMetrics = calculateVersionMetrics;
window.calculateMetrics = calculateMetrics;
window.saveCurrentVersion = saveCurrentVersion;
window.loadVersion = loadVersion;
window.deleteVersion = deleteVersion;
window.renderVersions = renderVersions;
