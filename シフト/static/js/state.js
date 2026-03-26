// state.js - 共有ミュータブル状態
export var HOLIDAYS = {};
export var D = { staff: [], shifts: {}, wishes: {}, shiftVersions: {}, wardSettings: {}, shiftCreationNum: {}, dayHours: {} };
var _now = new Date();
export var Y = _now.getMonth() === 11 ? _now.getFullYear() + 1 : _now.getFullYear();
export var M = _now.getMonth() === 11 ? 1 : _now.getMonth() + 2;
export var W = "2";
export var sel = null;
export var currentViewDraft = null;
export var solveTimer = null;
export var solveStartTime = null;
export var solveChartData = [];
export var solveAttemptNum = 0;
export var backupTimer = null;
export var isShuttingDown = false;
export var _solveRetryCount = 0;
export var _solveMaxRetry = 3;
export var ACTUAL_MODE = false;
export var actualData = {};
export var confirmedData = {};
export var pendingActualChange = null;
export var wishDragState = { active: false, mode: null };
export var wishDragChip = null;
export var wishDragMoved = false;
export var wishQueue = [];
export var draggedId = null;

// setter functions for reassigning exported vars
export function setD(v) { D = v; }
export function setY(v) { Y = v; }
export function setM(v) { M = v; }
export function setW(v) { W = v; }
export function setSel(v) { sel = v; }
export function setCurrentViewDraft(v) { currentViewDraft = v; }
export function setSolveTimer(v) { solveTimer = v; }
export function setSolveStartTime(v) { solveStartTime = v; }
export function setSolveChartData(v) { solveChartData = v; }
export function setSolveAttemptNum(v) { solveAttemptNum = v; }
export function setBackupTimer(v) { backupTimer = v; }
export function setIsShuttingDown(v) { isShuttingDown = v; }
export function set_solveRetryCount(v) { _solveRetryCount = v; }
export function setACTUAL_MODE(v) { ACTUAL_MODE = v; }
export function setActualData(v) { actualData = v; }
export function setConfirmedData(v) { confirmedData = v; }
export function setPendingActualChange(v) { pendingActualChange = v; }
export function setWishDragState(v) { wishDragState = v; }
export function setWishDragChip(v) { wishDragChip = v; }
export function setWishDragMoved(v) { wishDragMoved = v; }
export function setWishQueue(v) { wishQueue = v; }
export function setDraggedId(v) { draggedId = v; }
export function setHOLIDAYS(v) { HOLIDAYS = v; }
