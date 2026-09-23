import React from 'react';
import { formatCount } from '../services/facets';

/**
 * Multi-select filter over counted choices (resolution tiers, file-size buckets).
 * `counts` maps choice id -> files, or is null while facets are unavailable. Choices with no
 * files cannot be picked unless already selected. layout: 'list' (sidebar) | 'chips'.
 */
export const FacetChoiceFilter = ({ catalog, field, title, listTitle, choices, counts, layout = 'chips', note = '' }) => {
  const selected = catalog.filters[field] || [];
  const toggle = id => {
    const next = selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id];
    catalog.setFilters(f => ({ ...f, [field]: next.length ? next : undefined }));
  };
  const unavailable = choice => Boolean(counts) && counts[choice.id] === 0 && !selected.includes(choice.id);

  return (
    <div className="flex flex-col gap-2" role="group" aria-label={title}>
      <span className={layout === 'list' ? 'text-sm font-bold text-nexus-textSecondary' : 'text-sm text-nexus-textMuted'}>
        {layout === 'list' ? listTitle || title : `${title}:`}
      </span>
      {layout === 'list' ? (
        <div className="flex flex-col gap-1.5">
          {choices.map(choice => (
            <label key={choice.id} title={choice.hint} className={`flex items-center gap-2 text-sm select-none ${unavailable(choice) ? 'text-nexus-textMuted opacity-60' : 'text-nexus-textSecondary hover:text-nexus-textPrimary cursor-pointer'}`}>
              <input type="checkbox" className="accent-nexus-brand rounded-xs" checked={selected.includes(choice.id)} disabled={unavailable(choice)} onChange={() => toggle(choice.id)} />
              <span>{choice.label}</span>
              <span className="ml-auto font-mono text-nexus-textMuted">{formatCount(counts?.[choice.id])}</span>
            </label>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-1.5 flex-wrap">
          {choices.map(choice => {
            const active = selected.includes(choice.id);
            return (
              <button key={choice.id} type="button" title={choice.hint} aria-pressed={active} disabled={unavailable(choice)} onClick={() => toggle(choice.id)}
                className={`text-sm px-2.5 py-1 rounded-sm border transition-colors disabled:opacity-50 ${active
                  ? 'bg-nexus-brandSubtle text-nexus-brandText border-nexus-border font-semibold'
                  : 'bg-nexus-elevated text-nexus-textMuted border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textSecondary'}`}>
                {choice.label} <span className="font-mono">({formatCount(counts?.[choice.id])})</span>
              </button>
            );
          })}
        </div>
      )}
      {note && <p className="text-xs text-nexus-textMuted">{note}</p>}
    </div>
  );
};
