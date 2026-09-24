import React from 'react';

export function SearchTiming({catalog}) {
  if (catalog.loading || catalog.error || !catalog.data) return null;
  return <p role="status" className="text-sm text-nexus-textMuted">
    Results shown in <strong>{(catalog.data.elapsed_ms / 1000).toFixed(2)} seconds</strong>
    {Number.isFinite(catalog.data.execution_time_ms) && <span> · Server search: {catalog.data.execution_time_ms.toFixed(0)} ms</span>}
  </p>;
}
