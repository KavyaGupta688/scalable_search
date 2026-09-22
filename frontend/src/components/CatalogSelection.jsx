import React, {useEffect, useRef} from 'react';

export function CatalogSelection({catalog}) {
  const {results, selectedFileIds, setSelectedFileIds, loading} = catalog;
  const checkbox = useRef(null);
  const ids = [...new Set(results.map(file => file.file_id || file.id))];
  const selectedOnPage = ids.filter(id => selectedFileIds.includes(id)).length;
  const allSelected = ids.length > 0 && selectedOnPage === ids.length;
  const wouldExceedLimit = selectedFileIds.length + ids.length - selectedOnPage > 100;
  useEffect(() => {
    if (checkbox.current) checkbox.current.indeterminate = selectedOnPage > 0 && !allSelected;
  }, [selectedOnPage, allSelected]);
  const togglePage = () => setSelectedFileIds(current => allSelected
    ? current.filter(id => !ids.includes(id))
    : [...new Set([...current, ...ids])].slice(0, 100));
  return <div className="nx-panel px-4 py-3 flex flex-wrap items-center gap-3 text-sm" aria-label="File selection">
    <label className="flex items-center gap-2 cursor-pointer font-semibold text-nexus-textPrimary">
      <input ref={checkbox} type="checkbox" className="h-4 w-4 accent-blue-600"
        checked={allSelected} disabled={loading || !ids.length || (!allSelected && wouldExceedLimit)}
        onChange={togglePage} />
      Select this page
    </label>
    <span className="text-nexus-brandText font-mono" role="status">{selectedFileIds.length} / 100 files selected</span>
    {selectedFileIds.length > 0 && <button type="button" className="text-nexus-textSecondary underline" onClick={() => setSelectedFileIds([])}>Clear selection</button>}
    <p className="w-full text-xs text-nexus-textMuted">{wouldExceedLimit && !allSelected
      ? 'This page exceeds the 100-file limit. Select individual files or clear some selections.'
      : 'Selections stay across pages. Changing the search, mode or filters clears them. Download Selected creates one ZIP archive.'}</p>
  </div>;
}
