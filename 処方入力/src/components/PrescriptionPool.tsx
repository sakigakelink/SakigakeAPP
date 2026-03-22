import type { PoolEntry } from '../types/prescription';
import { formatScheduleLabel, SLOT_LABELS, SLOT_ORDER } from '../utils/scheduleHelpers';
import type { TimeSlot } from '../types/prescription';
import './PrescriptionPool.css';

interface Props {
  entries: PoolEntry[];
  onDelete: (id: string) => void;
  onEdit: (id: string) => void;
}

export function PrescriptionPool({ entries, onDelete, onEdit }: Props) {
  if (entries.length === 0) {
    return (
      <div className="pool pool--empty">
        <p className="pool__empty-msg">薬剤が追加されていません</p>
      </div>
    );
  }

  // 同一薬剤・同一規格の重複を検出（成形時に統合される対象）
  const dupKeys = new Set<string>();
  const keyCounts = new Map<string, number>();
  for (const e of entries) {
    if (e.schedule.mode === 'prn' || e.schedule.mode === 'pediatric') continue;
    const key = `${e.drug.id}|${e.selectedStrength}`;
    keyCounts.set(key, (keyCounts.get(key) ?? 0) + 1);
  }
  for (const [key, count] of keyCounts) {
    if (count > 1) dupKeys.add(key);
  }

  return (
    <div className="pool">
      <h3 className="pool__title">処方プール ({entries.length}件)</h3>
      <table className="pool__table">
        <thead>
          <tr>
            <th>薬剤名</th>
            <th>1日量</th>
            <th>用法</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const willMerge = dupKeys.has(`${entry.drug.id}|${entry.selectedStrength}`);
            return (
            <tr key={entry.id}>
              <td className="pool__drug-name">
                {entry.drug.name}
                <span className="pool__form-badge">{entry.drug.formSymbol}</span>
                {willMerge && <span className="pool__merge-badge">統合</span>}
              </td>
              <td className="pool__dose">
                {entry.schedule.mode === 'pediatric' ? (
                  <>
                    {entry.schedule.dosePerKg}mg/kg/日
                    <br />
                    <span className="pool__dose-total">
                      = {entry.dose.dailyDoseMg.toFixed(1)}{entry.drug.unit}/日
                      （{entry.schedule.bodyWeight}kg）
                    </span>
                  </>
                ) : entry.dose.isUneven ? (
                  <>
                    {entry.selectedStrength}{entry.drug.unit} x{' '}
                    {Object.entries(entry.dose.slotDoses || {})
                      .filter(([, c]) => c && c > 0)
                      .sort(([a], [b]) => SLOT_ORDER.indexOf(a as TimeSlot) - SLOT_ORDER.indexOf(b as TimeSlot))
                      .map(([slot, count]) => `${SLOT_LABELS[slot as TimeSlot]}${count}`)
                      .join('-')}
                    {entry.drug.formSymbol}
                    <br />
                    <span className="pool__dose-total">= {entry.dose.dailyDoseMg}{entry.drug.unit}/日</span>
                  </>
                ) : entry.schedule.mode === 'prn' ? (
                  <>
                    {entry.selectedStrength}{entry.drug.unit} x {entry.dose.perDose}{entry.drug.formSymbol}
                    <br />
                    <span className="pool__dose-total">1回量</span>
                  </>
                ) : (
                  <>
                    {entry.selectedStrength}{entry.drug.unit} x {entry.dose.dailyTotal}{entry.drug.formSymbol}
                    <br />
                    <span className="pool__dose-total">= {entry.dose.dailyDoseMg}{entry.drug.unit}/日</span>
                  </>
                )}
              </td>
              <td className="pool__schedule">
                {formatScheduleLabel(entry.schedule)}
              </td>
              <td className="pool__actions">
                <button
                  className="pool__btn pool__btn--edit"
                  onClick={() => onEdit(entry.id)}
                  type="button"
                >
                  編集
                </button>
                <button
                  className="pool__btn pool__btn--delete"
                  onClick={() => onDelete(entry.id)}
                  type="button"
                >
                  削除
                </button>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
