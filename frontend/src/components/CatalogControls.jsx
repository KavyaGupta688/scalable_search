import React, {useState, useEffect, useRef} from 'react';
import {search, getSuggestions, getFacets} from '../services/searchApi';
import {fileView, backendModality} from '../services/presentation';

export function useCatalog({browse = false, limit = 24} = {}) {
  const [query, setQueryValue] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [mode, setModeValue] = useState('hybrid');
  const [filters, setFilterValues] = useState({});
  const [page, setPage] = useState(0);
  const [revision, refresh] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [facets, setFacets] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [selectedFileIds, setSelectedFileIds] = useState([]);
  const [activeDocId, setActiveDocId] = useState(null);
  const searchInputRef = useRef(null);
  const setQuery = value => {setQueryValue(value); setPage(0);};
  const setMode = value => {setModeValue(value); setPage(0);};
  const setFilters = change => {setFilterValues(change); setPage(0);};
  const hasSearch = browse || Boolean(debouncedQuery.trim()) || Boolean(filters.dataset_ids?.length);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    getFacets(controller.signal).then(setFacets).catch(e => {if (e.name !== 'AbortError') setError(`Filters unavailable: ${e.message}`);});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setSuggestions([]); setHighlight(-1);
    if (!query.trim() || !showSuggestions || activeDocId) return () => controller.abort();
    const timer = setTimeout(() => getSuggestions(query.trim(), controller.signal)
      .then(items => {if (!controller.signal.aborted) setSuggestions(items.slice(0,8));})
      .catch(e => {if (e.name !== 'AbortError') setError(`Suggestions unavailable: ${e.message}`);}), 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query, showSuggestions, activeDocId]);
  useEffect(() => {
    setSelectedFileIds([]);
  }, [debouncedQuery, mode, filters]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    if (!hasSearch) {setLoading(false); return () => controller.abort();}
    setLoading(true);
    search(debouncedQuery.trim() || '*', debouncedQuery.trim() ? mode : 'text', filters, limit, page * limit, controller.signal)
      .then(response => {if (!controller.signal.aborted) {setData({...response, results:response.results.map(fileView)});}})
      .catch(e => {if (!controller.signal.aborted) setError(e.message);})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [debouncedQuery, mode, filters, page, limit, revision, hasSearch]);
  const executeSearch = () => {setDebouncedQuery(query); setShowSuggestions(false); refresh(n => n + 1);};
  const handleSelectSuggestion = text => {setQuery(text); setDebouncedQuery(text); setShowSuggestions(false);};
  const handleOpenDocument = id => {setShowSuggestions(false); setActiveDocId(id);};
  const toggleSelect = id => setSelectedFileIds(ids => ids.includes(id) ? ids.filter(v => v !== id) : ids.length < 100 ? [...ids, id] : ids);
  const selectModality = types => setFilters(f => ({...f, file_types:types.length ? types.map(backendModality) : undefined}));
  const onSearchKeyDown = event => {
    if (event.key === 'ArrowDown') {event.preventDefault(); setHighlight(i => Math.min(i + 1, suggestions.length - 1));}
    if (event.key === 'ArrowUp') {event.preventDefault(); setHighlight(i => Math.max(i - 1, -1));}
    if (event.key === 'Escape') {event.preventDefault(); setShowSuggestions(false);}
    if (event.key === 'Enter') {event.preventDefault(); highlight >= 0 && suggestions[highlight] ? handleSelectSuggestion(suggestions[highlight].text) : executeSearch();}
  };
  return {query,setQuery,debouncedQuery,mode,setMode,filters,setFilters,page,setPage,limit,
    data,results:data?.results || [],totalCount:data?.total || 0,loading,error,facets:data?.facets || facets,
    suggestions,showSuggestions,setShowSuggestions,highlight,onSearchKeyDown,
    selectedFileIds,setSelectedFileIds,activeDocId,setActiveDocId,searchInputRef,hasSearch,
    executeSearch,handleSelectSuggestion,handleOpenDocument,toggleSelect,selectModality};
}

export function CatalogPagination({catalog}) {
  const {page,setPage,limit,totalCount,loading} = catalog;
  return <nav aria-label="Result pages" className={`flex items-center justify-between gap-3 py-3 text-sm ${catalog.selectedFileIds.length ? 'mb-52 sm:mb-32' : ''}`}>
    <button className="nx-button" disabled={!page || loading} onClick={() => setPage(p => p - 1)}>Previous</button>
    <span>Page {page + 1}{totalCount ? ` of ${Math.ceil(totalCount / limit)}` : ''}</span>
    <button className="nx-button" disabled={loading || (page + 1) * limit >= totalCount || (page + 1) * limit > 10000} onClick={() => setPage(p => p + 1)}>Next</button>
  </nav>;
}

export function CatalogFilters({catalog}) {
  const {filters,setFilters,facets} = catalog;
  const choose = (key,value) => setFilters(f => ({...f,[key]:value}));
  return <details className="text-sm border-t border-nexus-borderSubtle pt-3">
    <summary className="cursor-pointer font-semibold text-nexus-textSecondary">More filters</summary>
    <div className="flex flex-wrap gap-3 mt-3">
      {[['dataset_ids','Dataset','datasets'],['categories','Category','categories'],['tags','Tag','top_tags']].map(([key,label,source]) => {
        const values = facets?.[source] || [], selected = filters[key]?.[0];
        return <label key={key} className="flex flex-col gap-1 min-w-0">{label}<select className="nx-input max-w-full" aria-label={label} value={selected || ''} onChange={e => choose(key,e.target.value ? [e.target.value] : undefined)}>
          <option value="">All</option>{selected && !values.some(v => v.value === selected) && <option value={selected}>{selected}</option>}
          {values.map(v => <option value={v.value} key={v.value}>{v.label || v.value} ({v.count})</option>)}</select></label>;
      })}
      {[['ai_generated','AI-origin flag'],['pii_detected','PII detected']].map(([key,label]) => <label key={key} className="flex flex-col gap-1">{label}<select className="nx-input" value={filters[key] == null ? '' : String(filters[key])} onChange={e => choose(key,e.target.value === '' ? undefined : e.target.value === 'true')}><option value="">Any</option><option value="true">{key === 'ai_generated' ? 'Flagged' : 'Yes'}</option><option value="false">{key === 'ai_generated' ? 'Not flagged' : 'No'}</option></select></label>)}
      <p className="text-xs text-nexus-textMuted">AI-origin flags are model estimates. Not flagged includes missed detections or missing assessments; it does not confirm human origin.</p>
      {[['date_from','Ingested from'],['date_to','Ingested until']].map(([key,label]) => <label key={key} className="flex flex-col gap-1">{label}<input type="date" className="nx-input" value={filters[key]?.slice(0,10) || ''} onChange={e => choose(key,e.target.value ? `${e.target.value}${key === 'date_to' ? 'T23:59:59Z' : 'T00:00:00Z'}` : undefined)}/></label>)}
      {[['min_width','Minimum width'],['min_duration','Minimum seconds'],['max_duration','Maximum seconds']].map(([key,label]) => <label key={key} className="flex flex-col gap-1">{label}<input type="number" min="0" className="nx-input w-36" value={filters[key] ?? ''} onChange={e => choose(key,e.target.value === '' ? undefined : Number(e.target.value))}/></label>)}
      <button className="nx-button" onClick={() => setFilters({})}>Clear filters</button>
    </div>
  </details>;
}
