// constants.js - 定数定義
export var ABBR = { day: "日", late: "遅", night2: "夜", junnya: "準", shinya: "深", off: "休", paid: "有", ake: "明", refresh: "リ" };
export var WARDS = [{ id: "1", name: "一病棟" }, { id: "2", name: "二病棟" }, { id: "3", name: "三病棟" }];
export var WORK_TYPES = { day_only: "日勤のみ", "2kohtai": "二交代", "3kohtai": "三交代", night_only: "夜勤専従", fixed: "固定シフト" };
export var SHIFT_BTNS = [
    { shift: "day", label: "日勤", cls: "shift-day" },
    { shift: "late", label: "遅出", cls: "shift-late" },
    { shift: "night2", label: "夜勤", cls: "shift-night2" },
    { shift: "junnya", label: "準夜", cls: "shift-junnya" },
    { shift: "shinya", label: "深夜", cls: "shift-shinya" },
    { shift: "off", label: "休み", cls: "shift-off" },
    { shift: "paid", label: "有給", cls: "shift-paid" },
    { shift: "ake", label: "明け", cls: "shift-ake" },
    { shift: "refresh", label: "リフレッシュ", cls: "shift-refresh" },
    { shift: "", label: "クリア", cls: "btn-secondary" }
];
export var PENALTY_KEYS = [
    "consec_5", "consec_6", "night_interval_close",
    "shinya_no_rest", "scattered_night", "junnya_off_shinya",
    "day_to_shinya", "kibou_night", "junnya_shinya_balance"
];
