"""Regression test - 全病棟テスト（希望あり）＋品質評価"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))
from solver import ShiftSolver
from validation import employee_to_frontend
from shift_quality import evaluate_shift_quality, format_quality

with open('../shared/employees.json', 'r', encoding='utf-8') as f:
    all_emps = json.load(f)

with open('shared/ward_settings.json', 'r', encoding='utf-8') as f:
    _ws = json.load(f)

with open('shared/wishes_data.json', 'r', encoding='utf-8') as f:
    all_wishes = json.load(f)

WARD_IDS = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
WARD_CONFIGS = {
    wn: {**_ws[wn], "ward": wn, "monthlyOff": 9}
    for wn in ("1", "2", "3")
}

def build_staff(ward_id):
    w_emps = [e for e in all_emps if e.get('ward') == ward_id]
    staff = [employee_to_frontend(e) for e in w_emps]
    return [{"id": s["id"], "name": s["name"], "type": s.get("type","nurse"),
             "workType": s.get("workType","2kohtai"), "maxNight": s.get("maxNight",5),
             "nightRestriction": s.get("nightRestriction"), "fixedPattern": s.get("fixedPattern")}
            for s in staff]

def run_test(label, data):
    t0 = time.time()
    result = ShiftSolver(data).solve()
    elapsed = time.time() - t0
    st = result.get('status','?')
    at = result.get('attempt','?')
    vl = len(result.get('violations',[]))
    ok = "OK" if st.lower() in ['optimal','feasible'] else "NG"
    print(f"{label}: {ok} status={st} attempt={at} violations={vl} time={elapsed:.1f}s")
    if st.lower() not in ['optimal','feasible']:
        print(f"  {result.get('message','')[:200]}")
    else:
        q = evaluate_shift_quality(result, data)
        print(f"  品質: {format_quality(q)}")
        for nm, info in result.get('stats',{}).get('nightPerStaff',{}).items():
            if '専従' in info: print(f"  {nm}: {info}")
    return ok

failed = []

# --- 希望ありテスト（2026年4月） ---
print("=== 希望あり (2026-04) ===")
wishes_apr = all_wishes.get("2026-4", [])
for wn, cfg in WARD_CONFIGS.items():
    sp = build_staff(WARD_IDS[wn])
    staff_ids = {s["id"] for s in sp}
    ward_wishes = [w for w in wishes_apr if w.get("staffId") in staff_ids]
    prev = {}
    if wn == "3":
        k2 = [s for s in sp if s['workType'] == '2kohtai']
        for s in k2[:2]:
            prev[s["id"]] = {"lastDay": "night2"}
    data = {"year": 2026, "month": 4, "staff": sp, "config": {**cfg, "seed": 42},
            "wishes": ward_wishes, "prevMonthData": prev}
    ok = run_test(f"Ward {wn} (wishes={len(ward_wishes)})", data)
    if ok != "OK": failed.append(f"Ward {wn}")

# --- 結果 ---
print()
if failed:
    print(f"FAILED: {', '.join(failed)}")
    sys.exit(1)
else:
    print("ALL PASSED")
    sys.exit(0)
