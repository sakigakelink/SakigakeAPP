import { useRef, useEffect } from 'react';
import type { DrugMasterEntry } from '../types/prescription';
import { useDrugSearch } from '../hooks/useDrugSearch';
import './DrugSearch.css';

interface Props {
  onSelect: (drug: DrugMasterEntry) => void;
  selectedDrug: DrugMasterEntry | null;
  onClear: () => void;
}

export function DrugSearch({ onSelect, selectedDrug, onClear }: Props) {
  const { query, setQuery, results, clearResults } = useDrugSearch();
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        clearResults();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [clearResults]);

  if (selectedDrug) {
    return (
      <div className="drug-search">
        <label className="drug-search__label">薬剤名</label>
        <div className="drug-search__selected">
          <span className="drug-search__selected-name">
            {selectedDrug.name}
            <span className="drug-search__selected-form">
              ({selectedDrug.formSymbol})
            </span>
          </span>
          <button className="drug-search__clear-btn" onClick={onClear} type="button">
            変更
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="drug-search" ref={wrapperRef}>
      <label className="drug-search__label">薬剤名</label>
      <input
        className="drug-search__input"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="薬剤名を入力（2文字以上）"
        autoFocus
      />
      {results.length > 0 && (
        <ul className="drug-search__dropdown">
          {results.map((drug) => (
            <li
              key={drug.id}
              className="drug-search__item"
              onClick={() => {
                onSelect(drug);
                setQuery('');
                clearResults();
              }}
            >
              <span className="drug-search__item-name">{drug.name}</span>
              <span className="drug-search__item-meta">
                {drug.genericName} | {drug.strengths.map((s) => s.value).join('/')}
                {drug.unit} | {drug.formSymbol}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
