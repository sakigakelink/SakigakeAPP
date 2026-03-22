import { useState } from 'react';
import type { PoolEntry, PrescriptionContext, RpGroup, SlotSummary } from './types/prescription';
import { PrescriptionTypeBar } from './components/PrescriptionTypeBar';
import { DrugEntryForm } from './components/DrugEntryForm';
import { PrescriptionPool } from './components/PrescriptionPool';
import { StandardizedOutput } from './components/StandardizedOutput';
import { standardize, calcSlotSummary } from './utils/standardize';
import './App.css';

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function App() {
  const [pool, setPool] = useState<PoolEntry[]>([]);
  const [rxContext, setRxContext] = useState<PrescriptionContext>({
    mode: 'inpatient',
    startDate: todayStr(),
    startTimeSlot: 'morning',
  });
  const [rpGroups, setRpGroups] = useState<RpGroup[] | null>(null);
  const [slotSummary, setSlotSummary] = useState<SlotSummary | null>(null);

  const handleAdd = (entry: PoolEntry) => {
    setPool((prev) => [...prev, entry]);
    setRpGroups(null);
    setSlotSummary(null);
  };

  const handleDelete = (id: string) => {
    setPool((prev) => prev.filter((e) => e.id !== id));
    setRpGroups(null);
    setSlotSummary(null);
  };

  const handleEdit = (id: string) => {
    handleDelete(id);
  };

  const handleStandardize = () => {
    const groups = standardize(pool);
    setRpGroups(groups);
    setSlotSummary(calcSlotSummary(pool));
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">処方入力</h1>
      </header>

      <main className="app__main">
        <PrescriptionTypeBar value={rxContext} onChange={setRxContext} />

        <section className="app__section">
          <h2 className="app__section-title">薬剤追加</h2>
          <DrugEntryForm onAdd={handleAdd} />
        </section>

        <section className="app__section">
          <PrescriptionPool
            entries={pool}
            onDelete={handleDelete}
            onEdit={handleEdit}
          />
        </section>

        <div className="app__actions">
          <button
            className="app__standardize-btn"
            type="button"
            disabled={pool.length === 0}
            onClick={handleStandardize}
          >
            処方箋を成形
          </button>
        </div>

        {rpGroups && rpGroups.length > 0 && (
          <section className="app__section">
            <StandardizedOutput rpGroups={rpGroups} slotSummary={slotSummary ?? undefined} />
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
