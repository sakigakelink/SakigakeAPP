"""三病棟4月シフト infeasible 再現スクリプト"""
import json
import os
import calendar
from datetime import date
from validation import employee_to_frontend, WARD_ID_TO_CODE

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 1. Load employees
with open("shared/employees.json", "r", encoding="utf-8") as f:
    employees = json.load(f)

# Filter sanbyoutou staff
san_staff = [e for e in employees if e.get("ward") == "sanbyoutou"]
print(f"三病棟スタッフ数: {len(san_staff)}")
for s in san_staff:
    cat = s.get("shiftCategory", "?")
    print(f"  {s['name']} ({s['id']}) cat={cat} type={s.get('type')}")

# 2. Convert to frontend format
staff_list = [employee_to_frontend(e) for e in san_staff]
print(f"\nFrontend staff:")
for s in staff_list:
    print(f"  {s['name']} wt={s['workType']} maxN={s.get('maxNight')} type={s['type']}")

# 3. Build prev month data from confirmed shifts (March 2026)
prev_month_data = {}
confirmed_dir = "shared/confirmed_shifts"
prev_year, prev_month = 2026, 3
prev_days = calendar.monthrange(prev_year, prev_month)[1]

for ward_id, ward_code in WARD_ID_TO_CODE.items():
    fname = f"confirmed_{ward_code}_{prev_year}_{prev_month:02d}.json"
    fpath = os.path.join(confirmed_dir, fname)
    if not os.path.exists(fpath):
        continue
    with open(fpath, "r", encoding="utf-8") as f:
        shift_data = json.load(f)
    assignments = shift_data.get("assignments", {})
    for sid in [s["id"] for s in staff_list]:
        if sid in prev_month_data:
            continue
        if sid in assignments:
            shifts = assignments[sid]
            last_days = shifts[-(min(5, len(shifts))):]
            prev_month_data[sid] = {
                "lastShifts": last_days,
                "totalNightCount": sum(1 for sh in shifts if sh in ["night2","junnya","shinya","ake"]),
                "totalWorkDays": sum(1 for sh in shifts if sh not in ["off","yukyuu","kokyuu","furikyuu",""]),
            }

print(f"\nPrev month data found for {len(prev_month_data)} staff:")
for sid, data in prev_month_data.items():
    name = next((s["name"] for s in staff_list if s["id"] == sid), sid)
    print(f"  {name}: lastShifts={data['lastShifts']} nights={data['totalNightCount']} work={data['totalWorkDays']}")

# 4. Load wishes from backup if available
wishes = []
# Try backup directory (server-side backups)
backup_dir = os.path.join("backup")
if os.path.isdir(backup_dir):
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".json")]
    if backup_files:
        backup_files.sort()
        latest_backup = os.path.join(backup_dir, backup_files[-1])
        print(f"\nLoading wishes from: {latest_backup}")
        with open(latest_backup, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        all_wishes = backup_data.get("wishes", {}).get("2026-4", [])
        if not all_wishes:
            all_wishes = backup_data.get("wishes", {}).get("2026-04", [])
        # Filter to sanbyoutou staff only
        staff_ids = {s["id"] for s in staff_list}
        wishes = [w for w in all_wishes if w.get("staffId") in staff_ids]
        print(f"  Found {len(wishes)} wish entries for sanbyoutou 2026-04 (of {len(all_wishes)} total)")
    else:
        print("\nNo backup files found in backup/")
# Also try shared/temp_wishes_april.json
if not wishes:
    temp_path = os.path.join("shared", "temp_wishes_april.json")
    if os.path.exists(temp_path):
        print(f"\nLoading wishes from: {temp_path}")
        with open(temp_path, "r", encoding="utf-8") as f:
            all_wishes = json.load(f)
        staff_ids = {s["id"] for s in staff_list}
        wishes = [w for w in all_wishes if w.get("staffId") in staff_ids]
        print(f"  Found {len(wishes)} wish entries for sanbyoutou 2026-04")
if not wishes:
    print("\nNo wishes found - running without wishes")

# 5. monthlyOff calculation
year, month = 2026, 4
num_days = calendar.monthrange(year, month)[1]
from utils import HOLIDAYS
sundays = sum(1 for d in range(1, num_days + 1) if date(year, month, d).weekday() == 6)
holidays_in_month = sum(1 for h in HOLIDAYS if h[0] == year and h[1] == month and date(h[0], h[1], h[2]).weekday() != 6)
monthly_off = sundays + holidays_in_month
print(f"\nmonthlyOff: {monthly_off} (sundays={sundays}, holidays={holidays_in_month})")

# 6. Build config and run solver
from solver import ShiftSolver

config = {
    "year": year,
    "month": month,
    "staff": staff_list,
    "config": {
        "ward": "3",
        "reqDayWeekday": 7,
        "reqDayHoliday": 5,
        "reqJunnya": 3,
        "reqShinya": 2,
        "reqLate": 0,
        "maxLate": 0,
        "monthlyOff": monthly_off,
        "seed": 7,
    },
    "wishes": wishes,
    "prevMonthData": prev_month_data,
}

print(f"\n=== Running solver for {year}/{month} sanbyoutou ===")
print(f"Staff: {len(staff_list)}, Wishes: {len(wishes)}")
print(f"Config: reqJ=3, reqS=2, reqLate=0, monthlyOff={monthly_off}")

# Debug: show wishes per staff
wish_summary = {}
for w in wishes:
    sid = w.get("staffId")
    sh = w.get("shift")
    days = w.get("days", [])
    is_fixed = w.get("isFixed", False)
    key = f"{sid}"
    if key not in wish_summary:
        wish_summary[key] = []
    wish_summary[key].append(f"{sh}{'(fixed)' if is_fixed else ''}×{len(days)}")
print(f"\nWishes per staff:")
for sid, items in wish_summary.items():
    name = next((s["name"] for s in staff_list if s["id"] == sid), sid)
    print(f"  {name} ({sid}): {', '.join(items)}")

solver = ShiftSolver(config)

# Debug: show computed minNight
print(f"\nComputed minNight:")
total_min = 0
total_max = 0
for s in solver.staff_list:
    wt = s.get("workType", "?")
    if wt in ("day_only", "fixed"):
        continue
    mn = s.get('minNight', 0)
    mx = s.get('maxNight', 0)
    total_min += mn
    total_max += mx
    print(f"  {s['name']} wt={wt} minN={mn} maxN={mx}")
print(f"  合計: minN={total_min} maxN={total_max} demand={5*num_days}")
print(f"  供給比率: {total_max}/{5*num_days} = {total_max/(5*num_days)*100:.0f}%")
print(f"  _night_supply_ratio: {getattr(solver, '_night_supply_ratio', 'N/A (set during solve)')}")

# Count available days per staff (excluding wishes)
print(f"\n可用日数（希望休除く）:")
for s in solver.staff_list:
    wt = s.get("workType", "?")
    if wt in ("day_only", "fixed"):
        continue
    sid = s["id"]
    off_days = set()
    for w in wishes:
        if w.get("staffId") == sid and w.get("shift") in ("off","paid","refresh"):
            for d in w.get("days", []):
                off_days.add(d)
    avail = num_days - len(off_days)
    mx = s.get('maxNight', 0)
    print(f"  {s['name']}: avail={avail}/{num_days} maxN={mx} {'TIGHT' if avail < mx else ''}")

result = solver.solve()

print(f"\nStatus: {result.get('status')}")
if result.get("status") != "ok":
    msg = result.get("message", "")
    print(f"Message:\n{msg}")
else:
    print("OK - solution found")
