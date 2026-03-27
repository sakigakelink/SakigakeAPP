import type { PoolEntry, RpGroup, StandardizedDrug, SlotSummary, PrnSchedule, PediatricSchedule, TimeSlot, StandardSchedule, CustomSchedule } from '../types/prescription';
import { normalizeScheduleKey, getDosesPerDay, formatScheduleLabel, SLOT_ORDER } from './scheduleHelpers';

function getUnitPrice(entry: PoolEntry): number {
  const found = entry.drug.strengths.find((s) => s.value === entry.selectedStrength);
  return found?.price ?? 0;
}

function entryToDrug(entry: PoolEntry): StandardizedDrug {
  return {
    drugName: entry.drug.name,
    selectedStrength: entry.selectedStrength,
    unitPrice: getUnitPrice(entry),
    perDose: entry.dose.perDose,
    dailyCount: entry.dose.dailyTotal,
    formSymbol: entry.drug.formSymbol,
    formType: entry.drug.formType,
    isUneven: entry.dose.isUneven,
    slotDoses: entry.dose.slotDoses,
  };
}

function calcDailyCost(drugs: StandardizedDrug[]): number {
  return drugs.reduce((sum, d) => sum + d.unitPrice * d.dailyCount, 0);
}

/** 同一用法キーでグルーピング */
function groupByKey(entries: PoolEntry[]): Map<string, PoolEntry[]> {
  const groups = new Map<string, PoolEntry[]>();
  for (const entry of entries) {
    const key = normalizeScheduleKey(entry.schedule);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(entry);
  }
  return groups;
}

/**
 * 同一薬剤（drug.id + selectedStrength）が複数エントリに分かれている場合、
 * スロットを統合して1エントリにまとめる。
 * 例: デパケンR 200mg 朝食後1T + デパケンR 200mg 夕食後2T → 朝夕食後(朝1-夕2)
 */
function mergeSameDrugEntries(entries: PoolEntry[]): PoolEntry[] {
  const drugGroups = new Map<string, PoolEntry[]>();
  const otherEntries: PoolEntry[] = [];

  for (const entry of entries) {
    if (entry.schedule.mode === 'prn' || entry.schedule.mode === 'pediatric') {
      otherEntries.push(entry);
      continue;
    }
    const key = `${entry.drug.id}|${entry.selectedStrength}`;
    if (!drugGroups.has(key)) drugGroups.set(key, []);
    drugGroups.get(key)!.push(entry);
  }

  const result: PoolEntry[] = [...otherEntries];

  for (const [, group] of drugGroups) {
    if (group.length === 1) {
      result.push(group[0]);
      continue;
    }

    // 同一薬剤・同一規格の複数エントリ → スロット統合
    const slotDoses: Partial<Record<TimeSlot, number>> = {};
    let mealTiming: 'after' | 'before' | 'justBefore' | 'between' | 'wakeup' = 'after';
    let frequency: 'daily' | 'everyOtherDay' | 'weekly' = 'daily';

    for (const entry of group) {
      if (entry.schedule.mode === 'standard') {
        const std = entry.schedule as StandardSchedule;
        mealTiming = std.mealTiming;
        frequency = std.frequency;
        const perSlot = entry.dose.dailyTotal / std.slots.length;
        for (const slot of std.slots) {
          slotDoses[slot] = (slotDoses[slot] ?? 0) + perSlot;
        }
      } else if (entry.schedule.mode === 'custom') {
        const cst = entry.schedule as CustomSchedule;
        for (const [slot, count] of Object.entries(cst.slotDoses)) {
          if (count && count > 0) {
            slotDoses[slot as TimeSlot] = (slotDoses[slot as TimeSlot] ?? 0) + count;
          }
        }
      }
    }

    const activeSlots = Object.entries(slotDoses)
      .filter(([, n]) => n && n > 0)
      .sort(([a], [b]) => SLOT_ORDER.indexOf(a as TimeSlot) - SLOT_ORDER.indexOf(b as TimeSlot));
    const dailyTotal = activeSlots.reduce((sum, [, n]) => sum + n!, 0);
    const strength = group[0].selectedStrength;
    const allSame = activeSlots.length > 0 && activeSlots.every(([, n]) => n === activeSlots[0][1]);

    if (allSame) {
      // 均等: standard エントリとして統合
      const slots = activeSlots.map(([s]) => s as TimeSlot);
      result.push({
        ...group[0],
        dose: {
          perDose: activeSlots[0][1]!,
          timesPerDay: slots.length,
          dailyTotal,
          dailyDoseMg: strength * dailyTotal,
          isUneven: false,
        },
        schedule: {
          mode: 'standard',
          usageId: '',
          slots,
          mealTiming,
          frequency,
        },
      });
    } else {
      // 不均等: custom エントリとして統合
      result.push({
        ...group[0],
        dose: {
          perDose: 0,
          timesPerDay: activeSlots.length,
          dailyTotal,
          dailyDoseMg: strength * dailyTotal,
          isUneven: true,
          slotDoses: { ...slotDoses },
        },
        schedule: {
          mode: 'custom',
          slotDoses: { ...slotDoses },
        },
      });
    }
  }

  return result;
}

