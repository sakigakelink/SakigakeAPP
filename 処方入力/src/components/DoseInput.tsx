import type { DrugMasterEntry } from '../types/prescription';
import './DoseInput.css';

interface Props {
  drug: DrugMasterEntry;
  selectedStrength: number | null;
  tabletCount: number;
  onStrengthChange: (strength: number) => void;
  onCountChange: (count: number) => void;
  hideCount?: boolean;
  isPrn?: boolean;
}

export function DoseInput({ drug, selectedStrength, tabletCount, onStrengthChange, onCountChange, hideCount, isPrn }: Props) {
  const dailyDose = selectedStrength !== null ? selectedStrength * tabletCount : 0;
  const isOverMax = !isPrn && drug.maxDailyDose !== undefined && dailyDose > drug.maxDailyDose;
  const isPowderOrLiquid = drug.formType === 'powder' || drug.formType === 'liquid';

  return (
    <div className="dose-input">
      {/* 規格選択 */}
      <div className="dose-input__section">
        <label className="dose-input__label">規格</label>
        <div className="dose-input__strength-btns">
          {drug.strengths.map((s) => (
            <button
              key={s.value}
              type="button"
              className={`dose-input__strength-btn ${selectedStrength === s.value ? 'dose-input__strength-btn--active' : ''}`}
              onClick={() => onStrengthChange(s.value)}
            >
              <span className="dose-input__strength-value">{s.value}{drug.unit}</span>
              <span className="dose-input__strength-price">{s.price.toFixed(1)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 錠数選択 */}
      {selectedStrength !== null && !hideCount && (
        <div className="dose-input__section">
          <label className="dose-input__label">
            {isPowderOrLiquid ? '数量' : '錠数'}
          </label>
          <div className="dose-input__count-row">
            <button
              type="button"
              className="dose-input__count-btn"
              disabled={tabletCount <= 1}
              onClick={() => onCountChange(tabletCount - 1)}
            >
              −
            </button>
            <span className="dose-input__count-value">
              {tabletCount}{drug.formSymbol}
            </span>
            <button
              type="button"
              className="dose-input__count-btn"
              onClick={() => onCountChange(tabletCount + 1)}
            >
              +
            </button>
          </div>
          <div className="dose-input__summary">
            {isPrn ? (
              <>1回量: <strong>{dailyDose}{isPowderOrLiquid ? drug.inputUnit : drug.unit}</strong></>
            ) : (
              <>
                1日量: <strong>{dailyDose}{isPowderOrLiquid ? drug.inputUnit : drug.unit}</strong>
                {drug.maxDailyDose !== undefined && (
                  <span className="dose-input__max">
                    （最大 {drug.maxDailyDose}{drug.unit}）
                  </span>
                )}
              </>
            )}
          </div>
          {isOverMax && (
            <div className="dose-input__alert">
              1日最大量 {drug.maxDailyDose}{drug.unit} を超えています
            </div>
          )}
        </div>
      )}
    </div>
  );
}
