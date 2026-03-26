import { useState } from 'react';
import type { RpGroup, SlotSummary } from '../types/prescription';
import { formatRpGroupsToText } from '../utils/formatOutput';
import './StandardizedOutput.css';

interface Props {
  rpGroups: RpGroup[];
  slotSummary?: SlotSummary;
}

export function StandardizedOutput({ rpGroups, slotSummary }: Props) {
  const [copied, setCopied] = useState(false);
  const text = formatRpGroupsToText(rpGroups, slotSummary);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 警告の収集
  const warnings = rpGroups.flatMap((rp) =>
    rp.drugs.filter((d) => d.warning).map((d) => `${d.drugName}: ${d.warning}`)
  );

  return (
    <div className="std-output">
      <div className="std-output__header">
        <h3 className="std-output__title">成形結果</h3>
        <button
          className="std-output__copy-btn"
          onClick={handleCopy}
          type="button"
        >
          {copied ? 'コピー済み' : 'クリップボードにコピー'}
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="std-output__warnings">
          {warnings.map((w, i) => (
            <p key={i} className="std-output__warning">{w}</p>
          ))}
        </div>
      )}

      <pre className="std-output__text">{text}</pre>
    </div>
  );
}
