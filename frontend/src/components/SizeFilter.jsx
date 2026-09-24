import React, { useEffect, useState } from 'react';
import { formatBytes } from '../services/sizes';
import { sizeAt, positionAt, sizeRangeFilters } from '../services/sizeRange';

export function SizeFilter({ catalog }) {
  const { filters, setFilters } = catalog;
  const [low, setLow] = useState(positionAt(filters.min_size || 0));
  const [high, setHigh] = useState(filters.max_size == null ? 100 : positionAt(filters.max_size));
  useEffect(() => {
    setLow(positionAt(filters.min_size || 0));
    setHigh(filters.max_size == null ? 100 : positionAt(filters.max_size));
  }, [filters.min_size, filters.max_size]);
  const reset = () => { setLow(0); setHigh(100); setFilters(f => ({...f, min_size:undefined, max_size:undefined, size_buckets:undefined})); };
  return <fieldset className="min-w-0">
    <legend className="text-sm font-semibold text-nexus-textSecondary mb-4">File size</legend>
    <div className="catalog-filter-grid">
      {[[true, low, low === 0 ? 'No minimum' : formatBytes(sizeAt(low))], [false, high, high === 100 ? 'No maximum' : formatBytes(sizeAt(high))]].map(([minimum, value, text]) => <label key={String(minimum)} className="flex flex-col gap-4 min-w-0">
        <span className="flex justify-between gap-3 text-nexus-textMuted"><span>{minimum ? 'Minimum' : 'Maximum'}</span><strong className="text-nexus-brandText font-mono text-xs">{text}</strong></span>
        <input type="range" min="0" max="100" step="1" value={value} aria-label={minimum ? 'Minimum file size' : 'Maximum file size'} aria-valuetext={text}
          className="file-size-range" style={{background:`linear-gradient(to right, #38bdf8 ${value}%, #56617c ${value}%)`}}
          onChange={e => { const next=Number(e.target.value); if(minimum) { setLow(Math.min(next, high)); } else { setHigh(Math.max(next, low)); } }} />
      </label>)}
    </div>
    <div className="flex justify-between flex-wrap gap-3 items-center mt-5"><span className="text-xs text-nexus-textMuted">KB → MB → GB · ends remove the bounds</span><div className="flex gap-2"><button type="button" className="nx-button" onClick={reset}>Any size</button><button type="button" className="nx-button" onClick={() => setFilters(f => ({...f, ...sizeRangeFilters(low,high)}))}>Apply size</button></div></div>
  </fieldset>;
}
