import { Presence, FeedbackMotion } from '../components/Motion';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {useCatalog,CatalogPagination,CatalogFilters} from '../components/CatalogControls';
import { TrendingSearches } from '../components/TrendingSearches';
import { PopularDatasets } from '../components/PopularDatasets';
import { SearchResultCard } from '../components/SearchResultCard';
import { DownloadBar } from '../components/DownloadBar';
import { CatalogSelection } from '../components/CatalogSelection';
import { ModalDetail } from '../components/ModalDetail';
import {
  SearchIcon,
  CloseIcon,
  SpinnerIcon,
  ArrowUpLeftIcon,
} from '../components/Icons';

const DEBOUNCE_MS = 300;

/**
 * UserSearchView — User workspace for discovering datasets, searching multimodal files,
 * previewing neural annotations, and exporting batch downloads.
 */
export const UserSearchView = ({ showToast }) => {
  const catalog = useCatalog({limit:30});
  const {query,setQuery,debouncedQuery,mode,setMode,results,totalCount,loading,error,selectedFileIds,setSelectedFileIds,activeDocId,setActiveDocId,suggestions,showSuggestions,setShowSuggestions,searchInputRef,handleSelectSuggestion,handleOpenDocument,toggleSelect,hasSearch} = catalog;
  const contentTypeFilter = catalog.filters.file_types?.[0] === 'csv' ? 'tabular' : catalog.filters.file_types?.[0] || '';
  const setContentTypeFilter = value => catalog.selectModality(value ? [value] : []);
  const handleBrowseDataset = (id) => {catalog.setFilters(f => ({...f,dataset_ids:[id]})); setQuery('');};

  return (
    <>
      <div className="flex flex-col gap-6 max-w-5xl mx-auto pb-24">
        <div className="catalog-intro"><h1>Search datasets</h1><p>Find files across the connected catalog.</p></div>
        {/* Search header panel */}
        <div className="catalog-search flex flex-col gap-3.5">
          <div className="flex items-center justify-between">
            <h2 className="panel-title">Search Data Catalog</h2>
            {/* Search mode tabs */}
            <div className="flex items-center gap-1 bg-nexus-elevated border border-nexus-border rounded-sm p-0.5">
              {[
                { id: 'hybrid', label: 'Hybrid' },
                { id: 'vector', label: 'Semantic' },
                { id: 'text', label: 'Exact Keyword' },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`px-2.5 py-0.5 text-sm rounded-xs font-medium transition-colors ${
                    mode === m.id
                      ? 'bg-nexus-brandSubtle text-nexus-brandText font-semibold border border-nexus-border'
                      : 'text-nexus-textSecondary hover:text-nexus-textPrimary'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search bar with Autocomplete */}
          <div className="relative">
            <div className="search-field relative flex items-center bg-nexus-elevated border border-nexus-borderStrong rounded-sm px-3 h-11 transition-colors">
              <SearchIcon className="w-4 h-4 text-nexus-textMuted shrink-0 mr-2.5" />
              <input
                ref={searchInputRef}
                id="user-search-input"
                aria-label="Search data catalog" role="combobox" aria-expanded={showSuggestions && suggestions.length > 0} aria-controls="user-suggestions" aria-activedescendant={catalog.highlight >= 0 ? `user-suggestion-${catalog.highlight}` : undefined} onKeyDown={catalog.onSearchKeyDown}
                type="search"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => {
                  // Delay blur to allow clicking suggestion item
                  setTimeout(() => setShowSuggestions(false), 200);
                }}
                placeholder={
                  mode === 'text'
                    ? 'Search by exact keyword, filename, or metadata tag...'
                    : 'Search across all datasets using natural language description...'
                }
                className="flex-1 bg-transparent text-sm text-nexus-textPrimary outline-none placeholder:text-nexus-textMuted"
              />
              {query && (
                <button
                  type="button"
                  aria-label="Clear search"
                  onClick={() => {
                    setQuery('');

                    searchInputRef.current?.focus();
                  }}
                  className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
                >
                  <CloseIcon className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Suggestions Dropdown */}
            <Presence>{showSuggestions && suggestions.length > 0 && (
              <FeedbackMotion id="user-suggestions" role="listbox" className="absolute top-full left-0 right-0 mt-1 bg-nexus-surface border border-nexus-borderStrong rounded-sm shadow-xl z-40 overflow-hidden divide-y divide-nexus-borderSubtle">
                {suggestions.map((s, idx) => (
                  <button
                    key={idx} id={`user-suggestion-${idx}`} role="option" aria-selected={catalog.highlight === idx}
                    type="button"
                    onMouseDown={e => e.preventDefault()} onClick={() => handleSelectSuggestion(typeof s === 'string' ? s : s.text || s.query)}
                    className="w-full text-left px-3.5 py-2 text-sm text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover flex items-center justify-between transition-colors"
                  >
                    <span>{typeof s === 'string' ? s : s.text || s.query}</span>
                    <ArrowUpLeftIcon className="w-3.5 h-3.5 text-nexus-textMuted" />
                  </button>
                ))}
              </FeedbackMotion>
            )}</Presence>
          </div>

          {/* Content Type Filter Chips */}
          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
            {[
              { id: '', label: 'All Modalities' },
              { id: 'image', label: 'Images' },
              { id: 'video', label: 'Videos' },
              { id: 'document', label: 'Documents' },
              { id: 'audio', label: 'Audio' },
              { id: 'tabular', label: 'Tabular' },
            ].map((item) => {
              const active = contentTypeFilter === item.id;
              return (
                <button
                  key={item.id || 'all'}
                  type="button"
                  onClick={() => setContentTypeFilter(item.id)}
                  className={`text-sm px-2.5 py-1 rounded-sm border transition-colors ${
                    active
                      ? 'bg-nexus-brandSubtle text-nexus-brandText border-nexus-border font-semibold'
                      : 'bg-nexus-elevated text-nexus-textMuted border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textSecondary'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <CatalogFilters catalog={catalog}/>{error && <p role="alert" className="text-sm text-nexus-danger">{error}</p>}
        {/* Pre-search view: Trending Searches + Popular Datasets */}
        {!hasSearch && (
          <div className="flex flex-col gap-6">
            <TrendingSearches onSelectTerm={(term) => setQuery(term)} />
            <PopularDatasets onBrowse={handleBrowseDataset} />
          </div>
        )}

        {/* Active Search Results */}
        {hasSearch && (
          <div className="flex flex-col gap-3.5">
            {/* Stats Bar */}
            <div className="flex items-center justify-between text-sm text-nexus-textMuted">
              <span>
                {loading
                  ? 'Searching index...'
                  : `Found ${totalCount} file${totalCount !== 1 ? 's' : ''} matching "${debouncedQuery}"`}
              </span>
              {selectedFileIds.length > 0 && (
                <span className="font-mono text-nexus-brandText font-semibold">
                  {selectedFileIds.length} file{selectedFileIds.length !== 1 ? 's' : ''} selected
                </span>
              )}
            </div>

            {/* Skeletons */}
            <CatalogSelection catalog={catalog}/>
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
                <div className="text-sm font-bold text-nexus-textPrimary">No matching files found</div>
                <div className="text-sm text-nexus-textMuted max-w-sm">
                  Try different keywords, switch to exact keyword search, or reset modality filters.
                </div>
              </div>
            )}

            {/* Results Grid */}
            {results.length > 0 && (
              <div aria-busy={loading} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {results.map((doc, index) => (
                  <SearchResultCard
                    index={index}
                    key={doc.file_id || doc.id}
                    result={doc}
                    isSelected={selectedFileIds.includes(doc.file_id || doc.id)}
                    selectionDisabled={selectedFileIds.length >= 100}
                    onToggleSelect={() => toggleSelect(doc.file_id || doc.id)}
                    onOpen={() => handleOpenDocument(doc.file_id || doc.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {hasSearch && <CatalogPagination catalog={catalog}/>}
      {/* Sticky Bottom Batch Download Bar */}
      <DownloadBar
        selectedFileIds={selectedFileIds}
        onClear={() => setSelectedFileIds([])}
        onShowToast={showToast}
      />

      {/* Document Inspector Modal */}
      <Presence>{activeDocId && (
        <ModalDetail
          docId={activeDocId}
          onClose={() => setActiveDocId(null)}
          showToast={showToast}
          onSelectResult={item => setActiveDocId(item.file_id)} filters={catalog.filters}
        />
      )}</Presence>
    </>
  );
};
