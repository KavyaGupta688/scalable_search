import React, {useEffect, useRef, useState} from 'react';
import {saveArchive} from '../services/http';
import {formatBytes} from '../services/sizes';

const duration = seconds => seconds == null ? 'Calculating…' : seconds < 60 ? `${seconds.toFixed(1)} s` : `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;

export function PreparationStats({job}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if(job.status !== 'building') return; const timer=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(timer); }, [job.status]);
  const elapsed = Math.max(0, ((job.status === 'building' ? now : Date.parse(job.updated_at)) - Date.parse(job.created_at)) / 1000);
  if (!Number.isFinite(elapsed)) return null;
  const remaining = job.progress > 0 ? elapsed / job.progress * (job.file_count - job.progress) : null;
  return <p className="text-xs text-nexus-textMuted">{job.status === 'building' ? `Preparing: ${duration(elapsed)} elapsed · Estimated preparation time left: ${duration(remaining)}` : `Preparation ${job.status === 'failed' ? 'stopped after' : 'took'} ${duration(elapsed)}`}. Transfer speed appears when saving the archive.</p>;
}

export function ArchiveDownload({job}) {
  const [stats, setStats] = useState(null);
  const receiptKey = `download-receipts:${job.download_id}`;
  const [receipts, setReceipts] = useState(() => {
    try { const saved = JSON.parse(sessionStorage.getItem(receiptKey) || '[]'); return Array.isArray(saved) ? saved : []; }
    catch { return []; }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  const save = async part => {
    if(controller.current) return;
    controller.current = new AbortController();
    setBusy(true); setError(''); setStats(null);
    try {
      const result = await saveArchive(job.download_id, part.index, job.part_count || 1, part.size_bytes,
        {onProgress:setStats, signal:controller.current.signal});
      setReceipts(previous => {
        const next = [...previous, {...result, part:part.index}].slice(-20);
        try { sessionStorage.setItem(receiptKey, JSON.stringify(next)); } catch { /* Saving files still works when browser storage is disabled. */ }
        return next;
      });
    } catch(e) { setStats(null); setError(e.name === 'AbortError' ? 'Download cancelled.' : e.message); }
    finally { controller.current=null; setBusy(false); }
  };
  const parts = job.parts?.length ? job.parts : [{index:1, size_bytes:job.archive_bytes}];
  const picker = typeof window.showSaveFilePicker === 'function';
  return <div className="flex flex-col gap-3 w-full text-sm text-nexus-textSecondary">
    <p>{picker ? 'Choose a save location for each archive part.' : 'This browser controls the save location. Enable “Ask where to save each file” in browser download settings, or open this page in Chrome / Edge to choose a location here.'}</p>
    <div className="flex flex-wrap gap-2">{parts.map(part => <button key={part.index} type="button" className="nx-button nx-button--primary" disabled={busy} onClick={()=>save(part)}>
      {picker ? 'Choose location & save' : 'Save archive'}{parts.length > 1 ? ` · Part ${part.index}` : ''} · {formatBytes(part.size_bytes)}
    </button>)}</div>
    {busy && stats && <div role="status" className="nx-panel p-3">
      <p>Downloading {stats.filename}</p>
      <progress className="w-full" max={stats.total || undefined} value={stats.total ? stats.bytes : undefined}/>
      <p>{formatBytes(stats.bytes)} / {formatBytes(stats.total)} · Current speed: {formatBytes(stats.speed)}/s</p>
      <p>Time left: {duration(stats.remaining)} · Elapsed: {duration(stats.elapsed)}</p>
      <button className="nx-button mt-2" onClick={()=>controller.current?.abort()}>Cancel transfer</button>
    </div>}
    {error && <p role="alert" className="text-nexus-danger">{error}</p>}
    {receipts.map((receipt,index)=><div key={index} className="nx-panel p-3" role="status">
      <strong>{receipt.state === 'saved' ? 'Download saved' : 'Transferred to browser — check Downloads for save completion'}</strong>
      <p className="break-all">{receipt.filename}</p>
      <p>{formatBytes(receipt.bytes)} · Transfer took {duration(receipt.elapsed)} · Average speed: {formatBytes(receipt.average)}/s</p>
      <p>Finished {new Date(receipt.completedAt).toLocaleString()} · Part {receipt.part} of {parts.length}</p>
    </div>)}
  </div>;
}
