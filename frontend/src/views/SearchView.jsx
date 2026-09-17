import { Presence } from '../components/Motion';
import React, { useState, useEffect, useCallback } from 'react';
import { PageHeading } from '../components/DesignSystem';
import { search, getFacets, postSearchEvent } from '../services/searchApi';
import { ModalDetail } from '../components/ModalDetail';
import { ModalityBadge } from '../components/ModalityBadge';
import { SearchResultCard } from '../components/SearchResultCard';
import {
  SearchIcon,
  FilterIcon,
  GridIcon,
  ListIcon,
  CloseIcon,
  SpinnerIcon,
} from '../components/Icons';

export const SearchView = ({ showToast }) => {
  const [activeDocId, setActiveDocId] = useState(null);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('vector'); // 'vector' (natural) | 'text' (keyword) | 'similar'
  const [viewMode, setViewMode] = useState('grid');
  const [selectedModalities, setSelectedModalities] = useState([]);
  const [availableFacets, setAvailableFacets] = useState(['image', 'video', 'document', 'audio', 'tabular']);
  const [minConfidence, setMinConfidence] = useState(0);
  const [sortBy, setSortBy] = useState('relevance');
  const [results, setResults] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const exampleQueries = [
    'Cracked OLED display panels',
    'Robotic assembly line video feeds',
    'Display panel quality failure reports',
    'Motor vibration acoustic anomalies',
    'Defect telemetry inspection CSV',
  ];

  // Load facets
  useEffect(() => {
    getFacets()
      .then((data) => {
        if (data.content_type && Array.isArray(data.content_type)) {
          setAvailableFacets(data.content_type);
        }
      })
      .catch(() => {});
  }, []);

  const executeSearch = useCallback(async () => {
    setLoading(true);
    setError('');

    const contentType = selectedModalities.length === 1 ? selectedModalities[0] : null;

    try {
      const res = await search(query, mode, contentType, 24);
      let list = res.results || [];

      // Modality client filter if multiple chosen
      if (selectedModalities.length > 1) {
        list = list.filter((item) =>
          selectedModalities.includes((item.content_type || item.modality || '').toLowerCase())
        );
      }

      // Min confidence client filter
      if (minConfidence > 0) {
        list = list.filter((item) => (item.score || 0) >= minConfidence / 100);
      }

      // Sorting
      if (sortBy === 'newest') {
        list = [...list].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      } else if (sortBy === 'confidence') {
        list = [...list].sort((a, b) => (b.score || 0) - (a.score || 0));
      }

      setResults(list);
      setTotalCount(res.total != null ? res.total : list.length);

      // Log telemetry event
      postSearchEvent('SEARCH', {
        query_terms: query,
        mode,
        filters: { modalities: selectedModalities, minConfidence },
      });
    } catch (err) {
      setError(err.message || 'Search execution failed');
      if (showToast) showToast(err.message || 'Search failed', 'error');
    } finally {
      setLoading(false);
    }
  }, [query, mode, selectedModalities, minConfidence, sortBy, showToast]);

  useEffect(() => {
    executeSearch();
  }, [executeSearch]);

  const toggleModality = (id) => {
    setSelectedModalities((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const handleOpenDoc = (fileId) => {
    postSearchEvent('RESULT_CLICK', { file_id: fileId, query_terms: query });
    setActiveDocId(fileId);
  };

  const resetFilters = () => {
    setSelectedModalities([]);
    setMinConfidence(0);
    setQuery('');
  };

  return (
    <>
      <div className="flex flex-col gap-5">
        <PageHeading title="Multimodal Search" description="Find the right file across every connected source." />
        {/* Search Header Panel */}
        <div className="nx-panel p-6 flex flex-col gap-3.5">
          {/* Search Input Box */}
          <div className="search-field relative flex items-center bg-nexus-elevated border border-nexus-borderStrong rounded-sm pl-3 pr-[5px] h-11 transition-colors">
            <SearchIcon className="w-4 h-4 text-nexus-textMuted shrink-0 mr-2.5" />
            <input
              id="admin-search-input" aria-label="Search data catalog"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
              placeholder={
                mode === 'similar'
                  ? 'Enter Document ID or filename for reference file similarity...'
                  : mode === 'text'
                  ? 'Enter exact keywords, OCR tokens, or metadata tags...'
                  : 'Search multimodal objects with natural language or semantic description...'
              }
              className="w-full h-full !min-h-0 bg-transparent text-sm text-nexus-textPrimary outline-none placeholder:text-nexus-textMuted"
            />
            {query && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => {
                  setQuery('');
                  document.getElementById('admin-search-input')?.focus();
                }}
                className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary"
              >
                <CloseIcon className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={executeSearch}
              className="ml-2 h-8 px-3 inline-flex items-center justify-center bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-lg transition-colors shrink-0"
            >
              Search
            </button>
          </div>

          {/* Controls Bar: Mode Switcher & View Switcher */}
          <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-3 flex-wrap gap-2">
            <div className="flex items-center gap-1.5 bg-nexus-elevated border border-nexus-border rounded-sm p-0.5">
              {[
                { id: 'vector', label: 'Neural / Vector' },
                { id: 'text', label: 'Exact Keyword' },
                { id: 'similar', label: 'Find Similar' },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`px-3 py-1 text-sm rounded-xs font-medium transition-colors ${
                    mode === m.id
                      ? 'bg-nexus-brandSubtle text-nexus-brandText font-semibold border border-nexus-border'
                      : 'text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover border border-transparent'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 bg-nexus-elevated border border-nexus-border rounded-sm p-0.5">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-xs transition-colors ${
                  viewMode === 'grid' ? 'bg-nexus-surface text-nexus-brandText' : 'text-nexus-textMuted hover:text-nexus-textPrimary'
                }`}
                title="Grid View"
              >
                <GridIcon className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-xs transition-colors ${
                  viewMode === 'table' ? 'bg-nexus-surface text-nexus-brandText' : 'text-nexus-textMuted hover:text-nexus-textPrimary'
                }`}
                title="Table View"
              >
                <ListIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Example Queries */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold text-nexus-textMuted uppercase font-mono">Try:</span>
            {exampleQueries.map((ex, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setQuery(ex)}
                className="text-sm px-2.5 py-1 rounded-sm bg-nexus-elevated hover:bg-nexus-hover hover:border-nexus-brand border border-nexus-border text-nexus-textSecondary hover:text-nexus-brandText transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* Search Workspace (Sidebar Filters + Results Area) */}
        <div className="grid grid-cols-1 lg:grid-cols-[230px_1fr] gap-5 items-start">
          {/* Filters Sidebar */}
          <aside className="nx-panel p-6 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-2.5">
              <div className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-nexus-textPrimary font-mono">
                <FilterIcon className="w-3.5 h-3.5 text-nexus-brandText" />
                <span>Filters</span>
              </div>
              <button
                type="button"
                onClick={resetFilters}
                className="text-sm text-nexus-textMuted hover:text-nexus-brandText transition-colors"
              >
                Reset
              </button>
            </div>

            {/* Modality Filter */}
            <div className="flex flex-col gap-2 border-b border-nexus-borderSubtle pb-3">
              <span className="text-sm font-bold text-nexus-textSecondary">Content Modality</span>
              <div className="flex flex-col gap-1.5">
                {availableFacets.map((fac) => (
                  <label
                    key={fac}
                    className="flex items-center gap-2 text-sm text-nexus-textSecondary hover:text-nexus-textPrimary cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={selectedModalities.includes(fac)}
                      onChange={() => toggleModality(fac)}
                      className="accent-nexus-brand rounded-xs"
                    />
                    <span className="capitalize">{fac}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Minimum Confidence Slider */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-bold text-nexus-textSecondary">Min Confidence</span>
                <span className="font-mono text-nexus-brandText font-semibold">{minConfidence}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="95"
                step="5"
                aria-label="Minimum confidence" value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="accent-nexus-brand cursor-pointer w-full"
              />
            </div>
          </aside>

          {/* Results Main Area */}
          <section aria-label="Search results" className="flex flex-col gap-3 min-w-0">
            {/* Stats Bar */}
            <div className="flex items-center justify-between text-sm text-nexus-textMuted flex-wrap gap-2">
              <div>
                {loading ? (
                  <span>Executing vector search query...</span>
                ) : query ? (
                  <span>
                    Found <strong className="text-nexus-textPrimary">{totalCount}</strong> objects matching &quot;<em>{query}</em>&quot;
                  </span>
                ) : (
                  <span>
                    Showing <strong className="text-nexus-textPrimary">{totalCount}</strong> indexed files
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <span>Sort by:</span>
                <select
                  aria-label="Sort results" value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="bg-nexus-surface border border-nexus-border text-nexus-textPrimary text-sm px-2 py-1 rounded-sm outline-none font-medium"
                >
                  <option value="relevance">Relevance / Match Score</option>
                  <option value="confidence">AI Confidence</option>
                  <option value="newest">Newest Indexed</option>
                </select>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-950/30 border border-red-800 text-nexus-danger text-sm rounded-sm">
                {error}
              </div>
            )}

            {/* Skeletons while loading */}
            {loading && results.length === 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div
                    key={i}
                    className="nx-panel p-6 flex flex-col gap-3 animate-pulse h-40"
                  >
                    <div className="h-4 bg-nexus-elevated rounded-xs w-1/3" />
                    <div className="h-4 bg-nexus-elevated rounded-xs w-3/4" />
                    <div className="h-10 bg-nexus-elevated rounded-xs mt-auto" />
                  </div>
                ))}
              </div>
            )}

            {/* Empty State */}
            {!loading && results.length === 0 && (
              <div className="bg-nexus-surface border border-nexus-border p-12 rounded-sm text-center flex flex-col items-center gap-2">
                <SearchIcon className="w-8 h-8 text-nexus-textMuted" />
                <div className="text-sm font-bold text-nexus-textPrimary">No matching objects found</div>
                <div className="text-sm text-nexus-textMuted max-w-sm">
                  Try adjusting keywords, switching search modes, or lowering the minimum confidence threshold.
                </div>
              </div>
            )}

            {/* Results Table View */}
            {results.length > 0 && viewMode === 'table' && (
              <div aria-busy={loading} className="nx-panel overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-nexus-border bg-nexus-elevated text-nexus-textMuted font-mono text-sm uppercase">
                      <th className="p-3">Filename / ID</th>
                      <th className="p-3">Modality</th>
                      <th className="p-3">AI Finding / Description</th>
                      <th className="p-3">Match</th>
                      <th className="p-3">Indexed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-nexus-borderSubtle">
                    {results.map((doc) => (
                      <tr
                        key={doc.file_id || doc.id}
                        onClick={() => handleOpenDoc(doc.file_id || doc.id)}
                        className="hover:bg-nexus-hover cursor-pointer transition-colors"
                      >
                        <td className="p-3">
                          <strong className="text-nexus-textPrimary block">{doc.name || doc.filename}</strong>
                          <span className="font-mono text-sm text-nexus-textMuted">
                            {(doc.file_id || doc.id).slice(0, 18)}...
                          </span>
                        </td>
                        <td className="p-3">
                          <ModalityBadge type={doc.content_type || doc.modality} />
                        </td>
                        <td className="p-3 text-sm text-nexus-textSecondary max-w-xs truncate">
                          {doc.description || 'Neural indexed data object'}
                        </td>
                        <td className="p-3">
                          {doc.score != null ? (
                            <span className="font-mono font-bold text-nexus-brandText text-sm">
                              {Math.round(doc.score * 100)}%
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="p-3 font-mono text-nexus-textMuted text-sm">
                          {doc.created_at ? doc.created_at.slice(0, 10) : '2026-08-24'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Results Grid View */}
            {results.length > 0 && viewMode === 'grid' && (
              <div aria-busy={loading} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {results.map((doc, index) => (
                  <SearchResultCard
                    index={index}
                    key={doc.file_id || doc.id}
                    result={doc}
                    onOpen={() => handleOpenDoc(doc.file_id || doc.id)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Inspector Drawer */}
      <Presence>{activeDocId && (
        <ModalDetail
          docId={activeDocId}
          onClose={() => setActiveDocId(null)}
          showToast={showToast}
        />
      )}</Presence>
    </>
  );
};
