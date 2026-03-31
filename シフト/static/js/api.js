// api.js - データ永続化（localStorage / サーバーバックアップ）& アプリライフサイクル
import { D, W, M, setD, backupTimer, setBackupTimer, isShuttingDown, setIsShuttingDown } from './state.js';
import { getMonthlyOff } from './util.js';

export function saveWardSettings() {
    if (!D.wardSettings) D.wardSettings = {};
    var settings = {
        reqDayWeekday: parseInt(document.getElementById("reqDayWeekday").value) || 7,
        reqDayHoliday: parseInt(document.getElementById("reqDayHoliday").value) || 5,
        reqJunnya: parseInt(document.getElementById("reqJunnya").value) || 2,
        reqShinya: parseInt(document.getElementById("reqShinya").value) || 2,
        reqLate: parseInt(document.getElementById("reqLate").value) || 1,
        maxLate: parseInt(document.getElementById("maxLate").value) || 4
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
    settings.dayStaffByDay = dayStaffByDay;
    settings.minQualifiedByDay = minQualifiedByDay;
    settings.minAideByDay = minAideByDay;
    // hidden reqDayWeekday/reqDayHoliday を曜日別から自動算出（後方互換）
    settings.reqDayWeekday = dayStaffByDay.mon != null ? dayStaffByDay.mon : settings.reqDayWeekday;
    settings.reqDayHoliday = dayStaffByDay.sun != null ? dayStaffByDay.sun : settings.reqDayHoliday;
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

export function loadWardSettings() {
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
    // 曜日別日勤人数テーブル
    var dsbd = s.dayStaffByDay || {};
    var mq = s.minQualifiedByDay || {};
    var ma = s.minAideByDay || {};
    var weekdayDefault = s.reqDayWeekday || 7;
    var holidayDefault = s.reqDayHoliday || 5;
    var DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    var KEYS = ["mon","tue","wed","thu","fri","sat","sun"];
    for (var i = 0; i < DAYS.length; i++) {
        var def = (i <= 4) ? weekdayDefault : holidayDefault;
        var dsEl = document.getElementById("dayStaff" + DAYS[i]);
        var qEl = document.getElementById("minQual" + DAYS[i]);
        var aEl = document.getElementById("minAide" + DAYS[i]);
        if (dsEl) dsEl.value = dsbd[KEYS[i]] != null ? dsbd[KEYS[i]] : def;
        if (qEl) qEl.value = mq[KEYS[i]] != null ? mq[KEYS[i]] : "";
        if (aEl) aEl.value = ma[KEYS[i]] != null ? ma[KEYS[i]] : "";
    }
    // 公休日数は月で決まるため、読込後に上書き
    var mo = document.getElementById("monthlyOff");
    if (mo) {
        mo.value = getMonthlyOff(M);
    }
}

export function loadWardSettingsFromServer() {
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

export function cleanupOldData() {
    // 12ヶ月以上前のシフト・希望データを自動削除してlocalStorage容量を節約
    var now = new Date();
    var cutoffY = now.getFullYear();
    var cutoffM = now.getMonth() + 1 - 12; // 12ヶ月前
    if (cutoffM <= 0) { cutoffM += 12; cutoffY--; }
    var cleaned = 0;
    // D.shifts: キー形式 "YYYY-M-wardId"
    if (D.shifts) {
        for (var k in D.shifts) {
            var p = k.split("-");
            var ky = parseInt(p[0]), km = parseInt(p[1]);
            if (ky && km && (ky < cutoffY || (ky === cutoffY && km < cutoffM))) {
                delete D.shifts[k];
                cleaned++;
            }
        }
    }
    // D.wishes: キー形式 "YYYY-M"
    if (D.wishes) {
        for (var k in D.wishes) {
            var p = k.split("-");
            var ky = parseInt(p[0]), km = parseInt(p[1]);
            if (ky && km && (ky < cutoffY || (ky === cutoffY && km < cutoffM))) {
                delete D.wishes[k];
                cleaned++;
            }
        }
    }
    // D.dayHours: キー形式 "YYYY-M-wardId-staffId-day"
    if (D.dayHours) {
        for (var k in D.dayHours) {
            var p = k.split("-");
            var ky = parseInt(p[0]), km = parseInt(p[1]);
            if (ky && km && (ky < cutoffY || (ky === cutoffY && km < cutoffM))) {
                delete D.dayHours[k];
                cleaned++;
            }
        }
    }
    if (cleaned > 0) {
        console.log("古いデータ " + cleaned + "件を削除しました（12ヶ月以上前）");
        save();
    }
}

export function checkBackupStatus() {
    fetch("/api/backup/load")
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                var msg = "\uD83D\uDCBE " + res.timestamp;
                fetch("/api/backup/daily/info")
                    .then(function (r2) { return r2.json(); })
                    .then(function (info) {
                        if (info.count > 0) {
                            msg += " | \u65E5\u6B21: " + info.count + "\u4E16\u4EE3";
                        }
                        updateBackupStatus(msg);
                    })
                    .catch(function () { updateBackupStatus(msg); });
            }
        })
        .catch(function (e) { console.warn("fetch error:", e); });
}

