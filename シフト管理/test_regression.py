"""Regression test"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from solver import ShiftSolver
from validation import employee_to_frontend

with open('shared/employees.json', 'r', encoding='utf-8') as f:
    all_emps = json.load(f)

with open('shared/ward_settings.json', 'r', encoding='utf-8') as f:
    _ws = json.load(f)

WARD_IDS = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
WARD_CONFIGS = {
    wn: {**_ws[wn], "ward": wn, "monthlyOff": 9}
    for wn in ("1", "2", "3")
}

for wn, cfg in WARD_CONFIGS.items():
    ward_id = WARD_IDS[wn]
    w_emps = [e for e in all_emps if e.get('ward') == ward_id]
    staff = [employee_to_frontend(e) for e in w_emps]
    sp = [{"id": s["id"], "name": s["name"], "type": s.get("type","nurse"),
           "workType": s.get("workType","2kohtai"), "maxNight": s.get("maxNight",5),
           "nightRestriction": s.get("nightRestriction"), "fixedPattern": s.get("fixedPattern")}
          for s in staff]
    # Ward 3: provide prevMonthData (realistic scenario)
    # 前月も深夜帯==2を守っていたので、前月末night2は最大2名
    prev = {}
    if wn == "3":
        k2 = [s for s in sp if s['workType'] == '2kohtai']
        for s in k2[:2]:
            prev[s["id"]] = {"lastDay": "night2"}
    data = {"year": 2025, "month": 7, "staff": sp, "config": {**cfg, "seed": 42},
            "wishes": [], "prevMonthData": prev}
    solver = ShiftSolver(data)
    result = solver.solve()
    st = result.get('status','?')
    at = result.get('attempt','?')
    vl = len(result.get('violations',[]))
    ok = "OK" if st.lower() in ['optimal','feasible'] else "NG"
    print(f"Ward {wn}: {ok} status={st} attempt={at} violations={vl}")
    if st.lower() not in ['optimal','feasible']:
        print(f"  {result.get('message','')[:200]}")
    else:
        for nm, info in result.get('stats',{}).get('nightPerStaff',{}).items():
            if '専従' in info: print(f"  {nm}: {info}")
