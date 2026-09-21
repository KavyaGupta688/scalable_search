import React from 'react';

/**
 * Autocomplete options shared by the admin and user search boxes.
 * The parent supplies the role="listbox" container and the id prefix.
 */
export const SuggestionOptions = ({ idPrefix, items, highlight, onSelect }) => items.map((item, index) => {
  const text = typeof item === 'string' ? item : item.text || item.query;
  // The backend badge (e.g. trending) wins; otherwise label the source of the suggestion.
  const label = typeof item === 'string' ? '' : item.badge || (item.type === 'file' ? 'File' : item.type);
  return (
    <button
      key={`${text}-${index}`} id={`${idPrefix}-${index}`} role="option" aria-selected={highlight === index}
      type="button"
      onMouseDown={e => e.preventDefault()} onClick={() => onSelect(text)}
      className={`w-full text-left px-3.5 py-2 text-sm text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover flex items-center justify-between gap-3 transition-colors ${highlight === index ? 'bg-nexus-hover' : ''}`}
    >
      <span className="truncate">{text}</span>
      {label && <span className="text-xs font-mono uppercase tracking-wide text-nexus-textMuted shrink-0">{label}</span>}
    </button>
  );
});
