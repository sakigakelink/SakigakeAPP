import { useState } from 'react';
import type { DosingSchedule, TimeSlot, StandardSchedule, CustomSchedule, PrnSchedule, PediatricSchedule } from '../types/prescription';
import { USAGE_PRESETS } from '../data/usageMaster';
import { SLOT_ORDER } from '../utils/scheduleHelpers';
import './ScheduleSelector.css';

interface Props {
  value: DosingSchedule;
  onChange: (schedule: DosingSchedule) => void;
}

const PRN_CONDITIONS = [
  '不穏時', '不眠時', '疼痛時', '発熱時', '便秘時', '嘔気時', '不安時', '頭痛時',
];

export const DEFAULT_STANDARD: StandardSchedule = {
  mode: 'standard', usageId: 'tid-after',
  slots: ['morning', 'noon', 'evening'], mealTiming: 'after', frequency: 'daily',
};
const DEFAULT_CUSTOM: CustomSchedule = {
  mode: 'custom', slotDoses: {},
};
const DEFAULT_PRN: PrnSchedule = {
  mode: 'prn', condition: '不穏時',
};
const DEFAULT_PEDIATRIC: PediatricSchedule = {
  mode: 'pediatric', dosePerKg: 0, bodyWeight: 0, timesPerDay: 3, slots: [],
};
type ScheduleMode = 'standard' | 'prn' | 'custom' | 'pediatric';
const MODE_ORDER: ScheduleMode[] = ['standard', 'prn', 'custom', 'pediatric'];
const MODE_LABELS: Record<ScheduleMode, string> = {
  standard: '定期',
  prn: '頓用',
  custom: '不均等',
  pediatric: '体重換算',
};