/** プールエントリ群を成形してRpグループに変換 */
export function standardize(entries: PoolEntry[]): RpGroup[] {
  if (entries.length === 0) return [];

  // 前処理: 同一薬剤・同一規格のエントリをスロット統合
  const merged = mergeSameDrugEntries(entries);

  const rpGroups: RpGroup[] = [];
  let rpNumber = 1;

  // standard + custom を統合してグルーピング（同じスロット構成なら同一Rp）
  const scheduledEntries = merged.filter((e) => e.schedule.mode === 'standard' || e.schedule.mode === 'custom');
  const prnEntries = merged.filter((e) => e.schedule.mode === 'prn');
  const pediatricEntries = merged.filter((e) => e.schedule.mode === 'pediatric');

  // 1. 定時処方（standard + custom）: 同一用法キーでグルーピング
  for (const [, groupEntries] of groupByKey(scheduledEntries)) {
    // スケジュールラベルは standard エントリ優先、なければ custom から自動生成
    const standardEntry = groupEntries.find((e) => e.schedule.mode === 'standard');
    const schedule = standardEntry?.schedule ?? groupEntries[0].schedule;
    const drugs = groupEntries.map((e) => entryToDrug(e));
    rpGroups.push({
      rpNumber: rpNumber++,
      drugs,
      dosesPerDay: getDosesPerDay(schedule),
      scheduleLabel: formatScheduleLabel(schedule),
      isPrn: false,
      dailyCost: calcDailyCost(drugs),
    });
  }

  // 3. 屯用: 1薬剤=1Rp
  for (const entry of prnEntries) {
    const schedule = entry.schedule as PrnSchedule;
    const drug = entryToDrug(entry);
    // 屯用: dailyCountは0、perDoseが1回量
    rpGroups.push({
      rpNumber: rpNumber++,
      drugs: [drug],
      dosesPerDay: 0,
      scheduleLabel: schedule.condition,
      isPrn: true,
      dailyCost: drug.unitPrice * drug.perDose, // 1回分の薬価
    });
  }

  // 4. 体重換算: 1薬剤=1Rp
  for (const entry of pediatricEntries) {
    const schedule = entry.schedule as PediatricSchedule;
    const drugs: StandardizedDrug[] = [{
      drugName: entry.drug.name,
      selectedStrength: 0,
      unitPrice: 0,
      perDose: entry.dose.perDose,
      dailyCount: entry.dose.dailyTotal,
      formSymbol: entry.drug.formSymbol,
      formType: entry.drug.formType,
      isUneven: false,
    }];
    rpGroups.push({
      rpNumber: rpNumber++,
      drugs,
      dosesPerDay: schedule.timesPerDay,
      scheduleLabel: formatScheduleLabel(schedule),
      isPrn: false,
      dailyCost: 0,
    });
  }

  return rpGroups;
}

/** 一包化用: PoolEntryからスロット別の総錠数を集計（屯用除く） */
export function calcSlotSummary(entries: PoolEntry[]): SlotSummary {
  const summary: SlotSummary = { morning: 0, noon: 0, evening: 0, bedtime: 0 };

  for (const entry of entries) {
    const { schedule, dose } = entry;

    if (schedule.mode === 'prn') continue;

    if (dose.isUneven && dose.slotDoses) {
      // 不均等: スロット別にそのまま加算
      for (const [slot, count] of Object.entries(dose.slotDoses)) {
        if (count && count > 0) {
          summary[slot as TimeSlot] += count;
        }
      }
    } else if (schedule.mode === 'standard') {
      const std = schedule as StandardSchedule;
      const slotsCount = std.slots.length;
      if (slotsCount === 0) continue;
      const perSlot = dose.dailyTotal / slotsCount;
      for (const slot of std.slots) {
        summary[slot] += perSlot;
      }
    } else if (schedule.mode === 'pediatric') {
      const ped = schedule as PediatricSchedule;
      if (ped.slots.length > 0 && ped.timesPerDay > 0) {
        for (const slot of ped.slots) {
          summary[slot] += 1; // TODO: 実錠数は規格決定後に算出
        }
      }
    }
  }

  return summary;
}
