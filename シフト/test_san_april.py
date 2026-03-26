"""三病棟4月シフト生成テスト - リモート実データで実行"""
import sys, json, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from validation import employee_to_frontend, WARD_ID_TO_CODE
from solver import ShiftSolver

# 1. 職員データ読み込み
emps = json.load(open("shared/employees.json", "r", encoding="utf-8"))
san = [e for e in emps if e.get("ward") == "sanbyoutou"]
print(f"三病棟職員数: {len(san)}")

staff_list = []
for e in san:
    fe = employee_to_frontend(e)
    staff_list.append(fe)
    print(f"  {fe['name']} wt={fe['workType']} maxN={fe.get('maxNight','?')} type={fe['type']}")

# 2. 病棟設定
ws = json.load(open("shared/ward_settings.json", "r", encoding="utf-8"))
w3 = ws.get("3", {})
config = {
    "ward": "sanbyoutou",
    "reqDayWeekday": w3.get("reqDayWeekday", 7),
    "reqDayHoliday": w3.get("reqDayHoliday", 5),
    "reqJunnya": w3.get("reqJunnya", 3),
    "reqShinya": w3.get("reqShinya", 2),
    "reqLate": w3.get("reqLate", 0),
    "maxLate": w3.get("maxLate", 4),
    "dayStaffByDay": w3.get("dayStaffByDay", {}),
    "minQualifiedByDay": w3.get("minQualifiedByDay", {}),
    "minAideByDay": w3.get("minAideByDay", {}),
}
print(f"\n設定: reqJ={config['reqJunnya']} reqS={config['reqShinya']} reqLate={config['reqLate']}")

# 3. 前月シフトデータ読み込み（confirmed.shifts: {staffId: {day: shift}} → flatten to {staffId-day: shift}）
prev_shifts = {}
prev_file = "shifts/sanbyoutou/2026-03.json"
if os.path.exists(prev_file):
    prev_data_raw = json.load(open(prev_file, "r", encoding="utf-8"))
    confirmed = prev_data_raw.get("confirmed", {})
    nested = confirmed.get("shifts", {})
    for sid, day_map in nested.items():
        if isinstance(day_map, dict):
            for d, sh in day_map.items():
                prev_shifts[f"{sid}-{d}"] = sh
    print(f"前月シフト: {len(prev_shifts)}件 ({len(nested)}名分)")

# 前月引継ぎデータ構築
prev_days = 31  # 2026年3月
prev_month_data = {}
for s in staff_list:
    sid = s["id"]
    last_day = prev_shifts.get(f"{sid}-{prev_days}", "")
    second_last = prev_shifts.get(f"{sid}-{prev_days-1}", "")

    c_work = 0
    for k in range(10):
        d = prev_days - k
        if d < 1:
            break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if not sh or sh in ("off", "paid", "ake", "refresh"):
            break
        c_work += 1

    c_jun = 0
    for k in range(10):
        d = prev_days - k
        if d < 1:
            break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if sh != "junnya":
            break
        c_jun += 1

    c_off = 0
    for k in range(10):
        d = prev_days - k
        if d < 1:
            break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if not sh or sh not in ("off", "paid", "refresh"):
            break
        c_off += 1

    if last_day or second_last or c_work > 0 or c_jun > 0 or c_off > 0:
        prev_month_data[sid] = {
            "lastDay": last_day,
            "secondLastDay": second_last,
            "consecutiveWork": c_work,
            "consecutiveJunnya": c_jun,
            "consecutiveOff": c_off,
        }

print(f"前月引継ぎ: {len(prev_month_data)}名")
for sid, pd in prev_month_data.items():
    name = next((s["name"] for s in staff_list if s["id"] == sid), sid)
    if pd["lastDay"] or pd["consecutiveWork"] >= 4:
        print(f"  {name}: last={pd['lastDay']} cWork={pd['consecutiveWork']} cJun={pd['consecutiveJunnya']}")

# 4. 希望データ読み込み（トップレベル "2026-4" にフラットリスト、三病棟職員でフィルタ）
wishes = []
san_ids = {s["id"] for s in staff_list}
wishes_file = "shared/wishes_data.json"
if os.path.exists(wishes_file):
    all_wishes = json.load(open(wishes_file, "r", encoding="utf-8"))
    all_april = all_wishes.get("2026-4", [])
    wishes = [w for w in all_april if w.get("staffId") in san_ids]
    print(f"\n希望データ: {len(wishes)}件 (全体{len(all_april)}件から三病棟分抽出)")
    for w in wishes:
        name = next((s["name"] for s in staff_list if s["id"] == w.get("staffId")), w.get("staffId"))
        print(f"  {name}: {w.get('type')} {w.get('shift')} days={w.get('days')}")

# 5. ソルバー実行
solver_data = {
    "year": 2026,
    "month": 4,
    "staff": staff_list,
    "config": config,
    "wishes": wishes,
    "prevMonthData": prev_month_data,
}

# 希望を1件ずつ除外して原因希望を特定
print("\n=== 希望の原因特定 ===")
# まず全希望で実行
solver_all = ShiftSolver(solver_data)
result_all = solver_all.solve()
print(f"全希望({len(wishes)}件): {result_all.get('status')}")

if result_all.get("status") == "infeasible":
    # staffId別にグルーピングして除外テスト
    staff_wishes = {}
    for w in wishes:
        sid = w.get("staffId")
        staff_wishes.setdefault(sid, []).append(w)

    with open("test_san_result.txt", "w", encoding="utf-8") as f:
        f.write(f"全希望: {result_all.get('status')}\n")
        if result_all.get("message"):
            f.write(f"msg: {result_all['message']}\n\n")

        f.write("=== 職員別除外テスト ===\n")
        for sid, sw in staff_wishes.items():
            name = next((s["name"] for s in staff_list if s["id"] == sid), sid)
            # この職員の希望を除外
            filtered = [w for w in wishes if w.get("staffId") != sid]
            sd = dict(solver_data)
            sd["wishes"] = filtered
            r = ShiftSolver(sd).solve()
            status = r.get("status")
            mark = "*** SOLVED ***" if status != "infeasible" else ""
            line = f"  {name}({sid}) 除外 → {status} {mark}"
            print(line)
            f.write(line + "\n")

    result = result_all
else:
    result = result_all
    with open("test_san_result.txt", "w", encoding="utf-8") as f:
        f.write(f"全希望: {result.get('status')}\n")
        if result.get("shifts"):
            f.write(f"シフト数: {len(result['shifts'])}件\n")

status = result.get("status")
print(f"\nステータス: {status}")
if result.get("message"):
    print(f"メッセージ:\n{result['message']}")
if status in ("FEASIBLE", "OPTIMAL"):
    shifts = result.get("shifts", {})
    print(f"シフト数: {len(shifts)}件")
elif status == "INFEASIBLE":
    print("*** 解なし ***")

print("\n結果を test_san_result.txt に書き出しました")
