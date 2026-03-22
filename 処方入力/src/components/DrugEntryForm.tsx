import { useState } from 'react';
import type { DrugMasterEntry, DosingSchedule, PoolEntry, StandardSchedule, ResolvedDose } from '../types/prescription';
import { DrugSearch } from './DrugSearch';
import { DoseInput } from './DoseInput';
import { ScheduleSelector, DEFAULT_STANDARD } from './ScheduleSelector';
import { findUsagePreset } from '../data/usageMaster';
import './DrugEntryForm.css';

interface Props {
  onAdd: (entry: PoolEntry) => void;
}

/** 入力状態から ResolvedDose を導出 */
function resolveDose(
  schedule: DosingSchedule,
  selectedStrength: number | null,
  tabletCount: number,
): ResolvedDose {
  const strength = selectedStrength ?? 0;

  if (schedule.mode === 'pediatric') {
    const dailyTotalMg = schedule.dosePerKg * schedule.bodyWeight;
    const times = schedule.timesPerDay;
    return {
      perDose: times > 0 ? dailyTotalMg / times : 0, // mg単位
      timesPerDay: times,
      dailyTotal: dailyTotalMg, // mg単位
      dailyDoseMg: dailyTotalMg,
      isUneven: false,
    };
  }

  if (schedule.mode === 'prn') {
    return {
      perDose: tabletCount,
      timesPerDay: 0,
      dailyTotal: 0,
      dailyDoseMg: strength * tabletCount,
      isUneven: false,
    };
  }

  if (schedule.mode === 'custom') {
    const slotDoses = schedule.slotDoses;
    const activeSlots = Object.entries(slotDoses).filter(([, n]) => n && n > 0);
    const dailyTotal = activeSlots.reduce((sum, [, n]) => sum + n!, 0);
    return {
      perDose: 0, // 不均等のため単一値なし
      timesPerDay: activeSlots.length,
      dailyTotal,
      dailyDoseMg: strength * dailyTotal,
      isUneven: true,
      slotDoses: { ...slotDoses },
    };
  }

  // standard
  const times = schedule.slots.length;
  return {
    perDose: times > 0 ? tabletCount / times : tabletCount,
    timesPerDay: times,
    dailyTotal: tabletCount,
    dailyDoseMg: strength * tabletCount,
    isUneven: false,
  };
}

export function DrugEntryForm({ onAdd }: Props) {
  const [selectedDrug, setSelectedDrug] = useState<DrugMasterEntry | null>(null);
  const [selectedStrength, setSelectedStrength] = useState<number | null>(null);
  const [tabletCount, setTabletCount] = useState(1);
  const [schedule, setSchedule] = useState<DosingSchedule>(DEFAULT_STANDARD);

  const dose = resolveDose(schedule, selectedStrength, tabletCount);

  // PRNモードでは1日最大量チェックしない
  const isOverMax = schedule.mode !== 'prn'
    && selectedDrug?.maxDailyDose !== undefined
    && dose.dailyDoseMg > selectedDrug.maxDailyDose;

  // ノーマルモード: 錠数÷回数が割り切れない警告
  const slotsCount = schedule.mode === 'standard' ? schedule.slots.length : 0;
  const isUnevenSplit = schedule.mode === 'standard'
    && slotsCount > 0
    && selectedStrength !== null
    && tabletCount % slotsCount !== 0;

  // 追加可否
  const canAdd = (() => {
    if (!selectedDrug) return false;
    if (schedule.mode === 'pediatric') {
      return schedule.dosePerKg > 0 && schedule.bodyWeight > 0
        && schedule.timesPerDay > 0 && schedule.slots.length === schedule.timesPerDay;
    }
    if (selectedStrength === null) return false;
    if (schedule.mode === 'prn') {
      return tabletCount > 0 && schedule.condition.length > 0;
    }
    if (schedule.mode === 'custom') {
      return dose.dailyTotal > 0;
    }
    // standard
    return tabletCount > 0 && schedule.slots.length > 0;
  })();

  const handleAdd = () => {
    if (!canAdd || !selectedDrug) return;
    if (schedule.mode !== 'pediatric' && selectedStrength === null) return;
    onAdd({
      id: crypto.randomUUID(),
      drug: selectedDrug,
      selectedStrength: selectedStrength ?? 0,
      dose,
      schedule,
    });
    setSelectedDrug(null);
    setSelectedStrength(null);
    setTabletCount(1);
    setSchedule(DEFAULT_STANDARD);
  };

  const handleDrugSelect = (drug: DrugMasterEntry) => {
    setSelectedDrug(drug);
    setSelectedStrength(null);
    setTabletCount(1);
    // デフォルト用法があれば自動設定
    if (drug.defaultUsageId) {
      const preset = findUsagePreset(drug.defaultUsageId);
      if (preset) {
        const defaultSchedule: StandardSchedule = {
          mode: 'standard',
          usageId: preset.id,
          slots: [...preset.slots],
          mealTiming: preset.mealTiming,
          frequency: preset.frequency,
        };
        setSchedule(defaultSchedule);
      }
    }
  };

  const handleDrugClear = () => {
    setSelectedDrug(null);
    setSelectedStrength(null);
    setTabletCount(1);
  };

  return (
    <div className="drug-entry-form">
      <DrugSearch
        onSelect={handleDrugSelect}
        selectedDrug={selectedDrug}
        onClear={handleDrugClear}
      />
      {selectedDrug && schedule.mode !== 'pediatric' && (
        <DoseInput
          drug={selectedDrug}
          selectedStrength={selectedStrength}
          tabletCount={tabletCount}
          onStrengthChange={setSelectedStrength}
          onCountChange={setTabletCount}
          hideCount={schedule.mode === 'custom'}
          isPrn={schedule.mode === 'prn'}
        />
      )}
      <ScheduleSelector value={schedule} onChange={setSchedule} />

      {/* カスタムモード時の用量サマリー */}
      {schedule.mode === 'custom' && selectedStrength !== null && dose.dailyTotal > 0 && selectedDrug && (
        <div className="drug-entry-form__custom-summary">
          1日量: <strong>{dose.dailyDoseMg}{selectedDrug.unit}</strong>
          {selectedDrug.maxDailyDose !== undefined && (
            <span className="drug-entry-form__max"> （最大 {selectedDrug.maxDailyDose}{selectedDrug.unit}）</span>
          )}
          {isOverMax && (
            <div className="drug-entry-form__alert">
              1日最大量 {selectedDrug.maxDailyDose}{selectedDrug.unit} を超えています
            </div>
          )}
        </div>
      )}

      {isUnevenSplit && (
        <div className="drug-entry-form__warn">
          {tabletCount}{selectedDrug?.formSymbol ?? 'T'} ÷ {slotsCount}回 = 1回{(tabletCount / slotsCount).toFixed(2)}{selectedDrug?.formSymbol ?? 'T'}（割り切れません）
        </div>
      )}

      <button
        className="drug-entry-form__add-btn"
        type="button"
        disabled={!canAdd}
        onClick={handleAdd}
      >
        {isOverMax ? '⚠ 最大量超過で追加' : '追加'}
      </button>
    </div>
  );
}
