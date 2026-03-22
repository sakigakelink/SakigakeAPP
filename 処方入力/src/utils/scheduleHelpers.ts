import type { DosingSchedule, TimeSlot, MealTiming, Frequency } from '../types/prescription';
import { findUsagePreset } from '../data/usageMaster';

export const SLOT_ORDER: TimeSlot[] = ['morning', 'noon', 'evening', 'bedtime'];

export const SLOT_LABELS: Record<TimeSlot, string> = {
  morning: '朝',
  noon: '昼',
  evening: '夕',
  bedtime: '寝る前',
};

export const MEAL_TIMING_LABELS: Record<MealTiming, string> = {
  after: '食後',
  before: '食前',
  justBefore: '食直前',
  between: '食間',
  wakeup: '起床時',
};

const FREQUENCY_LABELS: Record<Frequency, string> = {
  daily: '',
  everyOtherDay: '隔日',
  weekly: '週1回',
};

function frequencySuffix(frequency: Frequency): string {
  const label = FREQUENCY_LABELS[frequency];
  return label ? ` ${label}` : '';
}

/** スロット+タイミング+頻度からラベル生成 */
function formatSlotsLabel(slots: TimeSlot[], mealTiming: MealTiming, frequency: Frequency): string {
  const sorted = [...slots].sort(
    (a, b) => SLOT_ORDER.indexOf(a) - SLOT_ORDER.indexOf(b)
  );
  const hasBedtime = sorted.includes('bedtime');
  const mealSlots = sorted.filter((s) => s !== 'bedtime');
  const freq = frequencySuffix(frequency);

  if (mealTiming === 'wakeup') {
    return `起床時${freq}`;
  }

  if (mealSlots.length === 0 && hasBedtime) {
    return `寝る前${freq}`;
  }

  const timingLabel = MEAL_TIMING_LABELS[mealTiming];

  if (
    mealSlots.length === 3 &&
    mealSlots.includes('morning') &&
    mealSlots.includes('noon') &&
    mealSlots.includes('evening')
  ) {
    const base = `毎${timingLabel}`;
    return hasBedtime ? `${base}＋寝る前${freq}` : `${base}${freq}`;
  }

  const slotPart = mealSlots.map((s) => SLOT_LABELS[s]).join('');
  const base = `${slotPart}${timingLabel}`;
  return hasBedtime ? `${base}＋寝る前${freq}` : `${base}${freq}`;
}

/** 用法を正規化キー文字列に変換（グルーピング用） */
export function normalizeScheduleKey(schedule: DosingSchedule): string {
  if (schedule.mode === 'pediatric') {
    return `pediatric|${schedule.timesPerDay}`;
  }
  if (schedule.mode === 'prn') {
    return `prn|${schedule.condition}`;
  }
  if (schedule.mode === 'custom') {
    // 不均等: アクティブスロットから用法キーを生成（standard と同一形式）
    // → 同じスロット構成の standard エントリと同一 Rp にグルーピングされる
    const sorted = Object.entries(schedule.slotDoses)
      .filter(([, count]) => count && count > 0)
      .sort(([a], [b]) => SLOT_ORDER.indexOf(a as TimeSlot) - SLOT_ORDER.indexOf(b as TimeSlot))
      .map(([slot]) => slot);
    return `${sorted.join(',')}|after|daily`;
  }
  // standard
  const sorted = [...schedule.slots].sort(
    (a, b) => SLOT_ORDER.indexOf(a) - SLOT_ORDER.indexOf(b)
  );
  return `${sorted.join(',')}|${schedule.mealTiming}|${schedule.frequency}`;
}

/** 用法の1日投与回数を算出 */
export function getDosesPerDay(schedule: DosingSchedule): number {
  if (schedule.mode === 'pediatric') return schedule.timesPerDay;
  if (schedule.mode === 'prn') return 0;
  if (schedule.mode === 'custom') {
    return Object.values(schedule.slotDoses).filter((c) => c && c > 0).length;
  }
  return schedule.slots.length;
}

/** 用法を日本語ラベルに変換 */
export function formatScheduleLabel(schedule: DosingSchedule): string {
  if (schedule.mode === 'pediatric') {
    const slotsLabel = schedule.slots.length > 0
      ? formatSlotsLabel(schedule.slots, 'after', 'daily')
      : `分${schedule.timesPerDay}`;
    return `${schedule.dosePerKg}mg/kg/日 ${slotsLabel}（${schedule.bodyWeight}kg）`;
  }
  if (schedule.mode === 'prn') {
    return schedule.condition;
  }

  if (schedule.mode === 'custom') {
    // アクティブスロットから用法ラベルを自動生成（食後固定）
    const activeSlots = Object.entries(schedule.slotDoses)
      .filter(([, c]) => c && c > 0)
      .sort(([a], [b]) => SLOT_ORDER.indexOf(a as TimeSlot) - SLOT_ORDER.indexOf(b as TimeSlot));
    const slots = activeSlots.map(([s]) => s as TimeSlot);
    const baseLabel = formatSlotsLabel(slots, 'after', 'daily');
    const dosePart = activeSlots.map(([slot, count]) => `${SLOT_LABELS[slot as TimeSlot]}${count}`).join('-');
    return `${baseLabel}(${dosePart})`;
  }

  // standard: 用法マスタのラベルを使用
  const preset = findUsagePreset(schedule.usageId);
  if (preset) return preset.label;
  return formatSlotsLabel(schedule.slots, schedule.mealTiming, schedule.frequency);
}

/** カスタム成形用: 単一スロットのラベル生成 */
export function formatSingleSlotLabel(slot: TimeSlot, mealTiming: MealTiming, frequency: Frequency): string {
  let label: string;
  if (slot === 'bedtime') {
    label = '寝る前';
  } else if (mealTiming === 'wakeup') {
    label = '起床時';
  } else {
    label = `${SLOT_LABELS[slot]}${MEAL_TIMING_LABELS[mealTiming]}`;
  }
  return label + frequencySuffix(frequency);
}
