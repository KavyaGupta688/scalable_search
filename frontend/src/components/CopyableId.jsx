import React, {useState} from 'react';

export function CopyableId({label, value}) {
  const [message, setMessage] = useState('');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setMessage('Copied');
    } catch {
      setMessage('Select the ID to copy it manually.');
    }
  };
  return <div className="min-w-0">
    <div className="flex items-start gap-2">
      <code className="min-w-0 break-all select-all text-nexus-brandText">{value || 'Unavailable'}</code>
      <button type="button" disabled={!value} aria-label={`Copy ${label}`} onClick={copy}
        className="shrink-0 text-xs text-nexus-textSecondary hover:text-nexus-textPrimary underline">Copy</button>
    </div>
    <span role="status" className="text-xs text-nexus-textMuted">{message}</span>
  </div>;
}
