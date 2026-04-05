"""
Sakigake Shift - 病棟エンジン基底クラス
ソルバー以外のユーティリティメソッド（職員読込、前月引継、flex検証）を提供
"""
import calendar
import json
from pathlib import Path


class WardEngine:
    """病棟別ユーティリティ操作の基底クラス"""

    WARD_ID = None  # サブクラスでオーバーライド

    def __init__(self):
        self.ward_config = {}
        if self.WARD_ID:
            config_path = Path(__file__).parent / self.WARD_ID / 'config.json'
            if config_path.exists():
                with open(config_path, encoding='utf-8') as f:
                    self.ward_config = json.load(f)

    def load_staff(self):
        """shared/employees.jsonから当該病棟の職員を読み込み"""
        employees_path = Path(__file__).parent.parent.parent / 'shared' / 'employees.json'
        if not employees_path.exists():
            return {
                'flexRequest': [],
                'dayOnly': [],
                'twoShift': [],
                'threeShift': [],
                'nightOnly': [],
            }

        with open(employees_path, encoding='utf-8') as f:
            all_staff = json.load(f)

        # 当該病棟の職員のみ抽出
        staff = [s for s in all_staff if s.get('ward') == self.WARD_ID]

        return {
            'flexRequest': [s for s in staff if s.get('shiftCategory') == 'flexRequest'],
            'dayOnly': [s for s in staff if s.get('shiftCategory') == 'dayOnly'],
            'twoShift': [s for s in staff if s.get('shiftCategory') == 'twoShift'],
            'threeShift': [s for s in staff if s.get('shiftCategory') == 'threeShift'],
            'nightOnly': [s for s in staff if s.get('shiftCategory') == 'nightOnly'],
        }

    def get_carry_over_state(self, year, month, prev_shift):
        """前月の状態を取得（休みが見つかるまで遡る）"""
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        last_day = calendar.monthrange(prev_year, prev_month)[1]
        rest_types = ['休', '有', '公', 'off', 'paid', 'refresh']

        result = {}
        staff_data = self.load_staff()
        all_staff = []
        for category in staff_data.values():
            all_staff.extend(category)

        for s in all_staff:
            staff_id = s['id']
            staff_shifts = prev_shift.get(staff_id, {})

            consecutive_work = 0
            trace_log = []

            for day in range(last_day, 0, -1):
                shift = self._get_shift_for_day(staff_shifts, prev_year, prev_month, day)

                log_entry = {
                    'date': f"{prev_year}-{prev_month:02d}-{day:02d}",
                    'shift': shift
                }

                if shift in rest_types:
                    log_entry['stop'] = True
                    log_entry['reason'] = 'rest_found'
                    trace_log.append(log_entry)
                    break

                if shift in ['ake', '明']:
                    log_entry['skip'] = True
                    log_entry['reason'] = 'ake_skip'
                    trace_log.append(log_entry)
                    continue

                consecutive_work += 1
                trace_log.append(log_entry)

            consecutive_off = 0
            for day in range(last_day, 0, -1):
                shift = self._get_shift_for_day(staff_shifts, prev_year, prev_month, day)
                if shift in rest_types:
                    consecutive_off += 1
                else:
                    break

            last_shift = self._get_shift_for_day(staff_shifts, prev_year, prev_month, last_day)
            force_ake = last_shift in ['night2', '夜']

            result[staff_id] = {
                'staffName': s['name'],
                'lastDayShift': last_shift,
                'consecutiveWork': consecutive_work,
                'consecutiveOff': consecutive_off,
                'forceAke': force_ake,
                'traceLog': trace_log
            }

        return result

    def _get_shift_for_day(self, staff_shifts, year, month, day):
        """複数の日付形式に対応してシフトを取得"""
        # 形式1: "YYYY-MM-DD"
        date_str = f"{year}-{month:02d}-{day:02d}"
        if date_str in staff_shifts:
            return staff_shifts[date_str]

        # 形式2: "d" (文字列)
        if str(day) in staff_shifts:
            return staff_shifts[str(day)]

        # 形式3: d (整数)
        if day in staff_shifts:
            return staff_shifts[day]

        # データがない場合はデフォルト（休み扱い）
        return 'off'

    def validate_flex_complete(self, year, month, assignments):
        """flexRequest職員の全日入力チェック"""
        num_days = calendar.monthrange(year, month)[1]
        staff_data = self.load_staff()
        flex_staff = staff_data.get('flexRequest', [])

        if len(flex_staff) == 0:
            return {
                'complete': True,
                'missing': [],
                'flexStaffCount': 0,
                'message': 'flexRequest職員がいないためスキップ可能'
            }

        missing = []
        for s in flex_staff:
            staff_id = s['id']
            missing_dates = []

            for day in range(1, num_days + 1):
                date_str = f"{year}-{month:02d}-{day:02d}"
                has_assignment = False

                # 形式1: {staff_id: {date_str: shift}}
                if staff_id in assignments:
                    staff_assignments = assignments[staff_id]
                    if isinstance(staff_assignments, dict):
                        if date_str in staff_assignments and staff_assignments[date_str]:
                            has_assignment = True
                        elif str(day) in staff_assignments and staff_assignments[str(day)]:
                            has_assignment = True

                # 形式2: {"staff_id-day": shift}（フラット形式）
                flat_key = f"{staff_id}-{day}"
                if flat_key in assignments and assignments[flat_key]:
                    has_assignment = True

                if not has_assignment:
                    missing_dates.append(date_str)

            if missing_dates:
                missing.append({
                    'staffId': staff_id,
                    'staffName': s['name'],
                    'dates': missing_dates,
                    'missingCount': len(missing_dates),
                    'totalDays': num_days
                })

        return {
            'complete': len(missing) == 0,
            'missing': missing,
            'flexStaffCount': len(flex_staff)
        }
