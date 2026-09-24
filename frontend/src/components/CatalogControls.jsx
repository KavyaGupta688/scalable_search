import React, {useState, useEffect, useRef} from 'react';
import {search, getSuggestions, getFacets} from '../services/searchApi';
import {fileView, backendModality} from '../services/presentation';
import {facetCount} from '../services/facets';
import { ResolutionFilter } from './ResolutionFilter';
import { SizeFilter } from './SizeFilter';

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
  const [lastFacets, setLastFacets] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [selectedFileIds, setSelectedFileIds] = useState([]);
  const [activeDocId, setActiveDocId] = useState(null);
  const searchInputRef = useRef(null);
  const setQuery = value => {setQueryValue(value); setPage(0);};
  const setMode = value => {setModeValue(value); setPage(0);};
  const setFilters = change => {setFilterValues(change); setPage(0);};
  // Any active filter starts a search, so choosing 4K or Images alone lists those files.
  const filterActive = Object.values(filters).some(v => Array.isArray(v) ? v.length > 0 : v !== undefined && v !== null && v !== '');
  const hasSearch = browse || Boolean(debouncedQuery.trim()) || filterActive;
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
    const started = performance.now();
    search(debouncedQuery.trim() || '*', debouncedQuery.trim() ? mode : 'text', filters, limit, page * limit, controller.signal)
      .then(response => {if (!controller.signal.aborted) {setData({...response, elapsed_ms: performance.now() - started, results:response.results.map(fileView)}); setLastFacets(response.facets || null);}})
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
  // The request behind the current results; download planning must ask for the same search.
  const searchParams = {query: debouncedQuery.trim() || '*', mode: debouncedQuery.trim() ? mode : 'text', filters};
  return {query,setQuery,debouncedQuery,mode,setMode,filters,setFilters,page,setPage,limit,searchParams,
    data,results:data?.results || [],totalCount:data?.total || 0,loading,error,facets:hasSearch ? (data?.facets || lastFacets || facets) : facets,
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
  const countLabel = count => typeof count === 'number' ? ` (${count.toLocaleString()})` : '';
  return <details open className="catalog-filters nx-panel p-5 text-sm">
    <summary className="cursor-pointer font-semibold text-nexus-textPrimary">Filters</summary>
    <div className="flex flex-col gap-5 mt-5">
      <div className="catalog-filter-grid">
        {[['dataset_ids','Dataset','datasets'],['categories','Category','categories'],['tags','Tag','top_tags']].map(([key,label,source]) => {
          const values = facets?.[source] || [], selected = filters[key]?.[0];
          return <label key={key} className="flex flex-col gap-2 min-w-0 text-nexus-textSecondary">{label}<select className="nx-input w-full min-w-0" aria-label={label} value={selected || ''} onChange={e => choose(key,e.target.value ? [e.target.value] : undefined)}>
            <option value="">All</option>{selected && !values.some(v => v.value === selected) && <option value={selected}>{selected}</option>}
            {values.map(v => <option value={v.value} key={v.value}>{v.label || v.value} ({v.count})</option>)}</select></label>;
        })}
      </div>
      <div className="border-t border-nexus-borderSubtle pt-4"><ResolutionFilter catalog={catalog} /></div>
      <div className="border-t border-nexus-borderSubtle pt-4"><SizeFilter catalog={catalog} /></div>
      <div className="catalog-filter-grid border-t border-nexus-borderSubtle pt-4">
        {[['date_from','Ingested from'],['date_to','Ingested until']].map(([key,label]) => <label key={key} className="flex flex-col gap-2 min-w-0 text-nexus-textSecondary">{label}<input type="date" className="nx-input w-full min-w-0" value={filters[key]?.slice(0,10) || ''} onChange={e => choose(key,e.target.value ? `${e.target.value}${key === 'date_to' ? 'T23:59:59Z' : 'T00:00:00Z'}` : undefined)}/></label>)}
        {[['min_width','Minimum width (px)'],['min_duration','Minimum duration (s)'],['max_duration','Maximum duration (s)']].map(([key,label]) => <label key={key} className="flex flex-col gap-2 min-w-0 text-nexus-textSecondary">{label}<input type="number" min="0" className="nx-input w-full min-w-0" value={filters[key] ?? ''} onChange={e => choose(key,e.target.value === '' ? undefined : Number(e.target.value))}/></label>)}
      </div>
      <div className="border-t border-nexus-borderSubtle pt-4">
        <div className="catalog-filter-grid">
          {[['ai_generated','AI-origin flag'],['pii_detected','PII detected']].map(([key,label]) => <label key={key} className="flex flex-col gap-2 min-w-0 text-nexus-textSecondary">{label}<select className="nx-input w-full" value={filters[key] == null ? '' : String(filters[key])} onChange={e => choose(key,e.target.value === '' ? undefined : e.target.value === 'true')}><option value="">Any</option><option value="true">{`Yes${countLabel(facetCount(facets,key,true))}`}</option><option value="false">{`No${countLabel(facetCount(facets,key,false))}`}</option></select></label>)}
        </div>
        <p className="text-xs text-nexus-textMuted mt-3 leading-relaxed">AI-origin flags are model estimates. An unflagged file is not confirmed to be human-created.</p>
      </div>
      <div className="flex justify-end border-t border-nexus-borderSubtle pt-4"><button type="button" className="nx-button" onClick={() => setFilters({})}>Clear filters</button></div>
    </div>
  </details>;
}
