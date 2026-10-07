import React from 'react';

const COMPONENT_LABELS = {
  vector: 'semantic and visual matching',
  rerank: 'relevance verification',
};

export function SearchTiming({catalog}) {
  if (catalog.loading || catalog.error || !catalog.data) return null;
  const degraded = catalog.data.partial_results ? (catalog.data.degraded_components || []) : [];
  return <>
    <p role="status" className="text-sm text-nexus-textMuted">
      Results shown in <strong>{(catalog.data.elapsed_ms / 1000).toFixed(2)} seconds</strong>
      {Number.isFinite(catalog.data.execution_time_ms) && <span> · Server search: {catalog.data.execution_time_ms.toFixed(0)} ms</span>}
    </p>
    {degraded.length > 0 && <p role="status" className="rounded-xl border border-amber-800/50 bg-amber-950/20 p-3 text-sm text-amber-200">
      Partial results: {degraded.map(name => COMPONENT_LABELS[name] || name).join(' and ')} {degraded.length > 1 ? 'are' : 'is'} temporarily unavailable, so these results come from keyword matching only. Try again shortly for the full ranking.
    </p>}
  </>;
}
