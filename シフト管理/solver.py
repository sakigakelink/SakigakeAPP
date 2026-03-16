"""
Sakigake Shift - 制約ソルバー
ShiftSolverクラス

勤務区分:
- 二交代 (2kohtai): ソルバー対象
- 三交代 (3kohtai): ソルバー対象
- 日勤のみ (day_only): ソルバー対象
- 固定シフト (fixed): ソルバー対象外、評価値計算からも除外
"""
import calendar
import json
import math
import os
from datetime import date
from ortools.sat.python import cp_model
from utils import HOLIDAYS


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """解の改善を監視するコールバック（進捗グラフ用）"""

    def __init__(self, log_queue=None):
        super().__init__()
        self.solutions = []
        self.best_objective = float('inf')
        self.log_queue = log_queue

    def on_solution_callback(self):
        current_obj = self.ObjectiveValue()
        current_time = self.WallTime()

        if current_obj < self.best_objective:
            improvement = self.best_objective - current_obj if self.best_objective != float('inf') else 0
            self.best_objective = current_obj
            self.solutions.append({
                'objective': current_obj,
                'time': round(current_time, 2)
            })

            # ログ出力（キューがあれば）
            if self.log_queue is not None:
                self.log_queue.put({
                    'type': 'progress',
                    'obj': int(current_obj),
                    'time': round(current_time, 2),
                    'improvement': int(improvement),
                    'solutions': len(self.solutions)
                })

# シフト定数
SHIFTS = ["day", "late", "night2", "junnya", "shinya", "off", "paid", "ake", "refresh"]
SHIFT_IDX = {s: i for i, s in enumerate(SHIFTS)}
DAY_SHIFTS = ["day", "late"]


