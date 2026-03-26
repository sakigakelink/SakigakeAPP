import { D, W, Y, M, sel, setSel, solveTimer, setSolveTimer, solveStartTime, setSolveStartTime, solveChartData, setSolveChartData, solveAttemptNum, setSolveAttemptNum, _solveRetryCount, set_solveRetryCount, _solveMaxRetry, currentViewDraft, setCurrentViewDraft, ACTUAL_MODE } from './state.js';
import { ABBR, SHIFT_BTNS, WARDS } from './constants.js';
import { escHtml, isHoliday, getMonthlyOff, mergePrevWithConfirmed } from './util.js';
import { save } from './api.js';
import { render } from './render.js';
import { autoSaveDraft } from './draft.js';

function checkFixedStaffComplete() {
    // 固定シフトは希望データから読み取るためUIチェック不要
    var btn = document.getElementById("btnSolve");
    if (!btn) return;
    btn.disabled = false;
    btn.title = "";
    btn.textContent = "生成開始";
}

function getShiftReason(staffId, day) {
    var sk = Y + "-" + M + "-" + W;
    var wk = Y + "-" + M;
    var shift = D.shifts[sk] ? (D.shifts[sk][staffId + "-" + day] || "") : "";
    var reasons = [];
    // 1. 希望チェック
    var wishes = D.wishes[wk] || [];
    for (var i = 0; i < wishes.length; i++) {
        var w = wishes[i];
        if (w.staffId === staffId && w.type === "assign" && w.days && w.days.indexOf(day) >= 0) {
            if (w.shift === shift) reasons.push("✅ 希望通り（" + w.shift + "）");
            else reasons.push("⚠ 希望" + w.shift + "→" + shift);
        }
    }
    // 2. 前月引継ぎチェック（day 1-2）
    if (day <= 2) {
        var co = D.carryOver ? D.carryOver[Y + "-" + M + "-" + W] : null;
        if (co) {
            for (var ci = 0; ci < co.length; ci++) {
                if (co[ci].staffId === staffId) {
                    var lastDay = co[ci].lastDayShift || "";
                    if (lastDay === "night2" || lastDay === "junnya" || lastDay === "shinya") {
                        if (day === 1 && shift === "ake") reasons.push("前月夜勤→明け（自動）");
                        if (day === 2 && shift === "off") reasons.push("夜勤明け翌日→休み（自動）");
                    }
                    break;
                }
            }
        }
    }
    // 3. 固定シフトチェック
    var staff = null;
    for (var i = 0; i < D.staff.length; i++) { if (D.staff[i].id === staffId) { staff = D.staff[i]; break; } }
    if (staff && staff.workType === "fixed") reasons.push("固定シフト職員");
    // 4. violations チェック
    if (window._lastViolations) {
        for (var i = 0; i < window._lastViolations.length; i++) {
            var v = window._lastViolations[i];
            if (v.staffId === staffId && v.day === day) reasons.push("⚠ " + v.type);
        }
    }
    // 5. デフォルト
    if (reasons.length === 0 && shift) reasons.push("ソルバーによる自動割当");
    return reasons;
}