export function load() {
    var s = localStorage.getItem("sakigakeData");
    if (s) {
        try {
            setD(JSON.parse(s));
        } catch (e) {
            console.error("LocalStorageデータ破損 - サーバーバックアップから自動復元を試行:", e);
            _restoreFromServer("保存データが破損していたため");
        }
    } else {
        // localStorageが空の場合もサーバーバックアップから復元を試行
        _restoreFromServer("");
    }
    if (!D.dayHours) D.dayHours = {};
}

function _restoreFromServer(reason) {
    try {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/api/backup/load", false); // 同期リクエスト
        xhr.send();
        if (xhr.status === 200) {
            var res = JSON.parse(xhr.responseText);
            if (res.status === "success" && res.data) {
                setD(res.data);
                localStorage.setItem("sakigakeData", JSON.stringify(D));
                if (reason) {
                    alert(reason + "サーバーバックアップから復元しました（" + (res.timestamp || "不明") + "時点）");
                } else {
                    console.log("サーバーバックアップから復元しました（" + (res.timestamp || "不明") + "時点）");
                }
            } else {
                setD({ staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} });
                if (reason) {
                    alert(reason + "バックアップも見つかりませんでした。初期状態で起動します。");
                }
            }
        } else {
            setD({ staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} });
            if (reason) {
                alert(reason + "初期状態で起動します。");
            }
        }
    } catch (e) {
        console.error("バックアップ復元失敗:", e);
        setD({ staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} });
        if (reason) {
            alert(reason + "初期状態で起動します。");
        }
    }
}

export function save() {
    var json = JSON.stringify(D);
    if (json.length > 4 * 1024 * 1024) {
        console.warn("データサイズ警告: " + (json.length / 1024 / 1024).toFixed(1) + "MB");
    }
    try {
        localStorage.setItem("sakigakeData", json);
    } catch (e) {
        console.error("localStorage書き込み失敗:", e);
        alert("保存容量超過: ブラウザのストレージ上限に達しました。不要な月のデータを削除してください。");
    }

    // デバウンス付き自動バックアップ（3秒後）
    if (backupTimer) clearTimeout(backupTimer);
    setBackupTimer(setTimeout(function () {
        backupToServer();
    }, 3000));
}

export function backupToServer() {
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

export function restoreFromBackup() {
    if (!confirm("サーバーのバックアップからデータを復元しますか？\n現在のデータは上書きされます。")) return;

    fetch("/api/backup/load")
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (res.status === "success") {
                setD(res.data);
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

export function exportSettings() {
    fetch("/api/settings/export", {method: "POST"})
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "sakigake_settings_" + new Date().toISOString().slice(0, 10) + ".json";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
        })
        .catch(function (e) { alert("\u30A8\u30AF\u30B9\u30DD\u30FC\u30C8\u5931\u6557: " + e); });
}

export function importSettings() {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = function () {
        if (!input.files || !input.files[0]) return;
        var reader = new FileReader();
        reader.onload = function (e) {
            var data;
            try {
                data = JSON.parse(e.target.result);
            } catch (err) {
                alert("\u7121\u52B9\u306AJSON\u30D5\u30A1\u30A4\u30EB\u3067\u3059");
                return;
            }
            if (!data.version || !data.version.startsWith("1.")) {
                alert("\u672A\u5BFE\u5FDC\u306E\u30D5\u30A1\u30A4\u30EB\u5F62\u5F0F\u3067\u3059");
                return;
            }
            var msg = "\u8A2D\u5B9A\u3092\u30A4\u30F3\u30DD\u30FC\u30C8\u3057\u307E\u3059\u304B\uFF1F\n\u73FE\u5728\u306E\u8A2D\u5B9A\u306F\u81EA\u52D5\u30D0\u30C3\u30AF\u30A2\u30C3\u30D7\u3055\u308C\u307E\u3059\u3002";
            if (data.employees) msg += "\n\u30FB\u8077\u54E1\u30C7\u30FC\u30BF: " + data.employees.length + "\u4EF6";
            if (data.wardSettings) msg += "\n\u30FB\u75C5\u68DF\u8A2D\u5B9A: " + Object.keys(data.wardSettings).length + "\u75C5\u68DF";
            if (data.holidays) msg += "\n\u30FB\u795D\u65E5\u30C7\u30FC\u30BF";
            if (!confirm(msg)) return;
            fetch("/api/settings/import", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(data),
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res.status === "success") {
                        alert(res.message);
                        location.reload();
                    } else {
                        alert("\u30A4\u30F3\u30DD\u30FC\u30C8\u30A8\u30E9\u30FC: " + res.message);
                    }
                })
                .catch(function (err) { alert("\u63A5\u7D9A\u30A8\u30E9\u30FC: " + err); });
        };
        reader.readAsText(input.files[0]);
    };
    input.click();
}

export function migrateStaffToBackend() {
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

export function updateBackupStatus(msg) {
    var el = document.getElementById("backupStatus");
    if (el) el.textContent = msg;
}

export function restartServer() {
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

export function shutdownApp() {
    if (!confirm("アプリを終了しますか？\nデータは自動バックアップされています。")) return;

    setIsShuttingDown(true);

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
            setIsShuttingDown(false);
            alert("終了処理中にエラーが発生しました");
        });
}
