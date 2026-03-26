import type { UsagePreset } from '../types/prescription';

export const USAGE_PRESETS: UsagePreset[] = [
  // ==================== 食後 ====================
  { id: 'tid-after',       label: '毎食後',             category: '食後', slots: ['morning', 'noon', 'evening'],             mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'bid-am-pm-after', label: '朝夕食後',           category: '食後', slots: ['morning', 'evening'],                     mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'qd-am-after',    label: '朝食後',              category: '食後', slots: ['morning'],                                mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'qd-pm-after',    label: '夕食後',              category: '食後', slots: ['evening'],                                mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'qd-noon-after',  label: '昼食後',              category: '食後', slots: ['noon'],                                   mealTiming: 'after', frequency: 'daily' },
  { id: 'bid-am-noon-after', label: '朝昼食後',         category: '食後', slots: ['morning', 'noon'],                        mealTiming: 'after', frequency: 'daily' },
  { id: 'bid-noon-pm-after', label: '昼夕食後',         category: '食後', slots: ['noon', 'evening'],                        mealTiming: 'after', frequency: 'daily' },
  { id: 'tid-after-hs',   label: '毎食後＋寝る前',      category: '食後', slots: ['morning', 'noon', 'evening', 'bedtime'],  mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'bid-am-pm-after-hs', label: '朝夕食後＋寝る前', category: '食後', slots: ['morning', 'evening', 'bedtime'],         mealTiming: 'after', frequency: 'daily' },
  { id: 'qd-am-after-hs', label: '朝食後＋寝る前',      category: '食後', slots: ['morning', 'bedtime'],                    mealTiming: 'after', frequency: 'daily' },
  { id: 'qd-pm-after-hs', label: '夕食後＋寝る前',      category: '食後', slots: ['evening', 'bedtime'],                    mealTiming: 'after', frequency: 'daily' },

  // ==================== 食前 ====================
  { id: 'tid-before',       label: '毎食前',             category: '食前', slots: ['morning', 'noon', 'evening'],            mealTiming: 'before', frequency: 'daily', isQuick: true },
  { id: 'qd-am-before',    label: '朝食前',              category: '食前', slots: ['morning'],                               mealTiming: 'before', frequency: 'daily' },
  { id: 'qd-pm-before',    label: '夕食前',              category: '食前', slots: ['evening'],                               mealTiming: 'before', frequency: 'daily' },
  { id: 'qd-noon-before',  label: '昼食前',              category: '食前', slots: ['noon'],                                  mealTiming: 'before', frequency: 'daily' },
  { id: 'bid-am-pm-before', label: '朝夕食前',           category: '食前', slots: ['morning', 'evening'],                    mealTiming: 'before', frequency: 'daily' },
  { id: 'bid-am-noon-before', label: '朝昼食前',         category: '食前', slots: ['morning', 'noon'],                       mealTiming: 'before', frequency: 'daily' },

  // ==================== 食直前 ====================
  { id: 'tid-justBefore',     label: '毎食直前',         category: '食直前', slots: ['morning', 'noon', 'evening'],          mealTiming: 'justBefore', frequency: 'daily' },
  { id: 'qd-am-justBefore',  label: '朝食直前',          category: '食直前', slots: ['morning'],                             mealTiming: 'justBefore', frequency: 'daily' },
  { id: 'qd-pm-justBefore',  label: '夕食直前',          category: '食直前', slots: ['evening'],                             mealTiming: 'justBefore', frequency: 'daily' },
  { id: 'qd-noon-justBefore', label: '昼食直前',         category: '食直前', slots: ['noon'],                                mealTiming: 'justBefore', frequency: 'daily' },
  { id: 'bid-am-pm-justBefore', label: '朝夕食直前',     category: '食直前', slots: ['morning', 'evening'],                  mealTiming: 'justBefore', frequency: 'daily' },

  // ==================== 食間 ====================
  { id: 'tid-between',       label: '毎食間',            category: '食間', slots: ['morning', 'noon', 'evening'],            mealTiming: 'between', frequency: 'daily' },
  { id: 'bid-am-pm-between', label: '朝夕食間',          category: '食間', slots: ['morning', 'evening'],                    mealTiming: 'between', frequency: 'daily' },
  { id: 'qd-am-between',    label: '朝食間',             category: '食間', slots: ['morning'],                               mealTiming: 'between', frequency: 'daily' },
  { id: 'qd-noon-between',  label: '昼食間',             category: '食間', slots: ['noon'],                                  mealTiming: 'between', frequency: 'daily' },
  { id: 'qd-pm-between',    label: '夕食間',             category: '食間', slots: ['evening'],                               mealTiming: 'between', frequency: 'daily' },

  // ==================== その他 ====================
  { id: 'hs',     label: '寝る前',   category: 'その他', slots: ['bedtime'],  mealTiming: 'after', frequency: 'daily', isQuick: true },
  { id: 'wakeup', label: '起床時',   category: 'その他', slots: ['morning'],  mealTiming: 'wakeup', frequency: 'daily' },

  // ==================== 隔日 ====================
  { id: 'qd-am-after-eod',     label: '朝食後 隔日',     category: '隔日', slots: ['morning'],                              mealTiming: 'after', frequency: 'everyOtherDay' },
  { id: 'qd-pm-after-eod',     label: '夕食後 隔日',     category: '隔日', slots: ['evening'],                              mealTiming: 'after', frequency: 'everyOtherDay' },
  { id: 'bid-am-pm-after-eod', label: '朝夕食後 隔日',   category: '隔日', slots: ['morning', 'evening'],                   mealTiming: 'after', frequency: 'everyOtherDay' },
  { id: 'tid-after-eod',       label: '毎食後 隔日',     category: '隔日', slots: ['morning', 'noon', 'evening'],           mealTiming: 'after', frequency: 'everyOtherDay' },
  { id: 'hs-eod',              label: '寝る前 隔日',     category: '隔日', slots: ['bedtime'],                              mealTiming: 'after', frequency: 'everyOtherDay' },
  { id: 'qd-am-before-eod',    label: '朝食前 隔日',     category: '隔日', slots: ['morning'],                              mealTiming: 'before', frequency: 'everyOtherDay' },

  // ==================== 週1回 ====================
  { id: 'qd-am-after-wk',    label: '朝食後 週1回',     category: '週1回', slots: ['morning'],                              mealTiming: 'after', frequency: 'weekly' },
  { id: 'qd-pm-after-wk',    label: '夕食後 週1回',     category: '週1回', slots: ['evening'],                              mealTiming: 'after', frequency: 'weekly' },
  { id: 'qd-am-before-wk',   label: '朝食前 週1回',     category: '週1回', slots: ['morning'],                              mealTiming: 'before', frequency: 'weekly' },
  { id: 'hs-wk',             label: '寝る前 週1回',     category: '週1回', slots: ['bedtime'],                              mealTiming: 'after', frequency: 'weekly' },
  { id: 'wakeup-wk',         label: '起床時 週1回',     category: '週1回', slots: ['morning'],                              mealTiming: 'wakeup', frequency: 'weekly' },
];

/** カテゴリ順序 */
export const USAGE_CATEGORIES = ['食後', '食前', '食直前', '食間', 'その他', '隔日', '週1回'];

/** IDから用法マスタを検索 */
export function findUsagePreset(id: string): UsagePreset | undefined {
  return USAGE_PRESETS.find((p) => p.id === id);
}
