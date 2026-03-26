import type { RpGroup, SlotSummary, TimeSlot } from '../types/prescription';
import { SLOT_LABELS, SLOT_ORDER } from './scheduleHelpers';

/** 薬価を表示用にフォーマット */
function formatCost(cost: number): string {
  return cost % 1 === 0 ? `${cost}` : cost.toFixed(1);
}

/** 錠数を表示用にフォーマット（整数ならそのまま、小数なら小数点以下表示） */
function formatCount(n: number): string {
  return n % 1 === 0 ? `${n}` : n.toFixed(1);
}

/** RpGroupsを規格化テキストに変換 */
export function formatRpGroupsToText(groups: RpGroup[], slotSummary?: SlotSummary): string {
  // 屯用を除いた1日薬価合計
  const dailyCost = groups.filter((rp) => !rp.isPrn).reduce((sum, rp) => sum + rp.dailyCost, 0);
  const hasPrn = groups.some((rp) => rp.isPrn);

  const rpTexts = groups
    .map((rp) => {
      const drugLines = rp.drugs.map((d) => {
        if (d.formType === 'powder' || d.formType === 'liquid') {
          if (d.isUneven && d.slotDoses) {
            // 不均等の散剤/液剤
            const unevenPart = formatUnevenDoses(d.slotDoses, d.formSymbol);
            return `${d.drugName} 1日${formatCount(d.dailyCount)}${d.formSymbol}（${unevenPart}）`;
          }
          return `${d.drugName} ${formatCount(d.dailyCount)}${d.formSymbol}`;
        }
        if (d.isUneven && d.slotDoses) {
          // 不均等の錠剤/カプセル
          const unevenPart = formatUnevenDoses(d.slotDoses, d.formSymbol);
          return `${d.drugName}(${d.selectedStrength}) 1日${formatCount(d.dailyCount)}${d.formSymbol}（${unevenPart}）`;
        }
        return `${d.drugName}(${d.selectedStrength})${formatCount(d.dailyCount)}${d.formSymbol}`;
      });

      const costLabel = rp.isPrn
        ? `薬価: ${formatCost(rp.dailyCost)}円/回`
        : rp.dailyCost > 0
          ? `薬価: ${formatCost(rp.dailyCost)}円/日`
          : '';
      const rpHeader = costLabel
        ? `Rp${rp.rpNumber}（${costLabel}）`
        : `Rp${rp.rpNumber}`;

      if (rp.isPrn) {
        return [rpHeader, ...drugLines, rp.scheduleLabel].join('\n');
      }

      const scheduleLine = `${rp.dosesPerDay}x(  )${rp.scheduleLabel}`;
      return [rpHeader, ...drugLines, scheduleLine].join('\n');
    })
    .join('\n\n');

  const footer = hasPrn
    ? `合計薬価: ${formatCost(dailyCost)}円/日（屯用除く）`
    : `合計薬価: ${formatCost(dailyCost)}円/日`;

  // 一包化用スロット別錠数
  let slotLine = '';
  if (slotSummary) {
    const parts: string[] = [];
    if (slotSummary.morning > 0) parts.push(`朝${formatCount(slotSummary.morning)}`);
    if (slotSummary.noon > 0) parts.push(`昼${formatCount(slotSummary.noon)}`);
    if (slotSummary.evening > 0) parts.push(`夕${formatCount(slotSummary.evening)}`);
    if (slotSummary.bedtime > 0) parts.push(`寝${formatCount(slotSummary.bedtime)}`);
    if (parts.length > 0) {
      const total = slotSummary.morning + slotSummary.noon + slotSummary.evening + slotSummary.bedtime;
      slotLine = `\n一包化: ${parts.join(' ')}（計${formatCount(total)}錠/日）`;
    }
  }

  return `${rpTexts}\n\n─────────────────\n${footer}${slotLine}`;
}

/** 不均等のスロット別用量を表示用に整形 */
function formatUnevenDoses(slotDoses: Partial<Record<TimeSlot, number>>, formSymbol: string): string {
  return Object.entries(slotDoses)
    .filter(([, n]) => n && n > 0)
    .sort(([a], [b]) => SLOT_ORDER.indexOf(a as TimeSlot) - SLOT_ORDER.indexOf(b as TimeSlot))
    .map(([slot, count]) => `${SLOT_LABELS[slot as TimeSlot]}${count}${formSymbol}`)
    .join('・');
}
