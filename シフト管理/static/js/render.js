import { D, W, Y, M, setY, setM, sel, currentViewDraft, setCurrentViewDraft, compareDraftShifts, compareDraftName, ACTUAL_MODE, actualData, confirmedData, HOLIDAYS } from './state.js';
import { ABBR, WARDS, SHIFT_BTNS, PENALTY_KEYS } from './constants.js';
import { escHtml, isHoliday, getMonthlyOff, getWorkTypeBadge, getStaffTypeBadge, getStaffTypeColor } from './util.js';

function changeMonth(d) {
    setM(M + d);
    if (M > 12) { setM(1); setY(Y + 1); }
    if (M < 1) { setM(12); setY(Y - 1); }
    // 月切替時にサーバーからシフトデータを再取得
    setCurrentViewDraft(null);
    updateMonth();
    render();
    if (window.renderWishes) window.renderWishes();
    if (window.loadShiftFileAndTrackActual) window.loadShiftFileAndTrackActual();
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
    if (window.checkConfirmStatus) window.checkConfirmStatus();
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
            var loadResult = window.calculatePersonalLoad(s.id, D.shifts[sk], days, wt, Y, M, wishMap, window.getPrevMonthStaffData(s.id, Y, M, W));
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
            // 夜勤カウント：スロット数（2kohtai/night_only: night2+ake, 3kohtai: junnya+shinya）
            if (wt === "2kohtai" || wt === "night_only") {
                if (sh === "night2" || sh === "ake") nc++;
            } else if (wt === "3kohtai") {
                if (sh === "junnya" || sh === "shinya") nc++;
            } else {
                if (sh === "night2" || sh === "junnya" || sh === "shinya") nc++;
            }
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
            // 制約違反ハイライト
            var violCls = "";
            var violTip = "";
            if (window._lastViolations) {
                for (var vi = 0; vi < window._lastViolations.length; vi++) {
                    var vv = window._lastViolations[vi];
                    if (vv.staffId === s.id && vv.day === d) {
                        violCls = " cell-violation";
                        violTip = vv.type;
                        break;
                    }
                }
            }
            html += "<td class=\"shift-cell" + cls + cellHolCls + diffCls + violCls + "\" data-staff=\"" + s.id + "\" data-day=\"" + d + "\" style=\"" + style + "\"" + (violTip ? " title=\"" + escHtml(violTip) + "\"" : "") + ">" + cellContent + "</td>";
        }
        // 夜勤セル色分け: maxNightとの比率で背景色
        var ncStyle = "";
        if (wt !== "day_only" && wt !== "fixed") {
            var defaultMax = (wt === "2kohtai" || wt === "night_only") ? 10 : 5;
            var maxN = s.maxNight !== undefined ? s.maxNight : defaultMax;
            if (maxN > 0) {
                var ratio = nc / maxN;
                if (ratio >= 0.9) ncStyle = "background:#fca5a5;font-weight:bold";       // 赤: 90%以上
                else if (ratio >= 0.7) ncStyle = "background:#fed7aa";                     // オレンジ: 70-90%
                else if (ratio <= 0.3) ncStyle = "background:#bfdbfe;font-weight:bold";   // 青: 30%以下
                else if (ratio <= 0.5) ncStyle = "background:#dbeafe";                     // 薄青: 30-50%
            }
        }
        html += "<td>" + dc + "</td><td style=\"" + ncStyle + "\">" + nc + "</td><td>" + oc + "</td></tr>";
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
            window.openShift(this.getAttribute("data-staff"), parseInt(this.getAttribute("data-day")));
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
    if (window.renderWishUI) window.renderWishUI();
    if (window.renderWishes) window.renderWishes();
    if (window.renderVersions) window.renderVersions();
    if (window.checkFixedStaffComplete) window.checkFixedStaffComplete();

    // シフトがある場合のみ制約チェック・公平性評価を表示
    var sk = Y + "-" + M + "-" + W;
    var shifts = D.shifts[sk] || {};
    if (Object.keys(shifts).length > 0) {
        if (window.checkConstraints) window.checkConstraints();
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

export { changeMonth, updateMonth, loadConfirmedPrevShiftsForRender, updateConstraintSummary, renderConstraintRules, renderConstraintsTab, render };

window.render = render;
window.changeMonth = changeMonth;
window.updateMonth = updateMonth;
window.renderConstraintsSummary = updateConstraintSummary;
window.renderConstraintsTab = renderConstraintsTab;
window.renderConstraintRules = renderConstraintRules;
