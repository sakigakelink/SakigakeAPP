import { useState, useEffect, useRef } from 'react';
import type { DrugMasterEntry } from '../types/prescription';
import { drugMaster } from '../data/drugMaster';

export function useDrugSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DrugMasterEntry[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }

    if (query.length < 2) {
      setResults([]);
      return;
    }

    timerRef.current = window.setTimeout(() => {
      const q = query.toLowerCase();
      const filtered = drugMaster.filter(
        (d) =>
          d.name.toLowerCase().includes(q) ||
          d.genericName.toLowerCase().includes(q)
      );
      setResults(filtered.slice(0, 15));
    }, 150);

    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, [query]);

  return { query, setQuery, results, clearResults: () => setResults([]) };
}
