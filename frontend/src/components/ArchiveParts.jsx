import React from 'react';
import { formatBytes } from '../services/sizes';

/**
 * Save buttons for a finished download. Large requests are split into several archive parts,
 * each saved on its own; a single archive keeps the plain "Save archive" button.
 * onSave(partNumber) saves one part.
 */
export const ArchiveParts = ({ job, onSave, busy = false }) => {
  const parts = job?.parts || [];
  if (!parts.length) {
    return job?.download_url ? <button type="button" className="nx-button nx-button--primary" onClick={() => onSave(1)} disabled={busy}>Save archive</button> : null;
  }
  if (parts.length === 1) {
    return <button type="button" className="nx-button nx-button--primary" onClick={() => onSave(1)} disabled={busy}>Save archive ({formatBytes(parts[0].size_bytes)})</button>;
  }
  const saveAll = async () => { for (const part of parts) await onSave(part.index); };
  return (
    <div className="flex flex-col gap-1.5">
      <ul className="flex flex-col gap-1">
        {parts.map(part => (
          <li key={part.index} className="flex items-center gap-3 text-sm">
            <span className="text-nexus-textSecondary">Part {part.index} of {parts.length}</span>
            <span className="font-mono text-nexus-textMuted">{formatBytes(part.size_bytes)}</span>
            <button type="button" className="nx-button" onClick={() => onSave(part.index)} disabled={busy}>Save</button>
          </li>
        ))}
      </ul>
      <button type="button" className="nx-button nx-button--primary self-start" onClick={saveAll} disabled={busy}>Save all {parts.length} parts</button>
    </div>
  );
};