export function ScheduleSelector({ value, onChange }: Props) {
  const mode = value.mode;

  const switchMode = (newMode: ScheduleMode) => {
    if (newMode === mode) return;
    if (newMode === 'standard') onChange(DEFAULT_STANDARD);
    else if (newMode === 'custom') onChange(DEFAULT_CUSTOM);
    else if (newMode === 'prn') onChange(DEFAULT_PRN);
    else onChange(DEFAULT_PEDIATRIC);
  };

  return (
    <div className="schedule-selector">
      <label className="schedule-selector__label">用法</label>

      <div className="schedule-selector__mode-tabs">
        {MODE_ORDER.map((m) => (
          <button
            key={m}
            type="button"
            className={`schedule-selector__mode-tab ${mode === m ? 'schedule-selector__mode-tab--active' : ''}`}
            onClick={() => switchMode(m)}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>

      {mode === 'standard' && <UsageMasterPanel value={value as StandardSchedule} onChange={onChange} />}
      {mode === 'custom' && <CustomPanel value={value as CustomSchedule} onChange={onChange} />}
      {mode === 'prn' && <PrnPanel value={value as PrnSchedule} onChange={onChange} />}
      {mode === 'pediatric' && <PediatricPanel value={value as PediatricSchedule} onChange={onChange} />}
    </div>
  );
}

// ========== 用法マスタパネル（クイック選択 + 検索） ==========
function UsagePresetSelector({ activeId, onSelect }: { activeId: string; onSelect: (id: string) => void }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  const quickPresets = USAGE_PRESETS.filter((p) => p.isQuick);
  const activePreset = USAGE_PRESETS.find((p) => p.id === activeId);
  const isActiveInQuick = quickPresets.some((p) => p.id === activeId);

  // 検索結果: クイック以外 or 検索文字列でフィルタ
  const searchResults = searchQuery.length > 0
    ? USAGE_PRESETS.filter((p) =>
        p.label.includes(searchQuery) || p.category.includes(searchQuery)
      )
    : USAGE_PRESETS.filter((p) => !p.isQuick);

  const handleSelect = (id: string) => {
    onSelect(id);
    setSearchQuery('');
    setShowSearch(false);
  };

  return (
    <div className="schedule-selector__usage-master">
      {/* クイック選択ボタン */}
      <div className="schedule-selector__quick-btns">
        {quickPresets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`schedule-selector__usage-btn ${activeId === preset.id ? 'schedule-selector__usage-btn--active' : ''}`}
            onClick={() => handleSelect(preset.id)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* クイック外の用法が選択中の場合、選択中ラベル表示 */}
      {!isActiveInQuick && activePreset && (
        <div className="schedule-selector__active-other">
          選択中: <strong>{activePreset.label}</strong>（{activePreset.category}）
        </div>
      )}

      {/* 検索トグル + 入力 */}
      <div className="schedule-selector__search-area">
        {!showSearch ? (
          <button
            type="button"
            className="schedule-selector__search-toggle"
            onClick={() => setShowSearch(true)}
          >
            その他の用法を検索...
          </button>
        ) : (
          <div className="schedule-selector__search-box">
            <input
              type="text"
              className="schedule-selector__search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="用法を検索（例: 食間、隔日、起床時）"
              autoFocus
            />
            <button
              type="button"
              className="schedule-selector__search-close"
              onClick={() => { setSearchQuery(''); setShowSearch(false); }}
            >
              閉じる
            </button>
          </div>
        )}
        {showSearch && searchResults.length > 0 && (
          <div className="schedule-selector__search-results">
            {searchResults.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={`schedule-selector__search-item ${activeId === preset.id ? 'schedule-selector__search-item--active' : ''}`}
                onClick={() => handleSelect(preset.id)}
              >
                <span className="schedule-selector__search-label">{preset.label}</span>
                <span className="schedule-selector__search-cat">{preset.category}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ========== ノーマルパネル ==========
function UsageMasterPanel({ value, onChange }: { value: StandardSchedule; onChange: (s: DosingSchedule) => void }) {
  const selectUsage = (id: string) => {
    const preset = USAGE_PRESETS.find((p) => p.id === id);
    if (!preset) return;
    onChange({
      mode: 'standard', usageId: id,
      slots: [...preset.slots], mealTiming: preset.mealTiming, frequency: preset.frequency,
    });
  };

  return <UsagePresetSelector activeId={value.usageId} onSelect={selectUsage} />;
}

// ========== カスタムパネル ==========
const CUSTOM_SLOT_LABELS: Record<TimeSlot, string> = {
  morning: '朝食後',
  noon: '昼食後',
  evening: '夕食後',
  bedtime: '寝る前',
};

function CustomPanel({ value, onChange }: { value: CustomSchedule; onChange: (s: DosingSchedule) => void }) {
  const setSlotDose = (slot: TimeSlot, count: number) => {
    const newDoses = { ...value.slotDoses, [slot]: Math.max(0, count) };
    onChange({ ...value, slotDoses: newDoses });
  };

  const slotSum = Object.values(value.slotDoses).reduce((sum, c) => sum + (c || 0), 0);

  return (
    <div className="schedule-selector__uneven">
      <div className="schedule-selector__slot-doses">
        {SLOT_ORDER.map((slot) => {
          const count = value.slotDoses[slot] || 0;
          return (
            <div key={slot} className="schedule-selector__slot-row">
              <span className="schedule-selector__slot-label">{CUSTOM_SLOT_LABELS[slot]}</span>
              <button type="button" className="schedule-selector__slot-btn" disabled={count <= 0} onClick={() => setSlotDose(slot, count - 1)}>−</button>
              <span className="schedule-selector__slot-count">{count}</span>
              <button type="button" className="schedule-selector__slot-btn" onClick={() => setSlotDose(slot, count + 1)}>+</button>
            </div>
          );
        })}
      </div>
      {slotSum > 0 && (
        <div className="schedule-selector__sum schedule-selector__sum--ok">
          合計: {slotSum}
        </div>
      )}
    </div>
  );
}

// ========== 小児mg/kgパネル ==========
const PED_SLOT_OPTIONS: { slot: TimeSlot; label: string }[] = [
  { slot: 'morning', label: '朝食後' },
  { slot: 'noon', label: '昼食後' },
  { slot: 'evening', label: '夕食後' },
  { slot: 'bedtime', label: '寝る前' },
];

function PediatricPanel({ value, onChange }: { value: PediatricSchedule; onChange: (s: DosingSchedule) => void }) {
  const totalDailyDose = value.dosePerKg * value.bodyWeight;
  const perDose = value.timesPerDay > 0 ? totalDailyDose / value.timesPerDay : 0;

  const toggleSlot = (slot: TimeSlot) => {
    const has = value.slots.includes(slot);
    const newSlots = has
      ? value.slots.filter((s) => s !== slot)
      : [...value.slots, slot].sort((a, b) => SLOT_ORDER.indexOf(a) - SLOT_ORDER.indexOf(b));
    onChange({ ...value, slots: newSlots });
  };

  const setTimesPerDay = (n: number) => {
    onChange({ ...value, timesPerDay: n, slots: [] });
  };

  const slotMismatch = value.slots.length > 0 && value.slots.length !== value.timesPerDay;

  return (
    <div className="schedule-selector__pediatric">
      <div className="schedule-selector__ped-row">
        <label className="schedule-selector__ped-label">体重</label>
        <input
          type="number"
          className="schedule-selector__ped-input"
          value={value.bodyWeight || ''}
          placeholder="0"
          min={0}
          step={0.1}
          onChange={(e) => onChange({ ...value, bodyWeight: parseFloat(e.target.value) || 0 })}
        />
        <span className="schedule-selector__ped-unit">kg</span>
      </div>
      <div className="schedule-selector__ped-row">
        <label className="schedule-selector__ped-label">用量</label>
        <input
          type="number"
          className="schedule-selector__ped-input"
          value={value.dosePerKg || ''}
          placeholder="0"
          min={0}
          step={0.1}
          onChange={(e) => onChange({ ...value, dosePerKg: parseFloat(e.target.value) || 0 })}
        />
        <span className="schedule-selector__ped-unit">mg/kg/日</span>
      </div>
      <div className="schedule-selector__ped-row">
        <label className="schedule-selector__ped-label">分割</label>
        <div className="schedule-selector__ped-times">
          {[1, 2, 3, 4].map((n) => (
            <button
              key={n}
              type="button"
              className={`schedule-selector__usage-btn ${value.timesPerDay === n ? 'schedule-selector__usage-btn--active' : ''}`}
              onClick={() => setTimesPerDay(n)}
            >
              {n}回
            </button>
          ))}
        </div>
      </div>

      {/* スロット選択 */}
      {value.timesPerDay > 0 && (
        <div className="schedule-selector__ped-row">
          <label className="schedule-selector__ped-label">時間帯</label>
          <div className="schedule-selector__ped-slots">
            {PED_SLOT_OPTIONS.map(({ slot, label }) => (
              <label key={slot} className="schedule-selector__ped-check">
                <input
                  type="checkbox"
                  checked={value.slots.includes(slot)}
                  onChange={() => toggleSlot(slot)}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
      )}
      {slotMismatch && (
        <div className="schedule-selector__sum schedule-selector__sum--error">
          {value.slots.length}個選択中（{value.timesPerDay}回に合わせてください）
        </div>
      )}

      {value.bodyWeight > 0 && value.dosePerKg > 0 && (
        <div className="schedule-selector__ped-summary">
          <div>1日総量: <strong>{totalDailyDose.toFixed(1)}mg</strong></div>
          <div>1回量: <strong>{perDose.toFixed(1)}mg</strong> × {value.timesPerDay}回</div>
        </div>
      )}
    </div>
  );
}

// ========== 屯用パネル ==========
function PrnPanel({ value, onChange }: { value: PrnSchedule; onChange: (s: DosingSchedule) => void }) {
  const isPreset = PRN_CONDITIONS.includes(value.condition);
  const [customText, setCustomText] = useState(isPreset ? '' : value.condition);

  return (
    <>
      <div className="schedule-selector__prn-conditions">
        {PRN_CONDITIONS.map((cond) => (
          <button
            key={cond}
            type="button"
            className={`schedule-selector__prn-btn ${value.condition === cond ? 'schedule-selector__prn-btn--active' : ''}`}
            onClick={() => {
              setCustomText('');
              onChange({ ...value, condition: cond });
            }}
          >
            {cond}
          </button>
        ))}
      </div>
      <div className="schedule-selector__prn-custom">
        <span className="schedule-selector__custom-label">自由入力:</span>
        <input
          type="text"
          className="schedule-selector__prn-input"
          value={isPreset ? customText : value.condition}
          placeholder="その他の条件"
          onChange={(e) => {
            setCustomText(e.target.value);
            onChange({ ...value, condition: e.target.value });
          }}
        />
      </div>
    </>
  );
}
