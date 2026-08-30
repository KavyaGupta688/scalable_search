import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  SearchIcon,
  FilterIcon,
  GridIcon,
  ListIcon,
  CloseIcon,
  ImageIcon,
  VideoIcon,
  AudioIcon,
  DocumentIcon,
  TabularIcon
} from '../components/Icons';

export const SearchView = ({ onOpenDocument, onShowToast }) => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('natural');
  const [viewMode, setViewMode] = useState('grid');
  const [selectedModalities, setSelectedModalities] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [minConfidence, setMinConfidence] = useState(0);
  const [sortBy, setSortBy] = useState('relevance');
  const [results, setResults] = useState([]);
  const [totalCount, setTotalCount] = useState(0);

  const exampleQueries = [
    "Cracked OLED display panels",
    "Robotic assembly line videos",
    "Display panel quality failures",
    "Motor vibration acoustic anomalies",
    "OLED defect records CSV"
  ];

  const modalitiesList = [
    { id: 'image', label: 'Images' },
    { id: 'video', label: 'Videos' },
    { id: 'document', label: 'Documents' },
    { id: 'audio', label: 'Audio' },
    { id: 'tabular', label: 'Tabular' }
  ];

  const dataSources = api.getDataSources();

  const handleSearch = async () => {
    const res = await api.search({
      query,
      mode,
      modalities: selectedModalities,
      sources: selectedSources,
      minConfidence,
      sortBy
    });
    setResults(res.results);
    setTotalCount(res.total);
  };

  useEffect(() => {
    handleSearch();
  }, [query, mode, selectedModalities, selectedSources, minConfidence, sortBy]);

  const toggleModality = (id) => {
    setSelectedModalities((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const toggleSource = (sourceName) => {
    setSelectedSources((prev) =>
      prev.includes(sourceName) ? prev.filter((s) => s !== sourceName) : [...prev, sourceName]
    );
  };

  const resetFilters = () => {
    setSelectedModalities([]);
    setSelectedSources([]);
    setMinConfidence(0);
    setQuery('');
  };

  const renderModalityIcon = (mod) => {
    switch (mod) {
      case 'image': return <ImageIcon className="w-4 h-4" />;
      case 'video': return <VideoIcon className="w-4 h-4" />;
      case 'audio': return <AudioIcon className="w-4 h-4" />;
      case 'tabular': return <TabularIcon className="w-4 h-4" />;
      default: return <DocumentIcon className="w-4 h-4" />;
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Search Header Panel */}
      <div className="bg-prism-surface border border-prism-border p-5 rounded-sm flex flex-col gap-3.5">
        {/* Search Input Box */}
        <div className="relative flex items-center bg-prism-elevated border border-prism-borderStrong focus-within:border-prism-brand rounded-sm px-3 h-11 transition-colors">
          <SearchIcon className="w-4 h-4 text-prism-textMuted shrink-0 mr-2.5" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={
              mode === 'similar'
                ? "Enter Document ID or filename for reference file similarity..."
                : mode === 'keyword'
                ? "Enter exact keywords, OCR text tokens, or tags..."
                : "Search S3 objects with natural language, tags, or filenames..."
            }
            className="w-full bg-transparent text-xs text-prism-textPrimary outline-none placeholder:text-prism-textMuted"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-1 text-prism-textMuted hover:text-prism-textPrimary"
            >
              <CloseIcon className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={handleSearch}
            className="ml-2 px-3 py-1.5 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors"
          >
            Search
          </button>
        </div>

        {/* Mode Tabs & View Toggle */}
        <div className="flex items-center justify-between border-b border-prism-borderSubtle pb-3">
          <div className="flex items-center gap-1.5">
            {[
              { id: 'natural', label: 'Natural Language' },
              { id: 'keyword', label: 'Exact Keyword' },
              { id: 'similar', label: 'Similar S3 Object' }
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={`px-3 py-1 text-xs font-medium rounded-sm transition-colors ${
                  mode === m.id
                    ? 'bg-prism-brandSubtle text-prism-brandText font-semibold border border-[#23426e]'
                    : 'text-prism-textSecondary hover:text-prism-textPrimary hover:bg-prism-hover border border-transparent'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 bg-prism-elevated border border-prism-border rounded-sm p-0.5">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1 rounded-xs transition-colors ${
                viewMode === 'grid' ? 'bg-prism-surface text-prism-brandText' : 'text-prism-textMuted hover:text-prism-textPrimary'
              }`}
              title="Grid View"
            >
              <GridIcon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1 rounded-xs transition-colors ${
                viewMode === 'table' ? 'bg-prism-surface text-prism-brandText' : 'text-prism-textMuted hover:text-prism-textPrimary'
              }`}
              title="Table View"
            >
              <ListIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Interactive Query Chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold text-prism-textMuted uppercase font-mono">Try:</span>
          {exampleQueries.map((q) => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="text-[11px] px-2.5 py-1 rounded-sm bg-prism-elevated hover:bg-prism-hover hover:border-prism-brand border border-prism-border text-prism-textSecondary hover:text-prism-brandText transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Layout: Filters + Results */}
      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-5 items-start">
        {/* Left Filter Sidebar */}
        <aside className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-prism-borderSubtle pb-2.5">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-prism-textPrimary font-mono">
              <FilterIcon className="w-3.5 h-3.5" />
              <span>Filters</span>
            </div>
            <button
              onClick={resetFilters}
              className="text-[11px] text-prism-textMuted hover:text-prism-brandText transition-colors"
            >
              Reset
            </button>
          </div>

          {/* Modality Filter */}
          <div className="flex flex-col gap-2 border-b border-prism-borderSubtle pb-3">
            <span className="text-[11px] font-bold text-prism-textSecondary">Modality</span>
            <div className="flex flex-col gap-1.5">
              {modalitiesList.map((m) => (
                <label key={m.id} className="flex items-center gap-2 text-xs text-prism-textSecondary hover:text-prism-textPrimary cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selectedModalities.includes(m.id)}
                    onChange={() => toggleModality(m.id)}
                    className="accent-prism-brand rounded-xs"
                  />
                  <span>{m.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* S3 Bucket Filter */}
          <div className="flex flex-col gap-2 border-b border-prism-borderSubtle pb-3">
            <span className="text-[11px] font-bold text-prism-textSecondary">S3 Bucket</span>
            <div className="flex flex-col gap-1.5">
              {dataSources.map((src) => (
                <label key={src.id} className="flex items-center gap-2 text-xs text-prism-textSecondary hover:text-prism-textPrimary cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(src.name)}
                    onChange={() => toggleSource(src.name)}
                    className="accent-prism-brand rounded-xs"
                  />
                  <span className="truncate" title={src.name}>{src.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Confidence Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-bold text-prism-textSecondary">Min AI Confidence</span>
              <span className="font-mono text-prism-brandText font-semibold">{minConfidence}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="95"
              step="5"
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="accent-prism-brand cursor-pointer w-full"
            />
          </div>
        </aside>

        {/* Right Results Area */}
        <main className="flex flex-col gap-3.5">
          {/* Results Header Stats & Sort */}
          <div className="flex items-center justify-between text-xs text-prism-textMuted">
            <div>
              {query ? (
                <span>Found <strong className="text-prism-textPrimary">{totalCount}</strong> S3 objects matching "<em>{query}</em>"</span>
              ) : (
                <span>Showing <strong className="text-prism-textPrimary">{totalCount}</strong> indexed S3 objects</span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="sort-select" className="text-[11px]">Sort by:</label>
              <select
                id="sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-prism-surface border border-prism-border text-prism-textPrimary text-xs px-2 py-1 rounded-sm outline-none"
              >
                <option value="relevance">AI Relevance</option>
                <option value="date-desc">Newest First</option>
                <option value="size-desc">File Size</option>
              </select>
            </div>
          </div>

          {/* Result Cards Grid or Table */}
          {results.length === 0 ? (
            <div className="bg-prism-surface border border-prism-border p-12 rounded-sm text-center flex flex-col items-center gap-2">
              <SearchIcon className="w-8 h-8 text-prism-textMuted" />
              <div className="text-sm font-bold text-prism-textPrimary">No matching S3 objects found</div>
              <div className="text-xs text-prism-textMuted max-w-sm">
                Try adjusting your search query, clearing filters, or searching for other defect tags.
              </div>
            </div>
          ) : viewMode === 'table' ? (
            <div className="bg-prism-surface border border-prism-border rounded-sm overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-prism-border bg-prism-elevated text-prism-textMuted font-mono text-[10px] uppercase">
                    <th className="p-3">Filename & Preview</th>
                    <th className="p-3">Modality</th>
                    <th className="p-3">S3 Bucket</th>
                    <th className="p-3">AI Caption</th>
                    <th className="p-3">Score</th>
                    <th className="p-3">Size</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-prism-borderSubtle">
                  {results.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => onOpenDocument(doc.id)}
                      className="hover:bg-prism-hover cursor-pointer transition-colors"
                    >
                      <td className="p-3">
                        <strong className="text-prism-textPrimary block">{doc.filename}</strong>
                        <span className="font-mono text-[10px] text-prism-textMuted">{doc.id.slice(0, 18)}...</span>
                      </td>
                      <td className="p-3">
                        <span className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-xs bg-blue-500/10 text-blue-400">
                          {doc.modality}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[11px] text-prism-textSecondary">
                        {doc.sourceUri.split('/')[2]}
                      </td>
                      <td className="p-3 text-[11px] text-prism-textSecondary max-w-xs truncate">
                        {doc.canonicalCaption}
                      </td>
                      <td className="p-3">
                        <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-mono">
                          {Math.round((doc.searchScore || doc.relevanceScore) * 100)}%
                        </span>
                      </td>
                      <td className="p-3 font-mono text-prism-textMuted text-[11px]">{doc.fileSize}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {results.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => onOpenDocument(doc.id)}
                  className="bg-prism-surface border border-prism-border hover:border-prism-borderStrong rounded-sm overflow-hidden flex flex-col cursor-pointer transition-colors"
                >
                  {/* Thumbnail / Header */}
                  <div className="h-28 bg-[#0a101d] flex items-center justify-center text-prism-textMuted relative">
                    {renderModalityIcon(doc.modality)}
                    <span className="absolute top-2 left-2 text-[9px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-xs bg-blue-500/20 text-blue-300">
                      {doc.modality}
                    </span>
                    <span className="absolute top-2 right-2 text-[10px] font-mono font-bold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded-xs">
                      {Math.round((doc.searchScore || doc.relevanceScore) * 100)}% match
                    </span>
                  </div>

                  {/* Body */}
                  <div className="p-3.5 flex flex-col gap-2 flex-1">
                    <span className="text-xs font-bold text-prism-textPrimary truncate" title={doc.filename}>
                      {doc.filename}
                    </span>
                    <p className="text-[11px] text-prism-textSecondary line-clamp-2 leading-snug">
                      {doc.canonicalCaption}
                    </p>

                    <div className="flex flex-wrap gap-1 mt-auto pt-1">
                      {doc.tags.slice(0, 3).map((t) => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-xs bg-prism-elevated border border-prism-borderSubtle text-prism-textMuted">
                          {t}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center justify-between text-[10px] font-mono text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-1">
                      <span className="truncate max-w-[140px]" title={doc.sourceUri}>
                        s3://{doc.sourceUri.split('/')[2]}
                      </span>
                      <span>{doc.fileSize}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
