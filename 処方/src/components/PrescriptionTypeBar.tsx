import type { PrescriptionContext, PrescriptionMode, TimeSlot } from '../types/prescription';
import './PrescriptionTypeBar.css';

interface Props {
  value: PrescriptionContext;
  onChange: (ctx: PrescriptionContext) => void;
}

const TIME_SLOT_OPTIONS: { key: TimeSlot; label: string }[] = [
  { key: 'morning', label: '朝' },
  { key: 'noon', label: '昼' },
  { key: 'evening', label: '夕' },
  { key: 'bedtime', label: '寝る前' },
];

export function PrescriptionTypeBar({ value, onChange }: Props) {
  const setMode = (mode: PrescriptionMode) => {
    onChange({
      ...value,
      mode,
      endDate: mode === 'outpatient' ? value.endDate || value.startDate : undefined,
      endTimeSlot: mode === 'outpatient' ? value.endTimeSlot || 'evening' : undefined,
    });
  };

  return (
    <div className="rx-type-bar">
      <div className="rx-type-bar__modes">
        <label className="rx-type-bar__radio">
          <input
            type="radio"
            name="rxMode"
            checked={value.mode === 'inpatient'}
            onChange={() => setMode('inpatient')}
          />
          入院処方
        </label>
        <label className="rx-type-bar__radio">
          <input
            type="radio"
            name="rxMode"
            checked={value.mode === 'outpatient'}
            onChange={() => setMode('outpatient')}
          />
          外来・臨時処方
        </label>
      </div>

      {value.mode === 'inpatient' ? (
        /* === 入院: 開始日 + 開始タイミング === */
        <div className="rx-type-bar__dates">
          <label className="rx-type-bar__date-label">
            開始日:
            <input
              type="date"
              className="rx-type-bar__date-input"
              value={value.startDate}
              onChange={(e) => onChange({ ...value, startDate: e.target.value })}
            />
          </label>
          <div className="rx-type-bar__timing-group">
            {TIME_SLOT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={`rx-type-bar__timing-btn ${value.startTimeSlot === opt.key ? 'rx-type-bar__timing-btn--active' : ''}`}
                onClick={() => onChange({ ...value, startTimeSlot: opt.key })}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* === 外来・臨時: 開始日+開始タイミング → 終了日+終了タイミング === */
        <div className="rx-type-bar__dates">
          <div className="rx-type-bar__range-row">
            <label className="rx-type-bar__date-label">
              開始:
              <input
                type="date"
                className="rx-type-bar__date-input"
                value={value.startDate}
                onChange={(e) => onChange({ ...value, startDate: e.target.value })}
              />
            </label>
            <div className="rx-type-bar__timing-group">
              {TIME_SLOT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  className={`rx-type-bar__timing-btn ${value.startTimeSlot === opt.key ? 'rx-type-bar__timing-btn--active' : ''}`}
                  onClick={() => onChange({ ...value, startTimeSlot: opt.key })}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <span className="rx-type-bar__arrow">→</span>
          <div className="rx-type-bar__range-row">
            <label className="rx-type-bar__date-label">
              終了:
              <input
                type="date"
                className="rx-type-bar__date-input"
                value={value.endDate || ''}
                onChange={(e) => onChange({ ...value, endDate: e.target.value })}
              />
            </label>
            <div className="rx-type-bar__timing-group">
              {TIME_SLOT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  className={`rx-type-bar__timing-btn ${(value.endTimeSlot || 'evening') === opt.key ? 'rx-type-bar__timing-btn--active' : ''}`}
                  onClick={() => onChange({ ...value, endTimeSlot: opt.key })}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