function openShift(id, d) {
    setSel({ id: id, d: d, _actualMode: ACTUAL_MODE });
    var s = null;
    for (var i = 0; i < D.staff.length; i++) {
        if (D.staff[i].id === id) { s = D.staff[i]; break; }
    }
    document.getElementById("shiftModalTitle").textContent = s.name + " - " + M + "/" + d + (ACTUAL_MODE ? " [実績]" : "");
    // シフト理由表示
    var reasonEl = document.getElementById("shiftReasonInfo");
    if (reasonEl) {
        var reasons = getShiftReason(id, d);
        if (reasons.length > 0) {
            reasonEl.innerHTML = "<div style='padding:.5rem;background:var(--bg2);border-radius:4px;font-size:.8rem;margin-bottom:.5rem;border-left:3px solid var(--blue)'>" + reasons.join("<br>") + "</div>";
        } else {
            reasonEl.innerHTML = "";
        }
    }
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

function solve(seed, solveMode) {
    var log = document.getElementById("log");
    var btn = document.getElementById("btnSolve");
    var btnPool = document.getElementById("btnSolvePool");
    var progress = document.getElementById("solveProgress");
    var solveLog = document.getElementById("solveLog");
    var solveStatus = document.getElementById("solveStatus");
    var solveElapsed = document.getElementById("solveElapsed");

    // solveMode を保存（doSolve に引き継ぐ）
    window._currentSolveMode = solveMode || null;

    log.innerHTML = "";
    log.style.display = "none";
    solveLog.innerHTML = "";
    progress.style.display = "block";
    btn.disabled = true;
    if (btnPool) btnPool.disabled = true;
    btn.textContent = solveMode === "pool" ? "複数案生成中..." : "生成中...";

    // チャートリセット
    setSolveChartData([]);
    setSolveAttemptNum(0);
    var chart = document.getElementById("solveChart");
    if (chart) {
        chart.style.display = "none";
        var ctx = chart.getContext("2d");
        ctx.clearRect(0, 0, chart.width, chart.height);
    }

    // 再試行カウンタリセット
    set_solveRetryCount(0);

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
    setSolveStartTime(Date.now());
    setSolveTimer(setInterval(function() {
        var elapsed = ((Date.now() - solveStartTime) / 1000).toFixed(1);
        solveElapsed.textContent = "経過時間: " + elapsed + "秒";
    }, 100));

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

    // サーバーの確定シフトでローカルデータを補完（異動職員対応）
    var mergeResult = mergePrevWithConfirmed(prevShifts);
    prevShifts = mergeResult.shifts;
    var merged = mergeResult.merged;
    addProgressLog("前月データ読込: " + Object.keys(prevShifts).length + "件" + (merged > 0 ? " (異動補完" + merged + "件)" : ""));
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
        config: (function() {
            var cfg = {
                ward: W,
                reqDayWeekday: parseInt(document.getElementById("reqDayWeekday").value) || 7,
                reqDayHoliday: parseInt(document.getElementById("reqDayHoliday").value) || 5,
                reqJunnya: parseInt(document.getElementById("reqJunnya").value) || 2,
                reqShinya: parseInt(document.getElementById("reqShinya").value) || 2,
                reqLate: (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("reqLate").value) || 1),
                maxLate: (W === "1" || W === "3") ? 0 : (parseInt(document.getElementById("maxLate").value) || 4),
                monthlyOff: getMonthlyOff(M),
                seed: seed
            };
            // 曜日別日勤人数
            var DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
            var KEYS = ["mon","tue","wed","thu","fri","sat","sun"];
            var dayStaffByDay = {}, minQualifiedByDay = {}, minAideByDay = {};
            for (var i = 0; i < DAYS.length; i++) {
                var ds = document.getElementById("dayStaff" + DAYS[i]).value;
                var qv = document.getElementById("minQual" + DAYS[i]).value;
                var av = document.getElementById("minAide" + DAYS[i]).value;
                dayStaffByDay[KEYS[i]] = ds !== "" ? parseInt(ds) : null;
                minQualifiedByDay[KEYS[i]] = qv !== "" ? parseInt(qv) : null;
                minAideByDay[KEYS[i]] = av !== "" ? parseInt(av) : null;
            }
            cfg.dayStaffByDay = dayStaffByDay;
            cfg.minQualifiedByDay = minQualifiedByDay;
            cfg.minAideByDay = minAideByDay;
            // 日付別オーバーライド（デフォルトと異なる値のみ送信）
            var dayDateOverrides = {};
            var daysInMonth = new Date(Y, M, 0).getDate();
            for (var dd = 1; dd <= daysInMonth; dd++) {
                var qIn = document.getElementById("ovrQ_" + dd);
                var aIn = document.getElementById("ovrA_" + dd);
                var ov = {};
                if (qIn && qIn.value !== "") {
                    var qv2 = parseInt(qIn.value);
                    var qDef = parseInt(qIn.getAttribute("data-default")) || 0;
                    if (qv2 !== qDef) ov.minQualified = qv2;
                }
                if (aIn && aIn.value !== "") {
                    var av2 = parseInt(aIn.value);
                    var aDef = parseInt(aIn.getAttribute("data-default")) || 0;
                    if (av2 !== aDef) ov.minAide = av2;
                }
                if (Object.keys(ov).length > 0) {
                    dayDateOverrides[String(dd)] = ov;
                }
            }
            if (Object.keys(dayDateOverrides).length > 0) {
                cfg.dayDateOverrides = dayDateOverrides;
            }
            var chkRelax = document.getElementById("chkRelaxMode");
            if (chkRelax && chkRelax.checked) {
                cfg.relaxMode = true;
            }
            // 解プールモード
            if (window._currentSolveMode === "pool") {
                cfg.solveMode = "pool";
                cfg.analyzeSensitivity = true;
            }
            return cfg;
        })(),
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
                setSolveChartData([]);
                setSolveAttemptNum(data.num || 0);
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
        if (solveTimer) { clearInterval(solveTimer); setSolveTimer(null); }
        var finalTime = ((Date.now() - solveStartTime) / 1000).toFixed(1);
        progress.style.display = "none";
        log.style.display = "flex";
        addLog("エラー: " + e.message + " (" + finalTime + "秒)", "error");
        btn.disabled = false;
        btn.textContent = "生成開始";
    });

    function finishSolve(r) {
        if (solveTimer) { clearInterval(solveTimer); setSolveTimer(null); }
        var finalTime = ((Date.now() - solveStartTime) / 1000).toFixed(1);

        // === 解プールモード ===
        if (r.status && r.status.toLowerCase() === "pool" && r.solutions && r.solutions.length > 0) {
            progress.style.display = "none";
            log.style.display = "flex";

            var altCount = r.solutions.length - 1;
            addLog("🎯 ベストプラクティス + 代替" + altCount + "案を生成しました (" + finalTime + "秒)", "success");

            // 最良解をメイン表示
            var bestSol = r.solutions[0];
            var bestObj = Infinity;
            for (var si = 0; si < r.solutions.length; si++) {
                var solObj = (r.solutions[si].optimization_score || {}).objective_value || Infinity;
                if (solObj < bestObj) { bestObj = solObj; bestSol = r.solutions[si]; }
            }

            // メイン表示に最良解を適用
            var sk = Y + "-" + M + "-" + W;
            D.shifts[sk] = {};
            for (var k in bestSol.shifts) D.shifts[sk][k] = bestSol.shifts[k];
            save();
            render();

            // 各案をドラフトとして直列保存（競合防止）
            // idx=0: ベストプラクティス、idx=1~4: 代替案B~E
            var altLabels = ["B", "C", "D", "E"];
            var poolSolutions = r.solutions.slice();
            function savePoolDraftSequential(idx) {
                if (idx >= poolSolutions.length) {
                    addLog("📋 下書きパネルで各案を比較できます", "info");
                    loadDraftList();
                    return;
                }
                var sol = poolSolutions[idx];
                var draftName = idx === 0
                    ? "★ベストプラクティス"
                    : "代替案" + altLabels[idx - 1] + "_" + (sol.profile_label || "");
                var chars = sol.characteristics || {};
                autoSaveDraft(sol.shifts, draftName, {
                    solverStatus: sol.completeness || "feasible",
                    profileLabel: sol.profile_label,
                    nightDiff: chars.night_diff,
                    maxConsecutive: chars.max_consecutive,
                    objectiveValue: chars.objective_value
                }, function() {
                    savePoolDraftSequential(idx + 1);
                });
            }
            savePoolDraftSequential(0);
            for (var si = 0; si < r.solutions.length; si++) {
                var sol = r.solutions[si];
                var chars = sol.characteristics || {};
                var label = si === 0 ? "★ベストプラクティス" : "代替案" + altLabels[si - 1] + " " + (sol.profile_label || "");
                addLog("  " + label +
                    " (夜勤差" + (chars.night_diff || "?") +
                    ", 最大連勤" + (chars.max_consecutive || "?") + "日)", "info");
            }

            // 感度分析の表示
            if (r.sensitivity && r.sensitivity.length > 0) {
                addLog("📊 感度分析:", "info");
                for (var ai = 0; ai < r.sensitivity.length; ai++) {
                    var a = r.sensitivity[ai];
                    addLog("  " + a.label + " → " + a.improvement + "点改善", "info");
                }
            }

            btn.disabled = false;
            btn.textContent = "生成開始";
            var btnPoolEnd = document.getElementById("btnSolvePool");
            if (btnPoolEnd) btnPoolEnd.disabled = false;
            return;
        }

        if (r.status && r.status.toLowerCase() in { optimal: 1, feasible: 1 }) {
            progress.style.display = "none";
            log.style.display = "flex";

            addLog("完了: " + r.status + " (" + finalTime + "秒)", "success");
            // ステータスバーにソルバー結果を表示
            var compEl = document.getElementById("solverCompleteness");
            if (compEl) {
                var st = r.status.toLowerCase();
                window._lastSolverStatus = st;
                if (st === "optimal") {
                    compEl.textContent = "最適解";
                    compEl.style.background = "#166534";
                    compEl.style.color = "#fff";
                } else {
                    compEl.textContent = "暫定解";
                    compEl.style.background = "#854d0e";
                    compEl.style.color = "#fff";
                }
                if (r.relaxation) {
                    compEl.textContent = "緩和解";
                    compEl.style.background = "#d97706";
                    compEl.style.color = "#fff";
                }
                compEl.style.display = "inline";
            }
            if (r.relaxation) {
                addLog("⚠ 制約緩和: " + r.relaxation.label, "error");
            }
            if (r.attempt) {
                if (r.attempt === 4) {
                    addLog("⚠ 試行4: 勤務間インターバル違反の可能性あり", "error");
                } else if (r.attempt > 1) {
                    addLog("試行" + r.attempt + "で解決", "info");
                }
            }

            window._lastViolations = r.violations || [];
            if (r.violations && r.violations.length > 0) {
                addLog("\u26A0 \u5E0C\u671B\u9038\u8131 " + r.violations.length + "\u4EF6", "error");
                var shown = Math.min(r.violations.length, 10);
                for (var vi = 0; vi < shown; vi++) {
                    var v = r.violations[vi];
                    addLog("  " + v.name + " " + v.day + "\u65E5: " + v.type, "error");
                }
                if (r.violations.length > shown) {
                    addLog("  ...\u4ED6" + (r.violations.length - shown) + "\u4EF6", "error");
                }
            } else {
                addLog("\u5E0C\u671B\u306F\u3059\u3079\u3066\u53CD\u6620", "success");
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
            // 労基法コンプライアンスチェック結果表示
            if (window._laborCompliance) {
                var lc = window._laborCompliance;
                if (lc.compliant) {
                    addLog("労基法: 準拠 ✅", "success");
                } else {
                    var lcMsg = "労基法: 違反 " + lc.summary.total + "件";
                    if (lc.summary.interval_11h > 0) lcMsg += " [インターバル不足" + lc.summary.interval_11h + "]";
                    if (lc.summary.weekly_rest > 0) lcMsg += " [暦週休日なし" + lc.summary.weekly_rest + "]";
                    if (lc.summary.four_week_rest > 0) lcMsg += " [4週4休不足" + lc.summary.four_week_rest + "]";
                    addLog(lcMsg + " ⚠️", "error");
                }
            }
            renderVersions();

            // ハード制約違反チェック → 自動再試行
            // render() 内の checkConstraints() が window._lastCheckResult に結果を保存済み
            var checkResult = window._lastCheckResult;
            if (checkResult && checkResult.errors.length > 0 && _solveRetryCount < _solveMaxRetry) {
                set_solveRetryCount(_solveRetryCount + 1);
                var newSeed = Math.floor(Math.random() * 10000) + 1;
                addLog("⟳ ハード制約違反あり → 自動再試行 " + _solveRetryCount + "/" + _solveMaxRetry + " (seed=" + newSeed + ")", "error");

                // UIをリセットして再実行
                log.innerHTML = "";
                log.style.display = "none";
                solveLog.innerHTML = "";
                progress.style.display = "block";
                btn.disabled = true;
                btn.textContent = "再試行中...(" + _solveRetryCount + "/" + _solveMaxRetry + ")";
                setSolveChartData([]);
                setSolveAttemptNum(0);

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
        var btnPoolRestore = document.getElementById("btnSolvePool");
        if (btnPoolRestore) btnPoolRestore.disabled = false;
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

export {
    checkFixedStaffComplete,
    getShiftReason,
    openShift,
    setShift,
    solve,
    loadConfirmedPrevShifts,
    drawSolveChart,
    doSolve,
    addLog
};

window.openShift = openShift;
window.setShift = setShift;
window.solve = solve;
window.doSolve = doSolve;
window.drawSolveChart = drawSolveChart;
window.checkFixedStaffComplete = checkFixedStaffComplete;
