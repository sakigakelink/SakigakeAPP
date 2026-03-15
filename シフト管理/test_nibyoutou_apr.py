"""二病棟 2026年4月 ソルバーテスト"""
import json, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from solver import ShiftSolver
from validation import employee_to_frontend

with open('shared/employees.json', 'r', encoding='utf-8') as f:
    all_emps = json.load(f)
with open('shared/ward_settings.json', 'r', encoding='utf-8') as f:
    ws = json.load(f)
with open('shared/wishes_data.json', 'r', encoding='utf-8') as f:
    all_wishes = json.load(f)

# 二病棟のスタッフ
w_emps = [e for e in all_emps if e.get('ward') == 'nibyoutou']
staff = [employee_to_frontend(e) for e in w_emps]
sp = [{'id': s['id'], 'name': s['name'], 'type': s.get('type', 'nurse'),
       'workType': s.get('workType', '2kohtai'), 'maxNight': s.get('maxNight', 5),
       'nightRestriction': s.get('nightRestriction'), 'fixedPattern': s.get('fixedPattern')}
      for s in staff]

cfg = {**ws['2'], 'ward': '2', 'monthlyOff': 9, 'seed': 42}

data = {
    'year': 2026, 'month': 4,
    'staff': sp,
    'config': cfg,
    'wishes': all_wishes.get('2026-4', []),
    'prevMonthData': {}
}

print(f'二病棟 2026年4月 テスト')
print(f'スタッフ数: {len(sp)}')
print(f'設定: 日勤={cfg["reqDayWeekday"]}人, 準夜={cfg["reqJunnya"]}人, 深夜={cfg["reqShinya"]}人, 遅番={cfg["reqLate"]}人')
print(f'希望数: {len(data["wishes"])}件')
print('ソルバー実行中...')
sys.stdout.flush()

t0 = time.time()
result = ShiftSolver(data).solve()
elapsed = time.time() - t0

st = result.get('status', '?')
at = result.get('attempt', '?')
vl = result.get('violations', [])
ok = 'PASS' if st.lower() in ['optimal', 'feasible'] else 'FAIL'

print(f'結果: {ok}  status={st}  attempt={at}  violations={len(vl)}  time={elapsed:.1f}s')

if vl:
    print('違反:')
    for v in vl[:10]:
        print(f'  - {v}')

stats = result.get('stats', {})
nps = stats.get('nightPerStaff', {})
if nps:
    print('夜勤回数:')
    for nm, info in sorted(nps.items()):
        print(f'  {nm}: {info}')

sys.exit(0 if ok == 'PASS' else 1)
