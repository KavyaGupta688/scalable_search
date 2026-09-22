import React, { useState, useEffect } from 'react';
import { search, getSuggestions, getTrending, getPopularDatasets, getSimilar } from '../services/searchApi';
import { SearchResultCard } from '../components/SearchResultCard';
import { ModalDetail } from '../components/ModalDetail';
import { DownloadBar } from '../components/DownloadBar';
import { Presence } from '../components/Motion';

export function CatalogView({ showToast }) {
  const [query,setQuery] = useState(''); const [submitted,setSubmitted] = useState('');
  const [mode,setMode] = useState('hybrid'); const [filters,setFilters] = useState({});
  const [page,setPage] = useState(0); const [data,setData] = useState(null);
  const [busy,setBusy] = useState(false); const [error,setError] = useState('');
  const [suggestions,setSuggestions] = useState([]); const [highlight,setHighlight] = useState(-1);
  const [discovery,setDiscovery] = useState({trending:[],datasets:[]});
  const [selected,setSelected] = useState([]); const [active,setActive] = useState(null);
  const [similar,setSimilar] = useState(null); const [similarTitle,setSimilarTitle] = useState('selected file'); const [suggesting,setSuggesting] = useState(false);
  useEffect(() => { let current=true; Promise.all([getTrending(),getPopularDatasets()]).then(([t,d])=>{if(current)setDiscovery({trending:t.trending,datasets:d.datasets});}).catch(e=>{if(current)setError(e.message);}); return()=>{current=false;}; },[]);
  useEffect(() => {
    const controller=new AbortController(); setSuggestions([]); setHighlight(-1);
    if (!query.trim() || !suggesting || active) return;
    const timer=setTimeout(()=>getSuggestions(query.trim(),controller.signal).then(setSuggestions).catch(e=>{if(e.name!=='AbortError')setError(`Suggestions unavailable: ${e.message}`);}),250);
    return()=>{clearTimeout(timer);controller.abort();};
  },[query,suggesting,active]);
  useEffect(() => {
    if (!submitted && !similar) return;
    const controller=new AbortController(); setBusy(true);setError('');setData(null);setSelected([]);
    const pending=similar?getSimilar(similar,filters,controller.signal):search(submitted,mode,filters,20,page*20,controller.signal);
    pending.then(d=>{if(!controller.signal.aborted)setData(d);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setBusy(false);});
    return()=>controller.abort();
  },[submitted,mode,filters,page,similar]);
  const submit=(value=query)=>{setQuery(value);setSubmitted(value.trim());setPage(0);setSimilar(null);setSuggesting(false);setSuggestions([]);};
  const facet=(key,value)=>{setPage(0);setFilters(f=>({...f,[key]:value?[value]:undefined}));};
  const facetOptions=(key,facetKey)=>{
    const items=data?.facets?.[facetKey]||[]; const selected=filters[key]?.[0];
    return selected&&!items.some(item=>item.value===selected)?[{value:selected,count:null},...items]:items;
  };
  return <div className="flex flex-col gap-6">
    <header className="catalog-intro"><h1 className="page-title">Discover your data</h1><p>Search connected sources and explore enriched content.</p></header>
    <form className="nx-panel p-4 flex flex-wrap gap-3" onSubmit={e=>{e.preventDefault();submit(highlight>=0?suggestions[highlight]?.text:query);}}>
      <div className="relative flex-1 min-w-[240px]"><input className="nx-input w-full" aria-label="Search files" role="combobox" aria-expanded={suggestions.length>0} aria-controls="suggestions" aria-autocomplete="list" aria-activedescendant={highlight>=0?`suggestion-${highlight}`:undefined} placeholder="Describe what you are looking for" value={query} onFocus={()=>setSuggesting(true)} onChange={e=>{setQuery(e.target.value);setSuggesting(true);}} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();setHighlight(i=>Math.min(i+1,suggestions.length-1));}if(e.key==='ArrowUp'){e.preventDefault();setHighlight(i=>Math.max(i-1,-1));}if(e.key==='Escape'){setSuggesting(false);setSuggestions([]);}}} />
        {!!suggestions.length&&<ul id="suggestions" role="listbox" className="nx-panel absolute z-20 w-full p-2">{suggestions.map((s,i)=><li key={s.text} id={`suggestion-${i}`} role="option" aria-selected={i===highlight}><button type="button" className={`w-full text-left p-2 ${i===highlight?'bg-nexus-hover':''}`} onClick={()=>submit(s.text)}>{s.text}</button></li>)}</ul>}
      </div>
      <select className="nx-input" aria-label="Search mode" value={mode} onChange={e=>{setMode(e.target.value);setPage(0);}}>{['hybrid','text','vector'].map(m=><option key={m} value={m}>{m}</option>)}</select>
      <button className="nx-button nx-button--primary" disabled={!query.trim()}>Search</button>
    </form>
    <div className="flex flex-wrap gap-3">
      {[['file_types','File type','file_types'],['categories','Category','categories'],['dataset_ids','Dataset','datasets'],['tags','Tag','top_tags']].map(([key,label,facetKey])=><select key={key} className="nx-input" aria-label={label} value={filters[key]?.[0]||''} onChange={e=>facet(key,e.target.value)}><option value="">All {label.toLowerCase()}s</option>{facetOptions(key,facetKey).map(f=><option key={f.value} value={f.value}>{key==='dataset_ids'?(discovery.datasets.find(d=>d.dataset_id===f.value)?.dataset_name||f.value):f.value}{f.count==null?'':` (${f.count})`}</option>)}</select>)}
      <button className="nx-button" onClick={()=>{setFilters({});setPage(0);}}>Clear filters</button>
    </div>
    <details className="nx-panel p-4"><summary>More filters</summary><div className="flex flex-wrap gap-3 mt-3">
      {[['ai_generated','AI-origin flag'],['pii_detected','PII detected']].map(([key,label])=><label key={key}>{label}<select className="nx-input block" value={filters[key]===undefined?'':String(filters[key])} onChange={e=>{setPage(0);setFilters(f=>({...f,[key]:e.target.value===''?undefined:e.target.value==='true'}));}}><option value="">Any</option><option value="true">{key === 'ai_generated' ? 'Flagged' : 'Yes'}</option><option value="false">{key === 'ai_generated' ? 'Not flagged' : 'No'}</option></select></label>)}
      <p className="text-xs text-nexus-textMuted">AI-origin flags are model estimates. Not flagged includes missed detections or missing assessments; it does not confirm human origin.</p>
      {[['date_from','Ingested from'],['date_to','Ingested until']].map(([key,label])=><label key={key}>{label}<input className="nx-input block" type="date" value={filters[key]?.slice(0,10)||''} onChange={e=>{setPage(0);setFilters(f=>({...f,[key]:e.target.value?e.target.value+(key==='date_to'?'T23:59:59Z':'T00:00:00Z'):undefined}));}}/></label>)}
      {[['min_width','Minimum width'],['min_duration','Minimum seconds'],['max_duration','Maximum seconds']].map(([key,label])=><label key={key}>{label}<input className="nx-input block w-40" type="number" min="0" value={filters[key]??''} onChange={e=>{setPage(0);setFilters(f=>({...f,[key]:e.target.value===''?undefined:Number(e.target.value)}));}}/></label>)}
    </div></details>
    {error&&<p role="alert" className="nx-panel p-4 text-red-400">{error}</p>}
    {busy&&<p role="status">Searching…</p>}
    {!submitted&&!similar&&<div className="grid md:grid-cols-2 gap-4"><section className="nx-panel p-5"><h2>Trending searches</h2>{discovery.trending.length?discovery.trending.map(t=><button className="nx-button m-1" key={t.query} onClick={()=>submit(t.query)}>{t.query}</button>):<p>No recent searches.</p>}</section><section className="nx-panel p-5"><h2>Popular datasets</h2>{discovery.datasets.length?discovery.datasets.map(d=><button className="nx-button m-1" key={d.dataset_id} onClick={()=>{facet('dataset_ids',d.dataset_id);setMode('text');submit('*');}}>{d.dataset_name}</button>):<p>No published datasets.</p>}</section></div>}
    {similar&&<div><span>Files similar to {similarTitle}</span><button className="nx-button ml-3" onClick={()=>setSimilar(null)}>Return to search</button></div>}
    {data&&<><p role="status">{data.total} results</p><div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">{data.results.map((r,i)=><SearchResultCard key={r.file_id} result={r} index={i} isSelected={selected.includes(r.file_id)} onToggleSelect={()=>setSelected(s=>s.includes(r.file_id)?s.filter(id=>id!==r.file_id):[...s,r.file_id])} onOpen={()=>{setSuggesting(false);setSuggestions([]);setActive(r.file_id);}}/>)}</div>{!data.results.length&&<p className="nx-panel p-6">No matching files. Try another query or adjust the filters.</p>}{!similar&&<nav aria-label="Result pages" className="flex gap-4 items-center"><button className="nx-button" disabled={!page||busy} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page+1}</span><button className="nx-button" disabled={(page+1)*20>=data.total||busy} onClick={()=>setPage(p=>p+1)}>Next</button></nav>}</>}
    <DownloadBar selectedFileIds={selected} onClear={()=>setSelected([])} onShowToast={showToast}/>
    <Presence>{active&&<ModalDetail docId={active} onClose={()=>setActive(null)} showToast={showToast} onSimilar={(id,title)=>{setSimilarTitle(title||'selected file');setActive(null);setSuggesting(false);setSuggestions([]);setSimilar(id);setPage(0);}}/>}</Presence>
  </div>;
}
