"""三病棟4月 - 診断メッセージ確認用（軽量版）"""
import sys, json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from validation import employee_to_frontend
from solver import ShiftSolver

emps = json.load(open("../shared/employees.json", "r", encoding="utf-8"))
san = [employee_to_frontend(e) for e in emps if e.get("ward") == "sanbyoutou"]
ws = json.load(open("shared/ward_settings.json", "r", encoding="utf-8"))
w3 = ws.get("3", {})
config = {"ward": "sanbyoutou", "reqDayWeekday": w3.get("reqDayWeekday", 7),
          "reqDayHoliday": w3.get("reqDayHoliday", 5), "reqJunnya": w3.get("reqJunnya", 3),
          "reqShinya": w3.get("reqShinya", 2), "reqLate": w3.get("reqLate", 0),
          "maxLate": w3.get("maxLate", 4), "dayStaffByDay": w3.get("dayStaffByDay", {}),
          "minQualifiedByDay": w3.get("minQualifiedByDay", {}),
          "minAideByDay": w3.get("minAideByDay", {})}

# 前月シフト
prev_shifts = {}
prev_file = "shifts/sanbyoutou/2026-03.json"
if os.path.exists(prev_file):
    raw = json.load(open(prev_file, "r", encoding="utf-8"))
    nested = raw.get("confirmed", {}).get("shifts", {})
    for sid, dm in nested.items():
        if isinstance(dm, dict):
            for d, sh in dm.items():
                prev_shifts[f"{sid}-{d}"] = sh

prev_days = 31
prev_month_data = {}
for s in san:
    sid = s["id"]
    ld = prev_shifts.get(f"{sid}-{prev_days}", "")
    sl = prev_shifts.get(f"{sid}-{prev_days-1}", "")
    cw, cj, co = 0, 0, 0
    for k in range(10):
        d = prev_days - k
        if d < 1: break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if not sh or sh in ("off","paid","ake","refresh"): break
        cw += 1
    for k in range(10):
        d = prev_days - k
        if d < 1: break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if sh != "junnya": break
        cj += 1
    for k in range(10):
        d = prev_days - k
        if d < 1: break
        sh = prev_shifts.get(f"{sid}-{d}", "")
        if not sh or sh not in ("off","paid","refresh"): break
        co += 1
    if ld or sl or cw > 0 or cj > 0 or co > 0:
        prev_month_data[sid] = {"lastDay": ld, "secondLastDay": sl,
                                "consecutiveWork": cw, "consecutiveJunnya": cj, "consecutiveOff": co}

# 希望
san_ids = {s["id"] for s in san}
all_w = json.load(open("shared/wishes_data.json", "r", encoding="utf-8"))
wishes = [w for w in all_w.get("2026-4", []) if w.get("staffId") in san_ids]

result = ShiftSolver({"year": 2026, "month": 4, "staff": san, "config": config,
                       "wishes": wishes, "prevMonthData": prev_month_data}).solve()

with open("test_san_quick_result.txt", "w", encoding="utf-8") as f:
    f.write(f"status: {result.get('status')}\n")
    if result.get("message"):
        f.write(f"message:\n{result['message']}\n")
    if result.get("shifts"):
        f.write(f"shifts: {len(result['shifts'])}件\n")
print("Done")
