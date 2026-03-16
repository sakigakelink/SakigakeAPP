"""三病棟4月 - reqJunnya/reqShinya変動テスト"""
import sys, json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from validation import employee_to_frontend
from solver import ShiftSolver

emps = json.load(open("shared/employees.json", "r", encoding="utf-8"))
san = [employee_to_frontend(e) for e in emps if e.get("ward") == "sanbyoutou"]

# minNight全員0
for s in san:
    s["minNight"] = 0

ws = json.load(open("shared/ward_settings.json", "r", encoding="utf-8"))
w3 = ws.get("3", {})
config = {"ward": "sanbyoutou", "reqDayWeekday": w3.get("reqDayWeekday", 7),
          "reqDayHoliday": w3.get("reqDayHoliday", 5), "reqJunnya": w3.get("reqJunnya", 3),
          "reqShinya": w3.get("reqShinya", 2), "reqLate": w3.get("reqLate", 0),
          "maxLate": w3.get("maxLate", 4), "dayStaffByDay": w3.get("dayStaffByDay", {}),
          "minQualifiedByDay": w3.get("minQualifiedByDay", {}),
          "minAideByDay": w3.get("minAideByDay", {})}

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

san_ids = {s["id"] for s in san}
all_w = json.load(open("shared/wishes_data.json", "r", encoding="utf-8"))
wishes = [w for w in all_w.get("2026-4", []) if w.get("staffId") in san_ids]

# 國枝のday希望(6,13,20,27)を除外
kunied_id = None
for s in san:
    if s["name"].startswith("國枝"):
        kunied_id = s["id"]
        break

wishes_no_kunie_day = []
for w in wishes:
    if w.get("staffId") == kunied_id and w.get("shift") == "day":
        continue
    wishes_no_kunie_day.append(w)

cases = [
    ("baseline", wishes, {}),
    ("no_kunie_day", wishes_no_kunie_day, {}),
]
with open("test_mn0_result.txt", "w", encoding="utf-8") as f:
    for label, ws, extra_cfg in cases:
        cfg = dict(config)
        cfg.update(extra_cfg)
        for s in san:
            s["minNight"] = 0
        r = ShiftSolver({"year": 2026, "month": 4, "staff": san, "config": cfg,
                          "wishes": ws, "prevMonthData": prev_month_data}).solve()
        line = f"{label}: {r.get('status')}"
        if r.get("shifts"):
            line += f" ({len(r['shifts'])}件)"
        f.write(line + "\n")
        print(line)
print("Done")