class ShiftSolver:
    def __init__(self, data):
        self.year = data["year"]
        self.month = data["month"]
        self.num_days = calendar.monthrange(self.year, self.month)[1]
        self.all_staff_list = data["staff"]  # 全職員リスト
        self.config = data.get("config", {})
        self.wishes = data.get("wishes", [])
        self.prev_month_data = data.get("prevMonthData", {})
        self.fixed_shifts_data = data.get("fixedShifts", {})  # 固定シフト職員の実際のシフト
        self.seed = self.config.get("seed", 0)
        self.model = cp_model.CpModel()
        self.shifts = {}

        # 固定シフト・flexRequest・ソルバー対象職員を分離
        self.fixed_staff = []  # 固定シフト職員
        self.flex_staff = []   # flexRequest職員（手動入力）
        self.staff_list = []   # ソルバー対象職員
        for s in self.all_staff_list:
            # workType="fixed" はフロントエンド形式、shiftCategory="flexRequest" はバックエンド形式
            # 両フォーマットで受け取り可能なよう両方チェックする
            if s.get("workType") == "fixed":
                self.fixed_staff.append(s)
            elif s.get("shiftCategory") == "flexRequest":
                self.flex_staff.append(s)
            else:
                self.staff_list.append(s)
        self.locked_shifts = data.get("lockedShifts", {})

        self.num_staff = len(self.staff_list)
        self.staff_id_to_idx = {s["id"]: i for i, s in enumerate(self.staff_list)}

        # minNight自動計算（明示指定がない職員にデフォルト値を設定）
        self._compute_default_min_night()

        # 病棟エンジン設定の読込
        WARD_ID_MAP = {"1": "ichiboutou", "2": "nibyoutou", "3": "sanbyoutou"}
        ward = str(self.config.get("ward", ""))
        ward_id = WARD_ID_MAP.get(ward, "")
        self.ward_engine_config = {}
        if ward_id:
            config_path = os.path.join(os.path.dirname(__file__), "engines", ward_id, "config.json")
            if os.path.exists(config_path):
                with open(config_path, encoding="utf-8") as f:
                    self.ward_engine_config = json.load(f)

    def _compute_default_min_night(self):
        """病棟の構成（2交代/3交代の人数・配置要件）に基づきminNightデフォルトを自動計算

        計算ロジック:
        - maxNight は全勤務体系で「夜勤帯スロット数」に統一
          - 二交代: night2+ake のスロット数（night2 1回 = 2スロット）
          - 三交代: junnya+shinya のスロット数
        - 夜勤帯の総需要 = (reqJunnya + reqShinya) × days
        - cap_2k, cap_3k, supply_no は全てスロット数
        - 3kohtai が担当する需要 = total_demand - supply_2k - supply_no
        """
        req_j = self.config.get("reqJunnya", 2)
        req_s = self.config.get("reqShinya", 2)
        days = self.num_days

        staff_2k = [(i, s) for i, s in enumerate(self.staff_list)
                    if s.get("workType") == "2kohtai"]
        staff_3k = [(i, s) for i, s in enumerate(self.staff_list)
                    if s.get("workType") == "3kohtai"]

        num_2k = len(staff_2k)
        num_3k = len(staff_3k)

        if num_2k == 0 and num_3k == 0:
            return

        cap_3k = sum(s.get("maxNight", 5) for _, s in staff_3k)
        cap_2k = sum(s.get("maxNight", 10) for _, s in staff_2k)

        # night_only の供給量（スロット数）
        staff_no = [s for s in self.staff_list if s.get("workType") == "night_only"]
        supply_no = sum(s.get("maxNight", 0) for s in staff_no)

        total_night_demand = (req_j + req_s) * days
        # night_onlyが担当する分を除く
        demand_after_no = max(0, total_night_demand - supply_no)

        # 総供給能力（全てスロット数で統一済み）
        total_supply = cap_2k + cap_3k + supply_no

        if num_2k > 0 and demand_after_no > 0:
            if cap_2k == 0:
                # 全2交代職員がmaxNight=0のため夜勤割当不可
                for idx, s in staff_2k:
                    if "minNight" not in s:
                        s["minNight"] = 0
            else:
                # 最低2kohtaiスロット数: 3kohtai需要が cap_3k を超えないように
                # demand_after_no - slots_2k <= cap_3k  →  slots_2k >= demand_after_no - cap_3k
                floor_slots_2k = max(0, math.ceil(demand_after_no - cap_3k))

                # min_total_slots_2k は cap_2k の 85% を上限とし、ソルバーに柔軟性を残す
                cap_2k_ceiling = int(cap_2k * 0.85)
                if floor_slots_2k <= cap_2k_ceiling:
                    # 通常ケース: 2kohtai容量内に余裕あり
                    # 10%マージンを加えるが上限は cap_2k の 85%
                    min_total_slots_2k = min(math.ceil(floor_slots_2k * 1.10), cap_2k_ceiling)
                    # 3kohtai残り需要の確認
                    remaining_check = demand_after_no - min_total_slots_2k
                    if remaining_check > cap_3k:
                        # マージン分でオーバーした場合、floorに戻す
                        min_total_slots_2k = floor_slots_2k
                elif floor_slots_2k <= cap_2k:
                    # タイトケース: floor は容量内だが85%を超える
                    # floorそのものを使うが cap_2k の 85% で切る
                    min_total_slots_2k = cap_2k_ceiling
                else:
                    # 供給不足ケース
                    # 2kohtai は maxNight の 70% を下限として確保（控えめに）
                    min_total_slots_2k = int(cap_2k * 0.70)

                # 各2kohtai職員に按分（maxNightの比率で）
                for idx, s in staff_2k:
                    if "minNight" not in s:
                        max_n = s.get("maxNight", 10)
                        if max_n <= 0:
                            s["minNight"] = 0
                        else:
                            share = min_total_slots_2k * max_n / cap_2k
                            s["minNight"] = min(max(1, int(share)), max_n)
        elif num_2k > 0:
            # 需要なし
            for idx, s in staff_2k:
                if "minNight" not in s:
                    s["minNight"] = 0

        # 3kohtaiのminNight
        if num_3k > 0:
            total_min_slots_2k = sum(s.get("minNight", 0) for _, s in staff_2k)
            remaining_for_3k = max(0, demand_after_no - total_min_slots_2k)

            if cap_3k == 0:
                # 全3交代職員がmaxNight=0のため夜勤割当不可
                for idx, s in staff_3k:
                    if "minNight" not in s:
                        s["minNight"] = 0
            else:
                # cap_3kの85%を上限としてクランプ（ソルバーに柔軟性を残す）
                cap_3k_ceiling = int(cap_3k * 0.85)
                remaining_for_3k = min(remaining_for_3k, cap_3k_ceiling)

                # 供給不足の場合は70%に抑える
                if total_supply < demand_after_no:
                    remaining_for_3k = min(remaining_for_3k, int(cap_3k * 0.70))

                for idx, s in staff_3k:
                    if "minNight" not in s:
                        max_n = s.get("maxNight", 5)
                        if max_n <= 0:
                            s["minNight"] = 0
                        else:
                            share = remaining_for_3k * max_n / cap_3k
                            s["minNight"] = min(max(1, int(share)), max_n)


    def _get_fixed_shift(self, staff, day):
        """固定シフト職員の指定日のシフトを取得"""
        # まずfixedShiftsデータから取得（ユーザーが入力したシフト）
        staff_id = staff.get("id")
        staff_fixed = self.fixed_shifts_data.get(staff_id)
        if isinstance(staff_fixed, dict):
            day_str = str(day)
            if day_str in staff_fixed:
                return staff_fixed[day_str]
            if day in staff_fixed:
                return staff_fixed[day]
        # なければパターンから取得
        pattern = staff.get("fixedPattern", {})
        if not pattern:
            return "day"  # デフォルト
        dt = date(self.year, self.month, day)
        wd = dt.weekday()  # 0=Mon, ..., 6=Sun
        return pattern.get(str(wd), pattern.get(wd, "day"))

    def _get_fixed_staff_shifts_for_day(self, day):
        """指定日の固定シフト職員のシフトリストを取得"""
        shifts = []
        for s in self.fixed_staff:
            sh = self._get_fixed_shift(s, day)
            shifts.append(sh)
        return shifts

    def _count_fixed_staff_for_shift_type(self, day, shift_types):
        """指定日に特定シフトタイプの固定シフト職員数をカウント"""
        count = 0
        for s in self.fixed_staff:
            sh = self._get_fixed_shift(s, day)
            if sh in shift_types:
                count += 1
        return count

    def _diagnose_infeasible(self):
        """infeasible時の原因を具体的に列挙する"""
        causes = []
        rest_shifts = {"off", "paid", "refresh"}

        req_day_wd = self.config.get("reqDayWeekday", 7)
        req_day_hol = self.config.get("reqDayHoliday", 5)
        req_j = self.config.get("reqJunnya", 2)
        req_s = self.config.get("reqShinya", 2)
        req_late = self.config.get("reqLate", 1)
        req_night_total = req_j + req_s

        # 希望休マップ
        wish_off = {}  # day -> set of staffId
        wish_assign = {}  # day -> set of staffId (勤務指定)
        for w in self.wishes:
            wt = w.get("type")
            sh = w.get("shift", "")
            for d in w.get("days", []):
                if 1 <= d <= self.num_days:
                    if wt == "assign" and sh in rest_shifts:
                        wish_off.setdefault(d, set()).add(w["staffId"])
                    elif wt == "assign" and sh not in rest_shifts:
                        wish_assign.setdefault(d, set()).add(w["staffId"])

        # 前月引継ぎによる強制休
        forced_off = {}  # day -> set of staffId
        forced_details = []  # 具体的な制約
        for s in self.staff_list:
            sid = s["id"]
            name = s.get("name", sid)
            prev = self.prev_month_data.get(sid, {})
            last_day = prev.get("lastDay", "")
            consec = prev.get("consecutiveWork", 0)
            wt = s.get("workType", "2kohtai")
            max_consec = 5
            if last_day == "night2":
                forced_off.setdefault(1, set()).add(sid)
                if wt == "2kohtai":
                    forced_off.setdefault(2, set()).add(sid)
                    forced_details.append(f"{name}: 前月末night2 → 1日ake+2日休み必須")
                else:
                    forced_details.append(f"{name}: 前月末night2 → 1日ake必須")
            elif last_day == "ake":
                forced_off.setdefault(1, set()).add(sid)
                forced_details.append(f"{name}: 前月末ake → 1日休み必須")
            if consec >= max_consec:
                forced_off.setdefault(1, set()).add(sid)
                forced_details.append(f"{name}: 前月末{consec}連勤 → 1日休み必須")
            elif consec >= 4:
                forced_details.append(f"{name}: 前月末{consec}連勤 → 月初2日目までに休み必要")

        # 夜勤不可スタッフID
        day_only_ids = {s["id"] for s in self.staff_list if s.get("workType") == "day_only"}
        fixed_ids = {s["id"] for s in self.staff_list if s.get("workType") == "fixed"}

        # === 原因1: 日別人員不足（確定事実） ===
        shortage_days = []
        for d in range(1, self.num_days + 1):
            dt = date(self.year, self.month, d)
            is_hol = dt.weekday() == 6 or f"{self.year}-{self.month}-{d}" in HOLIDAYS
            req_day = req_day_hol if is_hol else req_day_wd
            total_required = req_day + req_late + req_night_total

            unavail = set()
            unavail.update(wish_off.get(d, set()))
            unavail.update(forced_off.get(d, set()))
            available = sum(1 for s in self.staff_list
                           if s["id"] not in unavail and s["id"] not in fixed_ids)
            if available < total_required:
                unavail_names = []
                for s in self.staff_list:
                    if s["id"] in wish_off.get(d, set()):
                        unavail_names.append(f"{s['name']}(希望休)")
                    elif s["id"] in forced_off.get(d, set()):
                        unavail_names.append(f"{s['name']}(前月引継)")
                shortage_days.append(
                    f"  {d}日: 出勤可能{available}人 < 必要{total_required}人"
                    f"  不在: {', '.join(unavail_names[:5])}"
                )

        if shortage_days:
            causes.append("【人員不足】以下の日で出勤可能人数が必要人数を下回っています:\n" + "\n".join(shortage_days[:5]))

        # === 原因2: 夜勤可能人数不足 ===
        night_tight = []
        for d in range(1, self.num_days + 1):
            unavail = set()
            unavail.update(wish_off.get(d, set()))
            unavail.update(forced_off.get(d, set()))
            night_capable = sum(1 for s in self.staff_list
                                if s["id"] not in unavail
                                and s["id"] not in fixed_ids
                                and s["id"] not in day_only_ids)
            if night_capable < req_night_total:
                night_tight.append(f"  {d}日: 夜勤可能{night_capable}人 < 必要{req_night_total}枠")
            elif night_capable == req_night_total:
                night_tight.append(f"  {d}日: 夜勤可能{night_capable}人 = 必要{req_night_total}枠（余裕なし）")

        if night_tight:
            causes.append("【夜勤人員不足】以下の日で夜勤に入れる人が足りません:\n" + "\n".join(night_tight[:5]))

        # === 原因3: 前月引継ぎ制約 ===
        if forced_details:
            causes.append("【前月引継ぎ制約】\n" + "\n".join(f"  {d}" for d in forced_details))

        # === 原因4: 公休日数の矛盾 ===
        off_issues = []
        for s in self.staff_list:
            wt = s.get("workType", "2kohtai")
            if wt == "fixed":
                continue
            name = s.get("name", s["id"])
            min_off = s.get("minOff", 9)
            default_max = 10 if wt in ("2kohtai", "night_only") else 5
            max_night = s.get("maxNight", default_max)

            # 希望による拘束日数
            wish_work_days = len([d for d in range(1, self.num_days + 1) if s["id"] in wish_assign.get(d, set())])
            wish_off_days = len([d for d in range(1, self.num_days + 1) if s["id"] in wish_off.get(d, set())])

            if wt == "night_only":
                effective_night = min(max_night, self.num_days)
                avail_off = self.num_days - effective_night
                if wish_off_days > avail_off:
                    off_issues.append(f"  {name}: 休日希望{wish_off_days}日 > 公休枠{avail_off}日（夜勤専従 maxNight={max_night}）")
            else:
                max_work = self.num_days - min_off
                if wish_off_days + wish_work_days > self.num_days:
                    off_issues.append(f"  {name}: 希望合計{wish_off_days + wish_work_days}日 > 月日数{self.num_days}日")

        if off_issues:
            causes.append("【公休・希望の矛盾】\n" + "\n".join(off_issues))

        # === 原因5: 全体夜勤供給不足 ===
        # maxNight はスロット数に統一済み（2kohtai/night_only: night2+ake, 3kohtai: junnya+shinya）
        night_supply = 0
        for s in self.staff_list:
            wt = s.get("workType", "2kohtai")
            if wt in ("day_only", "fixed"):
                continue
            default_max = 10 if wt in ("2kohtai", "night_only") else 5
            mn = s.get("maxNight", default_max)
            night_supply += mn
        night_demand = req_night_total * self.num_days
        if night_supply < night_demand:
            causes.append(f"【夜勤供給不足】月間夜勤需要{night_demand}枠 > 供給可能{night_supply}枠")

        return causes

    def _solve_core(self, log_queue=None, timeout=15):
        # モデル再作成 (毎回新しいモデルで解く)
        self.model = cp_model.CpModel()
        self.shifts = {}
        self.violations = []
        ward = str(self.config.get("ward", "1"))
        shift_restrictions = self.ward_engine_config.get("shiftRestrictions", {})
        staff_shortage_penalty = 0  # ソフト制約のペナルティ累積

        # minNight自動計算結果をログ出力
        if log_queue:
            for s in self.staff_list:
                wt = s.get("workType", "")
                mn = s.get("minNight", 0)
                if mn > 0 and wt in ("2kohtai", "3kohtai"):
                    def_mn = 10 if wt == "2kohtai" else 5
                    log_queue.put({'type': 'log', 'msg': f'[minNight自動] {s.get("name",s["id"])}: {wt} minNight={mn} maxNight={s.get("maxNight",def_mn)}'})

        # ソルバー対象職員がいない場合は固定シフトのみ返す
        if self.num_staff == 0:
            result = {
                "status": "optimal",
                "shifts": {},
                "stats": {"solveTime": 0, "nightPerStaff": {}},
                "violations": [],
                "message": "ソルバー対象職員なし（固定シフトのみ）"
            }
            # 固定シフト職員のシフトを追加
            for s in self.fixed_staff:
                for d in range(1, self.num_days + 1):
                    sh = self._get_fixed_shift(s, d)
                    result["shifts"][s["id"] + "-" + str(d)] = sh
            # flexRequest職員のシフトを追加
            for s in self.flex_staff:
                staff_id = s["id"]
                for d in range(1, self.num_days + 1):
                    key = f"{staff_id}-{d}"
                    if key in self.locked_shifts:
                        result["shifts"][key] = self.locked_shifts[key]
                    elif staff_id in self.locked_shifts and isinstance(self.locked_shifts[staff_id], dict):
                        shift = self.locked_shifts[staff_id].get(str(d)) or self.locked_shifts[staff_id].get(d)
                        if shift:
                            result["shifts"][key] = shift
            return result

        # ─── 事前フィザビリティチェック ───────────────────────────────────
        # チェック A: 夜勤供給不足
        _req_j = self.config.get("reqJunnya", 2)
        _req_s = self.config.get("reqShinya", 2)
        _cap_2k = sum(s.get("maxNight", 10) for s in self.staff_list if s.get("workType") == "2kohtai")
        _cap_3k = sum(s.get("maxNight", 5) for s in self.staff_list if s.get("workType") == "3kohtai")
        _supply_no = sum(s.get("maxNight", 0) for s in self.staff_list if s.get("workType") == "night_only")
        _total_supply = _cap_2k + _cap_3k + _supply_no
        _total_demand = (_req_j + _req_s) * self.num_days
        # 供給/需要比率を保存（夜勤帯制約のソフト化判定に使用）
        self._night_supply_ratio = _total_supply / _total_demand if _total_demand > 0 else 999
        if _total_supply < _total_demand:
            msg = (
                f"夜勤供給不足のため解なし: "
                f"供給{_total_supply}枠（2交代={_cap_2k} + 3交代={_cap_3k} + 夜専={_supply_no}）"
                f" < 需要{_total_demand}枠（準夜{_req_j}+深夜{_req_s}）×{self.num_days}日"
            )
            if log_queue:
                log_queue.put({'type': 'log', 'msg': f'[事前チェックA] {msg}'})
            return {"status": "infeasible", "message": msg, "shifts": {}, "violations": []}

        # チェック B: 個別 off 希望過多
        monthly_off_pre = self.config.get("monthlyOff", 9)
        for s in range(self.num_staff):
            staff = self.staff_list[s]
            if staff.get("workType") == "night_only":
                continue
            staff_id = staff["id"]
            name = staff.get("name", staff_id)
            off_wish_days = set()
            for w in self.wishes:
                if w.get("staffId") == staff_id and w.get("shift") == "off" and w.get("type") == "assign":
                    for day in w.get("days", []):
                        if 1 <= day <= self.num_days:
                            off_wish_days.add(day)
            off_wish_count = len(off_wish_days)
            if off_wish_count > monthly_off_pre:
                msg = (
                    f"{name}: off希望{off_wish_count}日 > 公休上限{monthly_off_pre}日のため解なし。"
                    f" off希望を{monthly_off_pre}日以内に減らしてください。"
                )
                if log_queue:
                    log_queue.put({'type': 'log', 'msg': f'[事前チェックB] {msg}'})
                return {"status": "infeasible", "message": msg, "shifts": {}, "violations": []}
        # チェック C: workType に対して不可能な希望
        _blocked_shifts_pre = {
            "day_only": {"night2", "junnya", "shinya", "ake", "late"},
            "2kohtai": {"junnya", "shinya"},
            "3kohtai": {"night2", "ake"},
            "night_only": {"day", "late", "junnya", "shinya"},
        }
        wish_errors = []
        for w in self.wishes:
            sid = w.get("staffId")
            sidx = self.staff_id_to_idx.get(sid)
            if sidx is None:
                continue
            wt = w.get("type")
            sh = w.get("shift")
            if sh not in SHIFT_IDX:
                continue
            staff = self.staff_list[sidx]
            staff_name = staff.get("name", sid)
            staff_wtype = staff.get("workType", "2kohtai")
            blocked = _blocked_shifts_pre.get(staff_wtype, set())
            if wt == "assign" and sh in blocked:
                wish_errors.append(f"{staff_name}: {sh}は{staff_wtype}では不可")

        # チェック D: 夜勤専従の休日希望が公休上限超過
        _night_only_rest_wish_pre = {}  # {staff_idx: set[int]}
        for w in self.wishes:
            sid = w.get("staffId")
            sidx = self.staff_id_to_idx.get(sid)
            if sidx is None:
                continue
            staff = self.staff_list[sidx]
            if staff.get("workType") != "night_only":
                continue
            wt = w.get("type")
            sh = w.get("shift")
            if wt != "assign" or sh not in ("off", "paid", "refresh"):
                continue
            staff_name = staff.get("name", sid)
            max_night = staff.get("maxNight", 0)
            # maxNight はスロット数（night2+ake）。公休 = 月日数 - スロット数
            effective_night = min(max_night, self.num_days)
            quota = max(0, self.num_days - effective_night)

            new_days = {d for d in w.get("days", []) if 1 <= d <= self.num_days}
            already = _night_only_rest_wish_pre.get(sidx, set())
            combined = already | new_days
            if len(combined) > quota:
                wish_errors.append(
                    f"{staff_name}: 夜勤専従の休日希望({len(combined)}日)が公休上限({quota}日)を超過"
                )
            _night_only_rest_wish_pre[sidx] = combined

        # チェック E: 前月引き継ぎとの競合
        for s in range(self.num_staff):
            work_type = self.staff_list[s].get("workType", "2kohtai")
            if work_type not in ("2kohtai", "night_only"):
                continue
            staff_id = self.staff_list[s]["id"]
            staff_name = self.staff_list[s].get("name", staff_id)
            prev_data = self.prev_month_data.get(staff_id, {})
            last_day = prev_data.get("lastDay", "")
            # forced: {day_number(1-indexed): forced_shift}
            forced = {}
            if last_day == "night2":
                forced[1] = "ake"
                if work_type == "2kohtai":
                    forced[2] = "off"
            elif last_day == "ake":
                forced[1] = "off"
            if not forced:
                continue
            for w in self.wishes:
                if w.get("staffId") != staff_id:
                    continue
                if w.get("type") != "assign":
                    continue
                sh = w.get("shift")
                for day in w.get("days", []):
                    f_sh = forced.get(day)
                    if not f_sh:
                        continue
                    # off強制日にrefresh/paid希望はOK（どれも休みの一種）
                    if f_sh == "off" and sh in ("refresh", "paid"):
                        continue
                    if sh != f_sh:
                        wish_errors.append(
                            f"{staff_name}: {day}日は前月引継ぎで{f_sh}のため{sh}希望は不可"
                        )

        # チェック F: 同日に休み希望と勤務希望の重複
        # {(staffId, day): set of shifts} を構築して矛盾検出
        _wish_per_day = {}  # {(staffId, day): {"rest": set, "work": set}}
        _rest_shifts_pre = {"off", "paid", "refresh"}
        for w in self.wishes:
            sid = w.get("staffId")
            if self.staff_id_to_idx.get(sid) is None:
                continue
            wt = w.get("type")
            sh = w.get("shift")
            if wt != "assign" or not sh:
                continue
            for day in w.get("days", []):
                if day < 1 or day > self.num_days:
                    continue
                key = (sid, day)
                if key not in _wish_per_day:
                    _wish_per_day[key] = {"rest": set(), "work": set()}
                if sh in _rest_shifts_pre:
                    _wish_per_day[key]["rest"].add(sh)
                else:
                    _wish_per_day[key]["work"].add(sh)
        for (sid, day), kinds in _wish_per_day.items():
            if kinds["rest"] and kinds["work"]:
                sidx = self.staff_id_to_idx[sid]
                staff_name = self.staff_list[sidx].get("name", sid)
                rest_str = "/".join(sorted(kinds["rest"]))
                work_str = "/".join(sorted(kinds["work"]))
                wish_errors.append(
                    f"{staff_name}: {day}日に休み希望({rest_str})と勤務希望({work_str})が重複"
                )

        if wish_errors:
            msg = "以下の希望が不正です。修正してください:\n" + "\n".join(wish_errors)
            if log_queue:
                log_queue.put({'type': 'log', 'msg': f'[事前チェックC/D/E/F] {msg}'})
            return {"status": "infeasible", "message": msg, "shifts": {}, "violations": []}
        # ─────────────────────────────────────────────────────────────────

        # 変数作成（ソルバー対象職員のみ）
        # --- 禁止シフトマップ構築 ---
        forbidden_map = {}
        for s in range(self.num_staff):
            si = self.staff_list[s]
            wt = si.get("workType", "2kohtai")
            forbidden = set()
            if wt == "day_only":
                forbidden = {SHIFT_IDX["night2"], SHIFT_IDX["junnya"], SHIFT_IDX["shinya"], SHIFT_IDX["ake"], SHIFT_IDX["late"]}
            elif wt == "2kohtai":
                forbidden = {SHIFT_IDX["junnya"], SHIFT_IDX["shinya"]}
            elif wt == "3kohtai":
                forbidden = {SHIFT_IDX["night2"], SHIFT_IDX["ake"]}
            elif wt == "night_only":
                forbidden = {SHIFT_IDX["day"], SHIFT_IDX["late"], SHIFT_IDX["junnya"], SHIFT_IDX["shinya"]}
            if not shift_restrictions.get("late", True):
                forbidden.add(SHIFT_IDX["late"])
            restriction = si.get("nightRestriction", None)
            if restriction == "junnya_only":
                forbidden.add(SHIFT_IDX["shinya"])
            elif restriction == "shinya_only":
                forbidden.add(SHIFT_IDX["junnya"])
            forbidden_map[s] = forbidden

        # 禁止シフト用の共有BoolVar（常にFalse）
        _false = self.model.NewBoolVar("_shared_false")
        self.model.Add(_false == 0)

        for s in range(self.num_staff):
            fb = forbidden_map[s]
            for d in range(self.num_days):
                for t in range(len(SHIFTS)):
                    if t in fb:
                        self.shifts[(s,d,t)] = _false
                    else:
                        self.shifts[(s,d,t)] = self.model.NewBoolVar(f"s{s}d{d}t{t}")

        # === プリコンピュート共有変数 ===
        # is_work[s,d]: 勤務日 (off/paid/refreshでない)
        is_work = {}
        for s in range(self.num_staff):
            for d in range(self.num_days):
                w = self.model.NewBoolVar(f"work_{s}_{d}")
                self.model.AddBoolAnd([
                    self.shifts[(s,d,SHIFT_IDX["off"])].Not(),
                    self.shifts[(s,d,SHIFT_IDX["paid"])].Not(),
                    self.shifts[(s,d,SHIFT_IDX["refresh"])].Not()
                ]).OnlyEnforceIf(w)
                self.model.AddBoolOr([
                    self.shifts[(s,d,SHIFT_IDX["off"])],
                    self.shifts[(s,d,SHIFT_IDX["paid"])],
                    self.shifts[(s,d,SHIFT_IDX["refresh"])]
                ]).OnlyEnforceIf(w.Not())
                is_work[s,d] = w

        # is_rest[s,d]: 休日 (off/paid/refreshのいずれか) - is_work の反転
        is_rest = {}
        for s in range(self.num_staff):
            for d in range(self.num_days):
                is_rest[s,d] = is_work[s,d].Not()

        # is_night[s,d]: 夜勤 (junnya or shinya) - 3kohtai用
        is_night = {}
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "3kohtai":
                for d in range(self.num_days):
                    n = self.model.NewBoolVar(f"night3k_{s}_{d}")
                    self.model.AddBoolOr([
                        self.shifts[(s,d,SHIFT_IDX["junnya"])],
                        self.shifts[(s,d,SHIFT_IDX["shinya"])]
                    ]).OnlyEnforceIf(n)
                    self.model.AddBoolAnd([
                        self.shifts[(s,d,SHIFT_IDX["junnya"])].Not(),
                        self.shifts[(s,d,SHIFT_IDX["shinya"])].Not()
                    ]).OnlyEnforceIf(n.Not())
                    is_night[s,d] = n

        # 各職員は1日1シフト
        for s in range(self.num_staff):
            for d in range(self.num_days):
                self.model.AddExactlyOne(self.shifts[(s,d,t)] for t in range(len(SHIFTS)))

        # 公休日数（off のみ = monthlyOff。paid/refresh は追加の休みで別枠）
        # 公休数は絶対厳守（全試行で == 制約）
        monthly_off = self.config.get("monthlyOff", 9)
        if log_queue:
            log_queue.put({'type': 'log', 'msg': f'[公休制約] monthlyOff={monthly_off}'})
        for s in range(self.num_staff):
            # 夜勤専従は独自の公休制約を持つためスキップ
            if self.staff_list[s].get("workType", "2kohtai") == "night_only":
                continue
            off_only = [self.shifts[(s,d,SHIFT_IDX["off"])] for d in range(self.num_days)]
            # 公休数は全レベルで絶対厳守（== monthlyOff）
            self.model.Add(sum(off_only) == monthly_off)

        # リフレッシュ日数を職員別に記録（負担調整に使用）
        # リフレッシュを取る人は休みが多い分、きつめのローテーションを許容する
        staff_refresh_days = {}  # {staff_idx: int}
        for s in range(self.num_staff):
            staff_id = self.staff_list[s]["id"]
            rc = 0
            for w in self.wishes:
                if w.get("staffId") == staff_id and w.get("shift") == "refresh" and w.get("type") == "assign":
                    rc += len(w.get("days", []))
            staff_refresh_days[s] = rc

        # 有給は希望がある場合のみ許可
        for s in range(self.num_staff):
            staff_id = self.staff_list[s]["id"]
            paid_wish_days = set()
            for w in self.wishes:
                if w.get("staffId") == staff_id and w.get("shift") == "paid" and w.get("type") == "assign":
                    for day in w.get("days", []):
                        paid_wish_days.add(day)

            for d in range(self.num_days):
                if (d + 1) not in paid_wish_days:
                    self.model.Add(self.shifts[(s, d, SHIFT_IDX["paid"])] == 0)

        # 勤務連続日数制限
        # 7連勤はハード禁止、6連勤はソフト制約（ペナルティ）
        # akeは夜勤の一部であり連勤を途切れさせない（休日=off/paid/refreshのみ）
        max_consecutive = 7
        for s in range(self.num_staff):
            for d in range(self.num_days - max_consecutive + 1):
                work_days = [is_work[s,d+dd] for dd in range(max_consecutive)]
                self.model.AddBoolOr([w.Not() for w in work_days])

            # 月初制約：前月からの連続勤務考慮
            staff_id = self.staff_list[s]["id"]
            if staff_id in self.prev_month_data:
                prev_work = self.prev_month_data[staff_id].get("consecutiveWork", 0)
                if prev_work > 0:
                    limit = max_consecutive - prev_work
                    if limit <= 0:
                        # prev_work >= max_consecutive: 月初日は必ず休みにする
                        self.model.AddBoolOr([
                            self.shifts[(s,0,SHIFT_IDX["off"])],
                            self.shifts[(s,0,SHIFT_IDX["paid"])],
                            self.shifts[(s,0,SHIFT_IDX["refresh"])]
                        ])
                    elif limit <= self.num_days:
                        start_work_days = [is_work[s,dd] for dd in range(limit)]
                        self.model.AddBoolOr([w.Not() for w in start_work_days])

        # リフレッシュ休暇は希望がない限り使わない
        for s in range(self.num_staff):
            refresh_wishes = set()
            for w in self.wishes:
                if w.get("staffId") == self.staff_list[s]["id"] and w.get("shift") == "refresh" and w.get("type") == "assign":
                    for day in w.get("days", []):
                        refresh_wishes.add(day - 1)
            for d in range(self.num_days):
                if d not in refresh_wishes:
                    self.model.Add(self.shifts[(s,d,SHIFT_IDX["refresh"])] == 0)

        # === 日別人員要件 ===
        # 固定シフト職員のシフトを事前計算
        fixed_day_counts = []  # 日勤人数
        fixed_junnya_counts = []  # 準夜帯人数
        fixed_shinya_counts = []  # 深夜帯人数
        fixed_late_counts = []  # 遅出人数

        # シフトデータが入力済みの固定シフト職員のみカウント対象
        # fixedShiftsDataにIDがあっても中身が空なら未入力扱い
        active_fixed_staff = [
            fs for fs in self.fixed_staff
            if (fs.get("id") in self.fixed_shifts_data and self.fixed_shifts_data[fs["id"]])
            or fs.get("fixedPattern")
        ]

        for d in range(self.num_days):
            day_count = 0
            junnya_count = 0
            shinya_count = 0
            late_count = 0
            for fs in active_fixed_staff:
                sh = self._get_fixed_shift(fs, d + 1)
                if sh in DAY_SHIFTS:
                    day_count += 1
                if sh in ["night2", "junnya"]:
                    junnya_count += 1
                if sh in ["ake", "shinya"]:
                    shinya_count += 1
                if sh == "late":
                    late_count += 1
            fixed_day_counts.append(day_count)
            fixed_junnya_counts.append(junnya_count)
            fixed_shinya_counts.append(shinya_count)
            fixed_late_counts.append(late_count)

        # 日勤の必要人数（曜日別 or フォールバック）
        req_day_weekday = self.config.get("reqDayWeekday", 7)
        req_day_holiday = self.config.get("reqDayHoliday", 5)
        day_staff_by_day = self.config.get("dayStaffByDay", {})
        WD_KEYS_SHORT = ["mon", "tue", "wed", "thu", "fri", "sat"]

        staff_shortage_info = []

        for d in range(self.num_days):
            # ソルバー対象職員の日勤
            dw = [self.shifts[(s,d,SHIFT_IDX[sh])] for s in range(self.num_staff) for sh in DAY_SHIFTS]

            dt_year, dt_month, dt_day = self.year, self.month, d+1
            dt_obj = date(dt_year, dt_month, dt_day)
            is_wed = (dt_obj.weekday() == 2)
            is_sat = (dt_obj.weekday() == 5)
            is_sun = (dt_obj.weekday() == 6)
            is_hol = (dt_year, dt_month, dt_day) in HOLIDAYS

            is_holiday_target = False
            weekday = dt_obj.weekday()

            if is_sun or is_hol:
                is_holiday_target = True
                ds_val = day_staff_by_day.get("sun")
                target = ds_val if ds_val is not None else req_day_holiday
            else:
                ds_val = day_staff_by_day.get(WD_KEYS_SHORT[weekday]) if weekday < 6 else None
                if ds_val is not None:
                    target = ds_val
                else:
                    target = req_day_weekday

            # 固定シフト職員の分を引く
            adjusted_target = target - fixed_day_counts[d]

            # 日勤人数はソフト制約（不足分にペナルティ）
            if adjusted_target > 0:
                shortage = self.model.NewIntVar(0, adjusted_target, f"shortage_day_{d}")
                self.model.Add(sum(dw) + shortage >= adjusted_target)
                staff_shortage_penalty += shortage * 500
                staff_shortage_info.append({"day": d+1, "type": "日勤", "var": shortage})
            else:
                self.model.Add(sum(dw) >= 0)
            # 日祝は休日基準値+1を上限（過剰配置防止）
            if is_holiday_target:
                self.model.Add(sum(dw) <= max(0, adjusted_target + 1))

        # 準夜帯の必要人数（夜勤専従含む全職員でカウント）
        req_j = self.config.get("reqJunnya", 2)
        # 供給余裕がない場合（≤110%）は1人不足までソフト制約化
        night_tight = getattr(self, '_night_supply_ratio', 999) <= 1.10
        if night_tight and log_queue:
            ratio_pct = round(getattr(self, '_night_supply_ratio', 0) * 100)
            log_queue.put({'type': 'log', 'msg': f'[夜勤帯] 供給余裕{ratio_pct}% → 夜勤帯1名不足を許容するソフト制約モードで実行'})
        for d in range(self.num_days):
            jw = [self.shifts[(s,d,SHIFT_IDX["junnya"])] for s in range(self.num_staff)]
            jw += [self.shifts[(s,d,SHIFT_IDX["night2"])] for s in range(self.num_staff)]
            adjusted_req = max(0, req_j - fixed_junnya_counts[d])
            if night_tight and adjusted_req > 0:
                # ソフト制約: 不足1人まで許容、不足にペナルティ
                j_short = self.model.NewIntVar(0, 1, f"j_short_{d}")
                self.model.Add(sum(jw) + j_short >= adjusted_req)
                self.model.Add(sum(jw) <= adjusted_req)
                staff_shortage_penalty += j_short * 2000  # 夜勤不足は日勤不足より重い
                staff_shortage_info.append({"day": d+1, "type": "準夜", "var": j_short})
            else:
                self.model.Add(sum(jw) == adjusted_req)

        # 深夜帯の必要人数（夜勤専従含む全職員でカウント、前月引き継ぎakeも含む）
        req_s = self.config.get("reqShinya", 2)
        for d in range(self.num_days):
            sw = [self.shifts[(s,d,SHIFT_IDX["shinya"])] for s in range(self.num_staff)]
            sw += [self.shifts[(s,d,SHIFT_IDX["ake"])] for s in range(self.num_staff)]
            adjusted_req = max(0, req_s - fixed_shinya_counts[d])
            if night_tight and adjusted_req > 0:
                s_short = self.model.NewIntVar(0, 1, f"s_short_{d}")
                self.model.Add(sum(sw) + s_short >= adjusted_req)
                self.model.Add(sum(sw) <= adjusted_req)
                staff_shortage_penalty += s_short * 2000
                staff_shortage_info.append({"day": d+1, "type": "深夜", "var": s_short})
            else:
                self.model.Add(sum(sw) == adjusted_req)

        # --- 職種別制約（config駆動、全病棟共通フレームワーク） ---
        nurseaide_indices = [i for i, st in enumerate(self.staff_list) if st.get("type") == "nurseaide"]
        num_nurseaide = len(nurseaide_indices)
        junkango_indices = [i for i, st in enumerate(self.staff_list) if st.get("type") == "junkango"]
        num_junkango = len(junkango_indices)
        nurse_indices = [i for i, st in enumerate(self.staff_list) if st.get("type") == "nurse"]
        qualified_indices = [i for i, st in enumerate(self.staff_list)
                             if st.get("type") in ("nurse", "junkango")]

        for d in range(self.num_days):
            dt_obj = date(self.year, self.month, d + 1)
            weekday = dt_obj.weekday()
            is_hol = (self.year, self.month, d + 1) in HOLIDAYS
            is_sun = (weekday == 6)

            # 准看護師2人での夜勤禁止（看護師+准看護師はOK）
            if num_junkango >= 2:
                jk_junnya = []
                for jk_idx in junkango_indices:
                    jk_junnya.append(self.shifts[(jk_idx, d, SHIFT_IDX["junnya"])])
                    jk_junnya.append(self.shifts[(jk_idx, d, SHIFT_IDX["night2"])])
                self.model.Add(sum(jk_junnya) <= 1)

                jk_shinya = []
                for jk_idx in junkango_indices:
                    jk_shinya.append(self.shifts[(jk_idx, d, SHIFT_IDX["shinya"])])
                    jk_shinya.append(self.shifts[(jk_idx, d, SHIFT_IDX["ake"])])
                self.model.Add(sum(jk_shinya) <= 1)

            # --- 有資格者(nurse+junkango)の日勤最低人数（ハード制約） ---
            # UI設定優先、なければengine config.jsonからフォールバック
            ui_min_qual = self.config.get("minQualifiedByDay", {})
            if qualified_indices:
                if ui_min_qual:
                    if is_sun or is_hol:
                        min_q = ui_min_qual.get("sun")
                    else:
                        min_q = ui_min_qual.get(WD_KEYS_SHORT[weekday]) if weekday < 6 else None
                else:
                    # フォールバック: engine config
                    qs_config = self.ward_engine_config.get("qualifiedStaffMinimum", {})
                    if qs_config.get("enabled"):
                        _WD_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
                        if is_sun or is_hol:
                            min_q = qs_config.get("day", {}).get("sunday_holiday")
                        else:
                            min_q = qs_config.get("day", {}).get(_WD_KEYS[weekday]) if weekday < 6 else None
                    else:
                        min_q = None

                if min_q is not None:
                    q_day = [self.shifts[(qi, d, SHIFT_IDX["day"])]
                             for qi in qualified_indices]
                    self.model.Add(sum(q_day) >= min_q)

            # --- 全時間帯で正看護師(nurse)が最低1名（ハード制約） ---
            nm_config = self.ward_engine_config.get("nurseMinimumPerBand", {})
            if nm_config.get("enabled") and nurse_indices:
                min_nurse_day = nm_config.get("day", 1)
                min_nurse_junnya = nm_config.get("junnya", 1)
                min_nurse_shinya = nm_config.get("shinya", 1)

                # 日勤帯
                n_day = [self.shifts[(ni, d, SHIFT_IDX["day"])]
                         for ni in nurse_indices]
                self.model.Add(sum(n_day) >= min_nurse_day)

                # 準夜帯 (junnya + night2)
                n_junnya = [self.shifts[(ni, d, SHIFT_IDX["junnya"])]
                            for ni in nurse_indices]
                n_night2 = [self.shifts[(ni, d, SHIFT_IDX["night2"])]
                            for ni in nurse_indices]
                self.model.Add(sum(n_junnya) + sum(n_night2) >= min_nurse_junnya)

                # 深夜帯 (shinya + ake)
                n_shinya = [self.shifts[(ni, d, SHIFT_IDX["shinya"])]
                            for ni in nurse_indices]
                n_ake = [self.shifts[(ni, d, SHIFT_IDX["ake"])]
                         for ni in nurse_indices]
                self.model.Add(sum(n_shinya) + sum(n_ake) >= min_nurse_shinya)

            # --- 看護補助者の夜勤人数制限（ハード制約） ---
            na_night_config = self.ward_engine_config.get("nurseAideNightLimits", {})
            if na_night_config.get("enabled") and num_nurseaide > 0:
                max_na_junnya = na_night_config.get("maxJunnya", 1)
                max_na_shinya = na_night_config.get("maxShinya", 1)

                na_junnya = [self.shifts[(na_idx, d, SHIFT_IDX["junnya"])]
                             for na_idx in nurseaide_indices]
                na_night2 = [self.shifts[(na_idx, d, SHIFT_IDX["night2"])]
                             for na_idx in nurseaide_indices]
                self.model.Add(sum(na_junnya) + sum(na_night2) <= max_na_junnya)

                na_shinya = [self.shifts[(na_idx, d, SHIFT_IDX["shinya"])]
                             for na_idx in nurseaide_indices]
                na_ake = [self.shifts[(na_idx, d, SHIFT_IDX["ake"])]
                          for na_idx in nurseaide_indices]
                self.model.Add(sum(na_shinya) + sum(na_ake) <= max_na_shinya)

            # --- 看護補助者の日勤最低人数（ハード制約、UI設定） ---
            ui_min_aide = self.config.get("minAideByDay", {})
            if ui_min_aide and nurseaide_indices:
                if is_sun or is_hol:
                    min_a = ui_min_aide.get("sun")
                else:
                    min_a = ui_min_aide.get(WD_KEYS_SHORT[weekday]) if weekday < 6 else None
                if min_a is not None and min_a > 0:
                    a_day = [self.shifts[(ai, d, SHIFT_IDX["day"])]
                             for ai in nurseaide_indices]
                    self.model.Add(sum(a_day) >= min_a)

        # 夜勤制約: nightRestrictionはforbidden_mapで処理済み

        # 遅出制約（shiftRestrictions.late == true の病棟のみ）
        late_config = self.ward_engine_config.get("lateShift", {})
        if shift_restrictions.get("late", True):
            req_late = self.config.get("reqLate", late_config.get("reqPerDay", 1))
            for d in range(self.num_days):
                lw = [self.shifts[(s,d,SHIFT_IDX["late"])] for s in range(self.num_staff)]
                adjusted_req = max(0, req_late - fixed_late_counts[d])
                self.model.Add(sum(lw) == adjusted_req)

        _night_only_rest_days = {}  # {staff_idx: int} - 夜勤専従の公休上限（希望overflow防止用）

        for s in range(self.num_staff):
            si = self.staff_list[s]
            work_type = si.get("workType", "2kohtai")
            default_max_night = 10 if work_type in ("2kohtai", "night_only") else 5
            max_night = si.get("maxNight", default_max_night)

            # 遅出上限（lateシフト有効な病棟のみ）
            if shift_restrictions.get("late", True):
                max_late = self.config.get("maxLate", late_config.get("maxPerStaff", 4))
                late_list = [self.shifts[(s,d,SHIFT_IDX["late"])] for d in range(self.num_days)]
                self.model.Add(sum(late_list) <= max_late)

            if work_type == "day_only":
                pass  # forbidden_mapで処理済み

            elif work_type == "2kohtai":
                # junnya/shinyaはforbidden_mapで処理済み

                # 二交代: night2→ake は常に厳守
                for d in range(self.num_days - 1):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["night2"])],
                        self.shifts[(s,d+1,SHIFT_IDX["ake"])]
                    )

                # 二交代: ake→休み は常にハード制約（明け後休みは絶対厳守）
                # off / paid / refresh のいずれかが入ればOK
                for d in range(self.num_days - 1):
                    rest_next = [
                        self.shifts[(s, d+1, SHIFT_IDX["off"])],
                        self.shifts[(s, d+1, SHIFT_IDX["paid"])],
                        self.shifts[(s, d+1, SHIFT_IDX["refresh"])],
                    ]
                    self.model.Add(sum(rest_next) >= 1).OnlyEnforceIf(
                        self.shifts[(s, d, SHIFT_IDX["ake"])]
                    )

                # 二交代の夜勤スロット数: night2+ake <= maxNight（ハード制約）
                night2_list = [self.shifts[(s,d,SHIFT_IDX["night2"])] for d in range(self.num_days)]
                ake_list = [self.shifts[(s,d,SHIFT_IDX["ake"])] for d in range(self.num_days)]
                self.model.Add(sum(night2_list) + sum(ake_list) <= max_night)

                # 二交代の最低夜勤スロット数（ソフト制約）
                min_night = si.get("minNight", 0)
                if min_night > 0:
                    mn_short = self.model.NewIntVar(0, min_night, f"mn_short_2k_{s}")
                    self.model.Add(sum(night2_list) + sum(ake_list) + mn_short >= min_night)
                    staff_shortage_penalty += mn_short * 300

                # 前月からの引き継ぎ（常に厳守）
                staff_id = self.staff_list[s]["id"]
                prev_data = self.prev_month_data.get(staff_id, {})
                if self.num_days > 0:
                    last_day = prev_data.get("lastDay", "")
                    if last_day == "night2":
                        # 前月末がnight2 → 当月1日はake
                        self.model.Add(self.shifts[(s,0,SHIFT_IDX["ake"])] == 1)
                    elif last_day == "ake":
                        # 前月末がake → 当月1日は休み（off / paid / refresh）
                        self.model.Add(self.shifts[(s,0,SHIFT_IDX["ake"])] == 0)
                        self.model.Add(
                            self.shifts[(s,0,SHIFT_IDX["off"])]
                            + self.shifts[(s,0,SHIFT_IDX["paid"])]
                            + self.shifts[(s,0,SHIFT_IDX["refresh"])]
                            >= 1
                        )
                    # 前月データなし: day0のakeは自由（ソルバーが深夜帯カバー等で判断）

                # akeの前日は必ずnight2（常に厳守）
                for d in range(1, self.num_days):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["ake"])],
                        self.shifts[(s,d-1,SHIFT_IDX["night2"])]
                    )

            elif work_type == "night_only":
                # 前月引き継ぎを先に確認（night2_target計算に影響するため）
                staff_id = self.staff_list[s]["id"]
                prev_data = self.prev_month_data.get(staff_id, {})
                last_day = prev_data.get("lastDay", "")
                # 前月末がnight2なら当月1日目はキャリーオーバーakeに固定される
                carryover_ake = 1 if last_day == "night2" else 0

                # 夜勤専従: day/late/junnya/shinyaはforbidden_mapで処理済み

                # night2→ake の基本ルール（二交代と同じ）
                for d in range(self.num_days - 1):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["night2"])],
                        self.shifts[(s,d+1,SHIFT_IDX["ake"])]
                    )
                # 夜勤専従は ake→off 不要（夜明夜明...の連続勤務が可能）

                # maxNight = 夜勤帯スロット数（night2+ake）を直接指定
                # 例: maxNight=21 → 当月のnight2+ake合計が21日
                effective_night = min(max_night, self.num_days)
                night2_list = [self.shifts[(s,d,SHIFT_IDX["night2"])] for d in range(self.num_days)]
                ake_list = [self.shifts[(s,d,SHIFT_IDX["ake"])] for d in range(self.num_days)]
                self.model.Add(sum(night2_list) + sum(ake_list) == effective_night)

                # 公休日数: 月日数 - 夜勤スロット数
                night_only_rest_days = max(0, self.num_days - effective_night)
                _night_only_rest_days[s] = night_only_rest_days
                off_list = [self.shifts[(s,d,SHIFT_IDX["off"])] for d in range(self.num_days)]
                paid_list = [self.shifts[(s,d,SHIFT_IDX["paid"])] for d in range(self.num_days)]
                refresh_list = [self.shifts[(s,d,SHIFT_IDX["refresh"])] for d in range(self.num_days)]
                self.model.Add(sum(off_list) + sum(paid_list) + sum(refresh_list) == night_only_rest_days)

                # 前月からの引き継ぎ制約
                if last_day == "night2":
                    self.model.Add(self.shifts[(s,0,SHIFT_IDX["ake"])] == 1)
                elif last_day == "ake":
                    self.model.Add(self.shifts[(s,0,SHIFT_IDX["ake"])] == 0)
                    self.model.Add(
                        self.shifts[(s,0,SHIFT_IDX["off"])]
                        + self.shifts[(s,0,SHIFT_IDX["paid"])]
                        + self.shifts[(s,0,SHIFT_IDX["refresh"])]
                        >= 1
                    )
                # 前月データなし: day0のakeは自由（ソルバーが判断）

                # akeの前日は必ずnight2
                for d in range(1, self.num_days):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["ake"])],
                        self.shifts[(s,d-1,SHIFT_IDX["night2"])]
                    )

            elif work_type == "3kohtai":
                # night2/akeはforbidden_mapで処理済み

                # 前月からの引き継ぎ（常に厳守）
                staff_id = self.staff_list[s]["id"]
                if staff_id in self.prev_month_data:
                    prev_data = self.prev_month_data[staff_id]
                    last_day_shift = prev_data.get("lastDay", "")
                    if last_day_shift == "junnya":
                        self.model.AddBoolOr([
                            self.shifts[(s,0,SHIFT_IDX["junnya"])],
                            self.shifts[(s,0,SHIFT_IDX["off"])],
                            self.shifts[(s,0,SHIFT_IDX["paid"])],
                            self.shifts[(s,0,SHIFT_IDX["refresh"])]
                        ])
                    elif last_day_shift == "shinya":
                        # 前月末が深夜→当月1日目は休み/深夜のみ（ハード制約）
                        self.model.AddBoolOr([
                            self.shifts[(s,0,SHIFT_IDX["off"])],
                            self.shifts[(s,0,SHIFT_IDX["paid"])],
                            self.shifts[(s,0,SHIFT_IDX["refresh"])],
                            self.shifts[(s,0,SHIFT_IDX["shinya"])]
                        ])

                    # 月境界: 3連続夜勤禁止
                    second_last = prev_data.get("secondLastDay", "")
                    prev_last_night = last_day_shift in ("junnya", "shinya")
                    prev_second_night = second_last in ("junnya", "shinya")

                    if prev_last_night and prev_second_night:
                        # 前月末2日が夜勤→当月1日目は夜勤禁止
                        self.model.Add(self.shifts[(s, 0, SHIFT_IDX["junnya"])] == 0)
                        self.model.Add(self.shifts[(s, 0, SHIFT_IDX["shinya"])] == 0)
                    elif prev_last_night and self.num_days >= 2:
                        # 前月末1日が夜勤→当月1日+2日の連続夜勤は禁止
                        self.model.AddBoolOr([is_night[s,0].Not(), is_night[s,1].Not()])

                # 三交代の基本ルール（常に厳守）
                for d in range(self.num_days - 1):
                    # 準夜の翌日は準夜/公休/有給/リフ休のみ
                    self.model.AddBoolOr([
                        self.shifts[(s,d+1,SHIFT_IDX["junnya"])],
                        self.shifts[(s,d+1,SHIFT_IDX["off"])],
                        self.shifts[(s,d+1,SHIFT_IDX["paid"])],
                        self.shifts[(s,d+1,SHIFT_IDX["refresh"])]
                    ]).OnlyEnforceIf(self.shifts[(s,d,SHIFT_IDX["junnya"])])

                    # 深夜の翌日は休みが望ましい（ソフト制約 = shinya_off_penalty で対応）
                    # ※ハード制約ではない → 公休9日との両立を可能にする

                # 3連続夜勤禁止（常に厳守）
                # ※深夜→深夜、準夜→準夜、深夜→準夜は2連続まで許可
                for d in range(self.num_days - 2):
                    self.model.AddBoolOr([is_night[s,d].Not(), is_night[s,d+1].Not(), is_night[s,d+2].Not()])

                # 準夜→深夜禁止、遅出→深夜禁止（常に厳守）
                for d in range(self.num_days - 1):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["junnya"])],
                        self.shifts[(s,d+1,SHIFT_IDX["shinya"])].Not()
                    )

                for d in range(self.num_days - 1):
                    self.model.AddImplication(
                        self.shifts[(s,d,SHIFT_IDX["late"])],
                        self.shifts[(s,d+1,SHIFT_IDX["shinya"])].Not()
                    )

                # 夜勤回数上限: 常に <= maxNight（ハード制約）
                night3_list = [self.shifts[(s,d,SHIFT_IDX["junnya"])] for d in range(self.num_days)]
                night3_list += [self.shifts[(s,d,SHIFT_IDX["shinya"])] for d in range(self.num_days)]
                self.model.Add(sum(night3_list) <= max_night)

                # 三交代の最低夜勤回数（ソフト制約）
                min_night = si.get("minNight", 0)
                if min_night > 0:
                    mn_short = self.model.NewIntVar(0, min_night, f"mn_short_3k_{s}")
                    self.model.Add(sum(night3_list) + mn_short >= min_night)
                    staff_shortage_penalty += mn_short * 300

        # 希望休みの日を職員別に収集（後続の夜勤配慮ペナルティで使用）
        # リフレッシュ休暇（refresh）も希望休みと同等に扱う
        kibou_yasumi_days = {}  # {staff_idx: set of 0-indexed day}
        for w in self.wishes:
            sid = w.get("staffId")
            sidx = self.staff_id_to_idx.get(sid)
            if sidx is None:
                continue
            if w.get("type") == "assign" and w.get("shift") in ("off", "refresh", "paid"):
                if sidx not in kibou_yasumi_days:
                    kibou_yasumi_days[sidx] = set()
                for day in w.get("days", []):
                    kibou_yasumi_days[sidx].add(day - 1)  # 0-indexed

        # 前月引き継ぎで強制されるシフトを記録（希望と競合チェック用）
        # {(staff_idx, day_idx): forced_shift_name}
        forced_by_prev = {}
        for s in range(self.num_staff):
            work_type = self.staff_list[s].get("workType", "2kohtai")
            if work_type not in ("2kohtai", "night_only"):
                continue
            staff_id = self.staff_list[s]["id"]
            prev_data = self.prev_month_data.get(staff_id, {})
            last_day = prev_data.get("lastDay", "")
            if last_day == "night2":
                # 当月1日=ake（強制）、2日=off（ake→off強制、2kohtaiのみ）
                forced_by_prev[(s, 0)] = "ake"
                if work_type == "2kohtai":
                    forced_by_prev[(s, 1)] = "off"
            elif last_day == "ake":
                # 当月1日=off（強制）
                forced_by_prev[(s, 0)] = "off"

        # 希望反映（全てハード制約）
        # 不正な希望は事前チェックC/D/Eで弾き済み
        for w in self.wishes:
            sid = w.get("staffId")
            sidx = self.staff_id_to_idx.get(sid)
            if sidx is None:
                continue  # 固定シフト職員の希望は無視
            wt = w.get("type")
            days = w.get("days", [])
            sh = w.get("shift")
            if sh not in SHIFT_IDX:
                continue

            for day in days:
                di = day - 1
                if di < 0 or di >= self.num_days:
                    continue

                if wt == "assign":
                    self.model.Add(self.shifts[(sidx, di, SHIFT_IDX[sh])] == 1)
                elif wt == "avoid":
                    self.model.Add(self.shifts[(sidx, di, SHIFT_IDX[sh])] == 0)

        # 目的関数：夜勤平準化（ソルバー対象職員のみ）
        # maxNight が異なる職員間の公平性のため、稼働率ベースで比較
        # CP-SATは整数のみ: raw_nc * NC_SCALE == nc_rate * max_burden + remainder
        NC_SCALE = 10
        nc_list = []
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "day_only" or wt == "night_only":
                continue
            default_max = 10 if wt == "2kohtai" else 5
            max_night = self.staff_list[s].get("maxNight", default_max)
            if max_night <= 0:
                continue

            if wt == "2kohtai":
                # night2+ake をスロット数としてカウント（maxNightと同じ単位）
                nl = [self.shifts[(s,d,SHIFT_IDX["night2"])] for d in range(self.num_days)]
                al = [self.shifts[(s,d,SHIFT_IDX["ake"])] for d in range(self.num_days)]
                raw_nc = self.model.NewIntVar(0, max_night, f"raw_nc_{s}")
                self.model.Add(raw_nc == sum(nl) + sum(al))
                max_burden = max_night
            elif wt == "3kohtai":
                nl = [self.shifts[(s,d,SHIFT_IDX["junnya"])] for d in range(self.num_days)]
                nl += [self.shifts[(s,d,SHIFT_IDX["shinya"])] for d in range(self.num_days)]
                raw_nc = self.model.NewIntVar(0, max_night, f"raw_nc_{s}")
                self.model.Add(raw_nc == sum(nl))
                max_burden = max_night
            else:
                continue

            nc_rate_upper = NC_SCALE + 1
            nc_rate = self.model.NewIntVar(0, nc_rate_upper, f"nc_rate_{s}")
            remainder = self.model.NewIntVar(0, max_burden - 1, f"nc_rem_{s}")
            self.model.Add(raw_nc * NC_SCALE == nc_rate * max_burden + remainder)
            nc_list.append(nc_rate)

        # 深夜の翌日は可能なら休みにする（ソフト制約）
        shinya_off_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt not in ["3kohtai"]:
                continue

            # リフレッシュ日数に応じてペナルティ軽減
            # 0日→20pt, 1日→12pt, 2日→7pt, 3日以上→3pt
            rc = staff_refresh_days.get(s, 0)
            if rc == 0:
                penalty_weight = 20
            elif rc == 1:
                penalty_weight = 12
            elif rc == 2:
                penalty_weight = 7
            else:
                penalty_weight = 3

            for d in range(self.num_days - 1):
                # 翌日が休みでも深夜連続でもない場合にペナルティ
                # （深夜→深夜は許可されるため、連続中はペナルティ不要）
                # next day is rest or shinya
                rest_or_shinya = self.model.NewBoolVar(f"rest_or_shinya_{s}_{d}")
                self.model.Add(
                    self.shifts[(s,d+1,SHIFT_IDX["off"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["paid"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["refresh"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["shinya"])] >= 1
                ).OnlyEnforceIf(rest_or_shinya)
                self.model.Add(
                    self.shifts[(s,d+1,SHIFT_IDX["off"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["paid"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["refresh"])]
                    + self.shifts[(s,d+1,SHIFT_IDX["shinya"])] == 0
                ).OnlyEnforceIf(rest_or_shinya.Not())

                shinya_and_no_rest = self.model.NewBoolVar(f"shinya_no_rest_pen_{s}_{d}")
                self.model.AddBoolAnd([
                    self.shifts[(s,d,SHIFT_IDX["shinya"])],
                    rest_or_shinya.Not()
                ]).OnlyEnforceIf(shinya_and_no_rest)
                self.model.AddBoolOr([
                    self.shifts[(s,d,SHIFT_IDX["shinya"])].Not(),
                    rest_or_shinya
                ]).OnlyEnforceIf(shinya_and_no_rest.Not())

                shinya_off_penalty += shinya_and_no_rest * penalty_weight

        # 散発夜勤回避
        scattered_night_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")

            if wt == "3kohtai":
                # リフレッシュ日数に応じて散発夜勤ペナルティを軽減
                # 0日→15pt, 1日→10pt, 2日→6pt, 3日以上→3pt
                rc = staff_refresh_days.get(s, 0)
                scattered_w = 15 if rc == 0 else (10 if rc == 1 else (6 if rc == 2 else 3))

                # 月またぎ: shinya(前月末)→rest(day0)→shinya(day1)
                staff_id = self.staff_list[s]["id"]
                if staff_id in self.prev_month_data and self.num_days >= 2:
                    prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                    if prev_last == "shinya":
                        sc_boundary = self.model.NewBoolVar(f"scattered_shinya_boundary_{s}")
                        self.model.AddBoolAnd([
                            is_rest[s, 0],
                            self.shifts[(s, 1, SHIFT_IDX["shinya"])]
                        ]).OnlyEnforceIf(sc_boundary)
                        self.model.AddBoolOr([
                            is_work[s, 0],
                            self.shifts[(s, 1, SHIFT_IDX["shinya"])].Not()
                        ]).OnlyEnforceIf(sc_boundary.Not())
                        scattered_night_penalty += sc_boundary * scattered_w

                for d in range(self.num_days - 2):
                    # 深夜→単体休み（off/refresh/paid）→深夜 の散発パターン
                    scattered = self.model.NewBoolVar(f"scattered_shinya_{s}_{d}")
                    self.model.AddBoolAnd([
                        self.shifts[(s,d,SHIFT_IDX["shinya"])],
                        is_rest[s,d+1],
                        self.shifts[(s,d+2,SHIFT_IDX["shinya"])]
                    ]).OnlyEnforceIf(scattered)
                    self.model.AddBoolOr([
                        self.shifts[(s,d,SHIFT_IDX["shinya"])].Not(),
                        is_work[s,d+1],
                        self.shifts[(s,d+2,SHIFT_IDX["shinya"])].Not()
                    ]).OnlyEnforceIf(scattered.Not())
                    scattered_night_penalty += scattered * scattered_w

        # 準夜→休→深夜パターン回避（体内リズム切替負担）
        junnya_off_shinya_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt != "3kohtai":
                continue
            # リフレッシュ日数に応じて基本ペナルティを軽減
            # 0日→50pt, 1日→35pt, 2日→25pt, 3日以上→12pt
            rc = staff_refresh_days.get(s, 0)
            base_penalty = 50 if rc == 0 else (35 if rc == 1 else (25 if rc == 2 else 12))

            # 月またぎ: junnya(前月末)→rest(day0)→shinya(day1)
            staff_id = self.staff_list[s]["id"]
            if staff_id in self.prev_month_data and self.num_days >= 2:
                prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                if prev_last == "junnya":
                    jos_boundary = self.model.NewBoolVar(f"junnya_off_shinya_boundary_{s}")
                    self.model.AddBoolAnd([
                        is_rest[s, 0],
                        self.shifts[(s, 1, SHIFT_IDX["shinya"])]
                    ]).OnlyEnforceIf(jos_boundary)
                    self.model.AddBoolOr([
                        is_work[s, 0],
                        self.shifts[(s, 1, SHIFT_IDX["shinya"])].Not()
                    ]).OnlyEnforceIf(jos_boundary.Not())
                    if s in kibou_yasumi_days and 0 in kibou_yasumi_days[s]:
                        junnya_off_shinya_penalty += jos_boundary * (base_penalty + 50)
                    else:
                        junnya_off_shinya_penalty += jos_boundary * base_penalty

            for d in range(self.num_days - 2):
                # junnya(d) → 休(d+1) → shinya(d+2)
                pattern = self.model.NewBoolVar(f"junnya_off_shinya_{s}_{d}")
                self.model.AddBoolAnd([
                    self.shifts[(s, d, SHIFT_IDX["junnya"])],
                    is_rest[s, d+1],
                    self.shifts[(s, d+2, SHIFT_IDX["shinya"])]
                ]).OnlyEnforceIf(pattern)
                self.model.AddBoolOr([
                    self.shifts[(s, d, SHIFT_IDX["junnya"])].Not(),
                    is_work[s, d+1],
                    self.shifts[(s, d+2, SHIFT_IDX["shinya"])].Not()
                ]).OnlyEnforceIf(pattern.Not())

                # 希望休みに該当する場合は追加ペナルティ（+50固定）
                if s in kibou_yasumi_days and (d + 1) in kibou_yasumi_days[s]:
                    junnya_off_shinya_penalty += pattern * (base_penalty + 50)
                else:
                    junnya_off_shinya_penalty += pattern * base_penalty

        # 希望休み前後の夜勤配慮（準夜→希望休み or 希望休み→深夜の単独パターン）
        kibou_night_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt != "3kohtai":
                continue
            if s not in kibou_yasumi_days:
                continue
            for ky_day in kibou_yasumi_days[s]:
                # 希望休み前日が準夜（せっかくの休みの前夜が遅くまで勤務）
                prev_day = ky_day - 1
                if prev_day < 0:
                    # 月またぎ: day0が希望休で前月末がjunnyaならペナルティ
                    staff_id = self.staff_list[s]["id"]
                    if staff_id in self.prev_month_data:
                        prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                        if prev_last == "junnya":
                            kibou_night_penalty += 10
                elif prev_day >= 0:
                    junnya_before = self.model.NewBoolVar(f"kibou_junnya_before_{s}_{ky_day}")
                    self.model.Add(
                        self.shifts[(s, prev_day, SHIFT_IDX["junnya"])] == 1
                    ).OnlyEnforceIf(junnya_before)
                    self.model.Add(
                        self.shifts[(s, prev_day, SHIFT_IDX["junnya"])] == 0
                    ).OnlyEnforceIf(junnya_before.Not())
                    kibou_night_penalty += junnya_before * 10

                # 希望休み翌日が深夜（休み明けにいきなり深夜勤務）
                next_day = ky_day + 1
                if next_day < self.num_days:
                    shinya_after = self.model.NewBoolVar(f"kibou_shinya_after_{s}_{ky_day}")
                    self.model.Add(
                        self.shifts[(s, next_day, SHIFT_IDX["shinya"])] == 1
                    ).OnlyEnforceIf(shinya_after)
                    self.model.Add(
                        self.shifts[(s, next_day, SHIFT_IDX["shinya"])] == 0
                    ).OnlyEnforceIf(shinya_after.Not())
                    kibou_night_penalty += shinya_after * 10

        # 日勤帯→深夜ペナルティ（三交代専用: インターバル約7時間で負担大）
        day_shinya_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt != "3kohtai":
                continue

            # 月またぎ: day/late(前月末)→shinya(day0)
            staff_id = self.staff_list[s]["id"]
            if staff_id in self.prev_month_data:
                prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                if prev_last in ("day", "late"):
                    day_shinya_penalty += self.shifts[(s, 0, SHIFT_IDX["shinya"])] * 25

            for d in range(self.num_days - 1):
                # day/late(d) → shinya(d+1)
                is_day_shift = self.model.NewBoolVar(f"is_day_shift_{s}_{d}")
                self.model.AddBoolOr([
                    self.shifts[(s, d, SHIFT_IDX["day"])],
                    self.shifts[(s, d, SHIFT_IDX["late"])]
                ]).OnlyEnforceIf(is_day_shift)
                self.model.AddBoolAnd([
                    self.shifts[(s, d, SHIFT_IDX["day"])].Not(),
                    self.shifts[(s, d, SHIFT_IDX["late"])].Not()
                ]).OnlyEnforceIf(is_day_shift.Not())

                day_then_shinya = self.model.NewBoolVar(f"day_shinya_{s}_{d}")
                self.model.AddBoolAnd([
                    is_day_shift,
                    self.shifts[(s, d+1, SHIFT_IDX["shinya"])]
                ]).OnlyEnforceIf(day_then_shinya)
                self.model.AddBoolOr([
                    is_day_shift.Not(),
                    self.shifts[(s, d+1, SHIFT_IDX["shinya"])].Not()
                ]).OnlyEnforceIf(day_then_shinya.Not())

                day_shinya_penalty += day_then_shinya * 25

        # 好ましいローテーション報酬（深夜→休→準夜、深夜→準夜→休）
        good_rotation_bonus = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt != "3kohtai":
                continue
            # リフレッシュ取得者はボーナス減額（休みが多い分、優遇を控える）
            # 0日→15pt, 1日→10pt, 2日→6pt, 3日以上→3pt
            rc = staff_refresh_days.get(s, 0)
            bonus_w = 15 if rc == 0 else (10 if rc == 1 else (6 if rc == 2 else 3))

            # 月またぎ: shinya(前月末)→rest(day0)→junnya(day1)
            staff_id = self.staff_list[s]["id"]
            if staff_id in self.prev_month_data and self.num_days >= 2:
                prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                if prev_last == "shinya":
                    gr_boundary = self.model.NewBoolVar(f"good_rot_boundary_{s}")
                    self.model.AddBoolAnd([
                        is_rest[s, 0],
                        self.shifts[(s, 1, SHIFT_IDX["junnya"])]
                    ]).OnlyEnforceIf(gr_boundary)
                    self.model.AddBoolOr([
                        is_work[s, 0],
                        self.shifts[(s, 1, SHIFT_IDX["junnya"])].Not()
                    ]).OnlyEnforceIf(gr_boundary.Not())
                    good_rotation_bonus += gr_boundary * bonus_w

            for d in range(self.num_days - 2):
                # 深夜(d) → 休(d+1) → 準夜(d+2)：体内リズムに沿った逆回転
                shinya_off_junnya = self.model.NewBoolVar(f"shinya_off_junnya_{s}_{d}")
                self.model.AddBoolAnd([
                    self.shifts[(s, d, SHIFT_IDX["shinya"])],
                    is_rest[s, d+1],
                    self.shifts[(s, d+2, SHIFT_IDX["junnya"])]
                ]).OnlyEnforceIf(shinya_off_junnya)
                self.model.AddBoolOr([
                    self.shifts[(s, d, SHIFT_IDX["shinya"])].Not(),
                    is_work[s, d+1],
                    self.shifts[(s, d+2, SHIFT_IDX["junnya"])].Not()
                ]).OnlyEnforceIf(shinya_off_junnya.Not())
                good_rotation_bonus += shinya_off_junnya * bonus_w

                # 深夜(d) → 準夜(d+1) → 休(d+2)：段階的にシフトダウン
                shinya_junnya_off = self.model.NewBoolVar(f"shinya_junnya_off_{s}_{d}")
                self.model.AddBoolAnd([
                    self.shifts[(s, d, SHIFT_IDX["shinya"])],
                    self.shifts[(s, d+1, SHIFT_IDX["junnya"])],
                    is_rest[s, d+2]
                ]).OnlyEnforceIf(shinya_junnya_off)
                self.model.AddBoolOr([
                    self.shifts[(s, d, SHIFT_IDX["shinya"])].Not(),
                    self.shifts[(s, d+1, SHIFT_IDX["junnya"])].Not(),
                    is_work[s, d+2]
                ]).OnlyEnforceIf(shinya_junnya_off.Not())
                good_rotation_bonus += shinya_junnya_off * bonus_w

        # 夜勤間隔ペナルティ
        night_interval_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "day_only" or wt == "night_only":
                continue

            if wt == "2kohtai":
                # 月またぎ: 前月末night2との間隔チェック
                staff_id = self.staff_list[s]["id"]
                if staff_id in self.prev_month_data:
                    prev_data = self.prev_month_data[staff_id]
                    prev_last = prev_data.get("lastDay", "")
                    prev_second = prev_data.get("secondLastDay", "")
                    if prev_last == "night2":
                        # day0=ake(強制), day1にnight2なら間隔2→30pt
                        if self.num_days >= 2:
                            night_interval_penalty += self.shifts[(s, 1, SHIFT_IDX["night2"])] * 30
                        # day2にnight2なら間隔3→10pt
                        if self.num_days >= 3:
                            night_interval_penalty += self.shifts[(s, 2, SHIFT_IDX["night2"])] * 10
                    elif prev_second == "night2":
                        # secondLast=night2→last=ake→day0=rest(強制), day1にnight2なら間隔3→10pt
                        if self.num_days >= 2:
                            night_interval_penalty += self.shifts[(s, 1, SHIFT_IDX["night2"])] * 10

                for d in range(self.num_days - 2):
                    close_night = self.model.NewBoolVar(f"close_night2_{s}_{d}")
                    self.model.AddBoolAnd([
                        self.shifts[(s, d, SHIFT_IDX["night2"])],
                        self.shifts[(s, d+2, SHIFT_IDX["night2"])]
                    ]).OnlyEnforceIf(close_night)
                    self.model.AddBoolOr([
                        self.shifts[(s, d, SHIFT_IDX["night2"])].Not(),
                        self.shifts[(s, d+2, SHIFT_IDX["night2"])].Not()
                    ]).OnlyEnforceIf(close_night.Not())
                    night_interval_penalty += close_night * 30

                for d in range(self.num_days - 3):
                    close_night2 = self.model.NewBoolVar(f"close_night2_2d_{s}_{d}")
                    self.model.AddBoolAnd([
                        self.shifts[(s, d, SHIFT_IDX["night2"])],
                        self.shifts[(s, d+3, SHIFT_IDX["night2"])]
                    ]).OnlyEnforceIf(close_night2)
                    self.model.AddBoolOr([
                        self.shifts[(s, d, SHIFT_IDX["night2"])].Not(),
                        self.shifts[(s, d+3, SHIFT_IDX["night2"])].Not()
                    ]).OnlyEnforceIf(close_night2.Not())
                    night_interval_penalty += close_night2 * 10

            elif wt == "3kohtai":
                # 月またぎ: 前月末shinya→当月day0 shinyaの連続夜勤チェック
                staff_id = self.staff_list[s]["id"]
                if staff_id in self.prev_month_data:
                    prev_last = self.prev_month_data[staff_id].get("lastDay", "")
                    # shinya→shinyaのみ発生しうる（ハード制約でshinya→junya/junnya→shinyaは不可）
                    if prev_last == "shinya":
                        night_interval_penalty += self.shifts[(s, 0, SHIFT_IDX["shinya"])] * 20

                night_shifts = ["junnya", "shinya"]
                for d in range(self.num_days - 1):
                    for ns1 in night_shifts:
                        for ns2 in night_shifts:
                            consec_night = self.model.NewBoolVar(f"consec_night_{s}_{d}_{ns1}_{ns2}")
                            self.model.AddBoolAnd([
                                self.shifts[(s, d, SHIFT_IDX[ns1])],
                                self.shifts[(s, d+1, SHIFT_IDX[ns2])]
                            ]).OnlyEnforceIf(consec_night)
                            self.model.AddBoolOr([
                                self.shifts[(s, d, SHIFT_IDX[ns1])].Not(),
                                self.shifts[(s, d+1, SHIFT_IDX[ns2])].Not()
                            ]).OnlyEnforceIf(consec_night.Not())
                            if not (ns1 == "junnya" and ns2 == "junnya"):
                                night_interval_penalty += consec_night * 20

        # 連勤ペナルティ
        consecutive_work_penalty = 0
        for s in range(self.num_staff):
            staff_id = self.staff_list[s]["id"]
            prev_work = 0
            if staff_id in self.prev_month_data:
                prev_work = self.prev_month_data[staff_id].get("consecutiveWork", 0)

            # prev_work >= 5 の特別ブロックは不要
            # （以下の prev_work >= 1 ブロックの days_needed_6 = 6 - prev_work で
            #   prev_work==5 時に days_needed_6=1 → day0勤務で300点ペナルティとなり
            #   重複して600点になるバグを修正）
            if prev_work >= 1:
                # 前月引き継ぎ: 5連勤ペナルティ
                # akeは夜勤の一部であり連勤を途切れさせない
                days_needed_5 = 5 - prev_work
                if days_needed_5 > 0 and days_needed_5 <= self.num_days:
                    work_start = [is_work[s,dd] for dd in range(days_needed_5)]
                    all_5_start = self.model.NewBoolVar(f"all5start_{s}")
                    self.model.AddBoolAnd(work_start).OnlyEnforceIf(all_5_start)
                    self.model.AddBoolOr([w.Not() for w in work_start]).OnlyEnforceIf(all_5_start.Not())
                    consecutive_work_penalty += all_5_start * 150

                # 前月引き継ぎ: 6連勤ペナルティ
                days_needed_6 = 6 - prev_work
                if days_needed_6 > 0 and days_needed_6 <= self.num_days:
                    work_start6 = [is_work[s,dd] for dd in range(days_needed_6)]
                    all_6_start = self.model.NewBoolVar(f"all6start_{s}")
                    self.model.AddBoolAnd(work_start6).OnlyEnforceIf(all_6_start)
                    self.model.AddBoolOr([w.Not() for w in work_start6]).OnlyEnforceIf(all_6_start.Not())
                    consecutive_work_penalty += all_6_start * 300

            for d in range(self.num_days - 4):
                work_5days = [is_work[s,d+dd] for dd in range(5)]
                all_5_work = self.model.NewBoolVar(f"all5work_{s}_{d}")
                self.model.AddBoolAnd(work_5days).OnlyEnforceIf(all_5_work)
                self.model.AddBoolOr([w.Not() for w in work_5days]).OnlyEnforceIf(all_5_work.Not())
                consecutive_work_penalty += all_5_work * 150

            # 6連勤ペナルティ（ソフト制約: 300点）
            for d in range(self.num_days - 5):
                work_6days = [is_work[s,d+dd] for dd in range(6)]
                all_6_work = self.model.NewBoolVar(f"all6work_{s}_{d}")
                self.model.AddBoolAnd(work_6days).OnlyEnforceIf(all_6_work)
                self.model.AddBoolOr([w.Not() for w in work_6days]).OnlyEnforceIf(all_6_work.Not())
                consecutive_work_penalty += all_6_work * 300

        # 遅出均等化（lateシフト有効な病棟のみ）
        late_equalization_penalty = 0
        if shift_restrictions.get("late", True):
            eq_weight = late_config.get("equalizationPenalty", 20)
            if eq_weight > 0:
                late_counts = []
                for s in range(self.num_staff):
                    wt = self.staff_list[s].get("workType", "2kohtai")
                    if wt == "day_only" or wt == "night_only":
                        continue
                    late_cnt = self.model.NewIntVar(0, self.num_days, f"late_cnt_{s}")
                    self.model.Add(late_cnt == sum(self.shifts[(s,d,SHIFT_IDX["late"])] for d in range(self.num_days)))
                    late_counts.append(late_cnt)
                if len(late_counts) >= 2:
                    late_max = self.model.NewIntVar(0, self.num_days, "late_max")
                    late_min = self.model.NewIntVar(0, self.num_days, "late_min")
                    self.model.AddMaxEquality(late_max, late_counts)
                    self.model.AddMinEquality(late_min, late_counts)
                    late_diff = self.model.NewIntVar(0, self.num_days, "late_diff")
                    self.model.Add(late_diff == late_max - late_min)
                    late_equalization_penalty = late_diff * eq_weight

        # 人員不足ペナルティ（希望は全てハード制約のためペナルティ項なし）
        total_violation = self.model.NewIntVar(0, 10000000, "total_vio")
        self.model.Add(total_violation == staff_shortage_penalty)

        # 準夜・深夜バランス
        # nightRestriction が junnya_only / shinya_only の職員は
        # 片方しか入れないためバランス計算から除外
        junnya_shinya_balance_penalty = 0
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt != "3kohtai":
                continue
            restriction = self.staff_list[s].get("nightRestriction", None)
            if restriction in ("junnya_only", "shinya_only"):
                continue

            junnya_count = self.model.NewIntVar(0, self.num_days, f"junnya_cnt_{s}")
            shinya_count = self.model.NewIntVar(0, self.num_days, f"shinya_cnt_{s}")
            self.model.Add(junnya_count == sum(self.shifts[(s,d,SHIFT_IDX["junnya"])] for d in range(self.num_days)))
            self.model.Add(shinya_count == sum(self.shifts[(s,d,SHIFT_IDX["shinya"])] for d in range(self.num_days)))

            diff = self.model.NewIntVar(-self.num_days, self.num_days, f"js_diff_{s}")
            abs_diff = self.model.NewIntVar(0, self.num_days, f"js_abs_diff_{s}")
            self.model.Add(diff == junnya_count - shinya_count)
            self.model.AddAbsEquality(abs_diff, diff)

            junnya_shinya_balance_penalty += abs_diff * 10

            mid_day = self.num_days // 2

            junnya_first_half = self.model.NewIntVar(0, mid_day, f"junnya_1st_{s}")
            shinya_first_half = self.model.NewIntVar(0, mid_day, f"shinya_1st_{s}")
            self.model.Add(junnya_first_half == sum(self.shifts[(s,d,SHIFT_IDX["junnya"])] for d in range(mid_day)))
            self.model.Add(shinya_first_half == sum(self.shifts[(s,d,SHIFT_IDX["shinya"])] for d in range(mid_day)))

            junnya_second_half = self.model.NewIntVar(0, self.num_days - mid_day, f"junnya_2nd_{s}")
            shinya_second_half = self.model.NewIntVar(0, self.num_days - mid_day, f"shinya_2nd_{s}")
            self.model.Add(junnya_second_half == sum(self.shifts[(s,d,SHIFT_IDX["junnya"])] for d in range(mid_day, self.num_days)))
            self.model.Add(shinya_second_half == sum(self.shifts[(s,d,SHIFT_IDX["shinya"])] for d in range(mid_day, self.num_days)))

            diff_1st = self.model.NewIntVar(-mid_day, mid_day, f"js_diff_1st_{s}")
            abs_diff_1st = self.model.NewIntVar(0, mid_day, f"js_abs_1st_{s}")
            self.model.Add(diff_1st == junnya_first_half - shinya_first_half)
            self.model.AddAbsEquality(abs_diff_1st, diff_1st)

            diff_2nd = self.model.NewIntVar(-self.num_days, self.num_days, f"js_diff_2nd_{s}")
            abs_diff_2nd = self.model.NewIntVar(0, self.num_days, f"js_abs_2nd_{s}")
            self.model.Add(diff_2nd == junnya_second_half - shinya_second_half)
            self.model.AddAbsEquality(abs_diff_2nd, diff_2nd)

            junnya_shinya_balance_penalty += (abs_diff_1st + abs_diff_2nd) * 15

        # 週末勤務平準化
        weekend_equalization_penalty = 0
        weekend_work_counts = []
        for s in range(self.num_staff):
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "day_only" or wt == "night_only":
                continue
            wk_cnt = self.model.NewIntVar(0, self.num_days, f"wkend_cnt_{s}")
            wk_vars = []
            for d in range(self.num_days):
                dt_obj = date(self.year, self.month, d + 1)
                if dt_obj.weekday() >= 5 or (self.year, self.month, d + 1) in HOLIDAYS:
                    is_wk_work = self.model.NewBoolVar(f"wkw_{s}_{d}")
                    self.model.AddBoolAnd([
                        self.shifts[(s,d,SHIFT_IDX["off"])].Not(),
                        self.shifts[(s,d,SHIFT_IDX["paid"])].Not(),
                        self.shifts[(s,d,SHIFT_IDX["ake"])].Not(),
                        self.shifts[(s,d,SHIFT_IDX["refresh"])].Not()
                    ]).OnlyEnforceIf(is_wk_work)
                    self.model.AddBoolOr([
                        self.shifts[(s,d,SHIFT_IDX["off"])],
                        self.shifts[(s,d,SHIFT_IDX["paid"])],
                        self.shifts[(s,d,SHIFT_IDX["ake"])],
                        self.shifts[(s,d,SHIFT_IDX["refresh"])]
                    ]).OnlyEnforceIf(is_wk_work.Not())
                    wk_vars.append(is_wk_work)
            if wk_vars:
                self.model.Add(wk_cnt == sum(wk_vars))
                weekend_work_counts.append(wk_cnt)

        if len(weekend_work_counts) >= 2:
            wk_max = self.model.NewIntVar(0, self.num_days, "wk_max")
            wk_min = self.model.NewIntVar(0, self.num_days, "wk_min")
            self.model.AddMaxEquality(wk_max, weekend_work_counts)
            self.model.AddMinEquality(wk_min, weekend_work_counts)
            wk_diff = self.model.NewIntVar(0, self.num_days, "wk_diff")
            self.model.Add(wk_diff == wk_max - wk_min)
            weekend_equalization_penalty = wk_diff * 40

        # 目的関数
        if nc_list:
            mx = self.model.NewIntVar(0, NC_SCALE + 1, "mx")
            mn = self.model.NewIntVar(0, NC_SCALE + 1, "mn")
            self.model.AddMaxEquality(mx, nc_list)
            self.model.AddMinEquality(mn, nc_list)

            # 夜勤レンジ段階的ペナルティ（レンジが大きいほど急激に増加）
            night_range_diff = self.model.NewIntVar(0, NC_SCALE + 1, "night_range_diff")
            self.model.Add(night_range_diff == mx - mn)
            night_range_penalty = 0
            # 段階ペナルティ: 夜勤差を強く抑制（日勤不足500pt/日より重い）
            thresholds = [(1, 200), (2, 500), (3, 800), (4, 1000), (5, 1500)]
            for thr, pen in thresholds:
                exceeded = self.model.NewBoolVar(f"night_range_ge_{thr}")
                self.model.Add(night_range_diff >= thr).OnlyEnforceIf(exceeded)
                self.model.Add(night_range_diff < thr).OnlyEnforceIf(exceeded.Not())
                night_range_penalty += exceeded * pen

            self.model.Minimize(
                total_violation
                + night_range_penalty
                + consecutive_work_penalty
                + weekend_equalization_penalty
                + night_interval_penalty
                + junnya_shinya_balance_penalty
                + late_equalization_penalty
                + scattered_night_penalty
                + shinya_off_penalty
                + junnya_off_shinya_penalty
                + kibou_night_penalty
                + day_shinya_penalty
                - good_rotation_bonus
            )
        else:
            self.model.Minimize(
                total_violation + consecutive_work_penalty
                + weekend_equalization_penalty + late_equalization_penalty
                + scattered_night_penalty + night_interval_penalty + shinya_off_penalty
                + junnya_off_shinya_penalty + kibou_night_penalty + day_shinya_penalty
                - good_rotation_bonus
            )

        solver = cp_model.CpSolver()

        # OR-Tools 最適化フラグ
        solver.parameters.log_search_progress = not self.config.get("_quiet", False)
        solver.parameters.symmetry_level = 2
        solver.parameters.linearization_level = 2
        solver.parameters.cp_model_presolve = True
        solver.parameters.enumerate_all_solutions = False
        solver.parameters.interleave_search = True
        solver.parameters.use_lns_only = False
        solver.parameters.max_presolve_iterations = 3

        # 全コア使用
        num_cores = os.cpu_count() or 4
        solver.parameters.num_search_workers = num_cores

        # タイムアウト: 各試行の秒数（デフォルト15秒、試行回数はsolve()で制御）
        solver.parameters.max_time_in_seconds = timeout

        seed = self.config.get("seed", 0)
        if seed > 0:
            solver.parameters.random_seed = seed

        # コールバック付きで実行（進捗グラフ用）
        callback = SolutionCallback(log_queue=log_queue)
        status = solver.Solve(self.model, callback)

        is_optimal = (status == cp_model.OPTIMAL)
        is_feasible = (status == cp_model.FEASIBLE)
        result = {
            "status": solver.StatusName(status),
            "completeness": "optimal" if is_optimal else ("feasible" if is_feasible else "none"),
            "shifts": {},
            "stats": {
                "solveTime": solver.WallTime()
            },
            "violations": []
        }

        if is_optimal or is_feasible:
            if nc_list:
                violation_score = solver.Value(total_violation)
                night_diff = solver.Value(mx - mn)
                # 段階的ペナルティと同じ計算方法でnight_scoreを算出
                _thresholds = [(1, 200), (2, 500), (3, 800), (4, 1000), (5, 1500)]
                night_score = sum(pen for thr, pen in _thresholds if night_diff >= thr)

                result["optimization_score"] = {
                    "total_violation": violation_score,
                    "night_diff": night_diff,
                    "night_score": night_score,
                    "objective_value": solver.ObjectiveValue()
                }
        else:
            result["status"] = "infeasible"
            causes = self._diagnose_infeasible()
            if causes:
                result["message"] = "解が見つかりません。\n\n" + "\n\n".join(causes)
            else:
                result["message"] = "解が見つかりません。職員数・公休日数・必要人数の設定を確認してください。"
            return result

        # ソルバー対象職員のシフトを取得
        for s in range(self.num_staff):
            sid = self.staff_list[s]["id"]
            for d in range(self.num_days):
                for t in range(len(SHIFTS)):
                    if solver.Value(self.shifts[(s,d,t)]) == 1:
                        result["shifts"][sid + "-" + str(d+1)] = SHIFTS[t]

        # 固定シフト職員のシフトを追加（パターンから直接生成）
        for s in self.fixed_staff:
            for d in range(1, self.num_days + 1):
                sh = self._get_fixed_shift(s, d)
                result["shifts"][s["id"] + "-" + str(d)] = sh

        # flexRequest職員のシフトを追加（手動入力分）
        for s in self.flex_staff:
            staff_id = s["id"]
            for d in range(1, self.num_days + 1):
                key = f"{staff_id}-{d}"
                if key in self.locked_shifts:
                    result["shifts"][key] = self.locked_shifts[key]
                elif staff_id in self.locked_shifts and isinstance(self.locked_shifts[staff_id], dict):
                    shift = self.locked_shifts[staff_id].get(str(d)) or self.locked_shifts[staff_id].get(d)
                    if shift:
                        result["shifts"][key] = shift

        # 人員不足違反を検出
        violations = []
        for si in staff_shortage_info:
            if solver.Value(si["var"]) > 0:
                shortage_val = solver.Value(si["var"])
                violations.append({
                    "name": "全体",
                    "day": si["day"],
                    "type": f"{si['type']}人数不足({shortage_val}名)"
                })

        # 希望逸脱チェック
        _rest_shifts = {"off", "paid", "refresh"}
        for w in self.wishes:
            if w.get("type") != "assign":
                continue
            sid = w.get("staffId")
            sidx = self.staff_id_to_idx.get(sid)
            if sidx is None:
                continue
            sh = w.get("shift")
            staff_name = self.staff_list[sidx].get("name", sid)
            for day in w.get("days", []):
                if day < 1 or day > self.num_days:
                    continue
                key = f"{sid}-{day}"
                actual = result["shifts"].get(key, "")
                if actual == sh:
                    continue
                # 休み系同士は逸脱とみなさない（off希望→paid等はOK）
                if sh in _rest_shifts and actual in _rest_shifts:
                    continue
                violations.append({
                    "name": staff_name,
                    "staffId": sid,
                    "day": day,
                    "type": f"希望{sh}→実際{actual}",
                })

        result["violations"] = violations

        # 公休数デバッグ検証（off + paid が monthlyOff と一致すべき）
        off_debug = []
        monthly_off_val = self.config.get("monthlyOff", 9)
        for s in range(self.num_staff):
            sid = self.staff_list[s]["id"]
            sname = self.staff_list[s]["name"]
            off_c = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["off"])]) == 1)
            paid_c = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["paid"])]) == 1)
            refresh_c = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["refresh"])]) == 1)
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "night_only":
                # 夜勤専従は公休数の基準が異なるためチェック対象外
                mark = " (専従)"
            else:
                mark = " ✗" if off_c != monthly_off_val else " ✓"
            off_debug.append(f"{sname}: off={off_c}{mark} paid={paid_c} ref={refresh_c}")
        result["offDebug"] = off_debug

        # 夜勤統計（ソルバー対象職員のみ）
        nps = {}
        for s in range(self.num_staff):
            nm = self.staff_list[s]["name"]
            wt = self.staff_list[s].get("workType", "2kohtai")
            if wt == "2kohtai":
                n2_cnt = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["night2"])]) == 1)
                ake_cnt = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["ake"])]) == 1)
                nps[nm] = str(n2_cnt + ake_cnt) + "pt (" + str(n2_cnt) + "回)"
            elif wt == "3kohtai":
                cnt = sum(1 for d in range(self.num_days) for ns in ["junnya","shinya"] if solver.Value(self.shifts[(s,d,SHIFT_IDX[ns])]) == 1)
                nps[nm] = str(cnt) + "pt (" + str(cnt) + "回)"
            elif wt == "night_only":
                cnt = sum(1 for d in range(self.num_days) if solver.Value(self.shifts[(s,d,SHIFT_IDX["night2"])]) == 1)
                nps[nm] = "専従 " + str(cnt) + "回"
            else:
                nps[nm] = "0pt"

        # 固定シフト職員は統計から除外（表示しない）

        result["stats"] = {"solveTime": round(solver.WallTime(), 2), "nightPerStaff": nps}
        return result

    def solve(self, log_queue=None):
        debug_log = []
        debug_log.append(f"Staff: {self.num_staff} (solver), {len(self.fixed_staff)} (fixed), {len(self.flex_staff)} (flex), Days: {self.num_days}")
        wt_counts = {}
        for s in self.staff_list:
            wt = s.get("workType", "unknown")
            wt_counts[wt] = wt_counts.get(wt, 0) + 1
        debug_log.append(f"Types: {wt_counts}")
        cfg = self.config
        debug_log.append(f"Config: ward={cfg.get('ward')}, reqLate={cfg.get('reqLate')}, reqJ={cfg.get('reqJunnya')}, reqS={cfg.get('reqShinya')}, monthlyOff={cfg.get('monthlyOff')}")

        # 複数seed試行でobj最小化（常に3回×15秒固定）
        seeds = [7, 31, 97]
        n = 3

        best_res = None
        best_obj = None
        for i, seed in enumerate(seeds[:n]):
            self.config["seed"] = seed
            if log_queue:
                log_queue.put({'type': 'log', 'msg': f'試行{i+1}/{n} (seed={seed})'})

            res = self._solve_core(log_queue=log_queue)
            status = res["status"].lower()
            debug_log.append(f"試行{i+1}(seed={seed}): {res['status']}")

            if status in ["optimal", "feasible"]:
                obj = res.get("optimization_score", {}).get("objective_value")
                if best_res is None or (obj is not None and (best_obj is None or obj < best_obj)):
                    best_res = res
                    best_obj = obj
                    best_attempt = i + 1
                if status == "optimal":
                    break  # 最適解確定、これ以上改善しない
            else:
                # infeasible/事前チェックエラーは即return
                if res.get("message"):
                    res["debug_log"] = debug_log
                    res["attempt"] = i + 1
                    return res
                if best_res is None:
                    best_res = res

        res = best_res
        res["debug_log"] = debug_log
        res["attempt"] = best_attempt if best_obj is not None else n

        if res["status"].lower() not in ["optimal", "feasible"]:
            if not res.get("message"):
                debug_info = " / ".join(debug_log)
                res["message"] = f"失敗: 解が見つかりません。職員数・公休日数・必要人数の設定を確認してください。[{debug_info}]"

        return res
