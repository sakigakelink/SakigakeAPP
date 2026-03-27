// === 剤型 ===
export type FormType = 'tablet' | 'capsule' | 'powder' | 'liquid';
export type FormSymbol = 'T' | 'C' | 'g' | 'mL';

// === 薬剤マスタ ===
export interface DrugStrength {
  value: number;   // 規格値
  price: number;   // 薬価（円）
}

export interface DrugMasterEntry {
  id: string;
  name: string;           // 商品名
  genericName: string;    // 一般名
  category: string;       // 薬効分類
  strengths: DrugStrength[];  // 利用可能規格+薬価
  unit: string;           // 規格の単位 "mg", "μg"
  inputUnit: string;      // 入力単位 "mg"(錠剤/カプセル), "g"(散剤), "mL"(液剤)
  formType: FormType;
  formSymbol: FormSymbol;
  maxDailyDose?: number;  // 1日最大量 (unit単位, 錠剤ならmg)
  defaultUsageId?: string; // 添付文書ベースのデフォルト用法（usageMasterのID）
}

// === 用法 ===
export type TimeSlot = 'morning' | 'noon' | 'evening' | 'bedtime';
export type MealTiming = 'after' | 'before' | 'justBefore' | 'between' | 'wakeup';
export type Frequency = 'daily' | 'everyOtherDay' | 'weekly';

// 用法マスタエントリ
export interface UsagePreset {
  id: string;
  label: string;
  category: string;
  slots: TimeSlot[];
  mealTiming: MealTiming;
  frequency: Frequency;
  isQuick?: boolean;  // プリセットボタンに表示するか
}

// ノーマル: 用法マスタから選択、均等投与
export interface StandardSchedule {
  mode: 'standard';
  usageId: string;
  slots: TimeSlot[];
  mealTiming: MealTiming;
  frequency: Frequency;
}

// カスタム: 4スロット固定、スロット別錠数入力、用法は自動決定
export interface CustomSchedule {
  mode: 'custom';
  slotDoses: Partial<Record<TimeSlot, number>>;
}

// 屯用
export interface PrnSchedule {
  mode: 'prn';
  condition: string;
}

// 小児用量（mg/kg）
export interface PediatricSchedule {
  mode: 'pediatric';
  dosePerKg: number;       // mg/kg/日
  bodyWeight: number;       // 体重 kg
  timesPerDay: number;      // 投与回数（分N）
  slots: TimeSlot[];        // 投与タイミング（朝食後/昼食後/夕食後/寝る前）
}

export type DosingSchedule = StandardSchedule | CustomSchedule | PrnSchedule | PediatricSchedule;

// === 用量構造（モード共通） ===
export interface ResolvedDose {
  perDose: number;        // 1回量（錠数 or g数）。不均等時は0
  timesPerDay: number;    // 1日回数（頓用=0）
  dailyTotal: number;     // 1日総量（錠数 or g数）。頓用=0
  dailyDoseMg: number;    // 1日総量（mg換算）。頓用=1回量mg
  isUneven: boolean;      // 不均等フラグ
  slotDoses?: Partial<Record<TimeSlot, number>>;  // 不均等時のスロット別1回量
}

// === プールエントリ ===
export interface PoolEntry {
  id: string;
  drug: DrugMasterEntry;
  selectedStrength: number; // 選択された規格
  dose: ResolvedDose;       // 用量構造
  schedule: DosingSchedule;
}

// === 処方区分 ===
export type PrescriptionMode = 'inpatient' | 'outpatient';

export interface PrescriptionContext {
  mode: PrescriptionMode;
  startDate: string;        // YYYY-MM-DD
  startTimeSlot: TimeSlot;  // 開始タイミング（入院/外来共通）
  endDate?: string;         // 外来/臨時: YYYY-MM-DD
  endTimeSlot?: TimeSlot;   // 外来/臨時: 終了タイミング
}

// === 成形結果 ===
export interface StandardizedDrug {
  drugName: string;
  selectedStrength: number;
  unitPrice: number;        // 1単位あたり薬価（円）
  perDose: number;          // 1回量（錠数/g数）。不均等時は0
  dailyCount: number;       // 1日合計数（錠数/g数）。PRNは0
  formSymbol: FormSymbol;
  formType: FormType;
  isUneven: boolean;        // 不均等フラグ
  slotDoses?: Partial<Record<TimeSlot, number>>;  // 不均等時のスロット別1回量
  warning?: string;
}

export interface RpGroup {
  rpNumber: number;
  drugs: StandardizedDrug[];
  dosesPerDay: number;     // PRNは0
  scheduleLabel: string;
  isPrn: boolean;
  dailyCost: number;       // Rp単位の1日薬価合計（円）
}

/** 一包化用: スロット別錠数サマリー */
export interface SlotSummary {
  morning: number;
  noon: number;
  evening: number;
  bedtime: number;
}
