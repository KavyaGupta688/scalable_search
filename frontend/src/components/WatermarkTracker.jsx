import React, {useRef, useState} from 'react';
import {UploadCloud, ShieldCheck, FileText, X, LoaderCircle} from 'lucide-react';
import {authHeaders} from '../services/auth';

export function WatermarkTracker() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);
  function choose(files) {
    if (busy) return;
    setResult(null); setError(''); setDragging(false);
    if (files.length > 1) {setError('Choose one file at a time.'); return;}
    const next = files[0] || null;
    if (next?.size > 64 * 1024 ** 2) {setFile(null); setError('Choose one extracted file up to 64 MiB.'); return;}
    setFile(next);
  }
  async function trace(event) {
    event.preventDefault(); setError(''); setResult(null);
    if (!file) return;
    if (file.size > 64 * 1024 ** 2) { setError('Choose one extracted file up to 64 MiB.'); return; }
    setBusy(true);
    try {
      const body = new FormData(); body.append('file', file);
      const headers = authHeaders(); delete headers['Content-Type'];
      const response = await fetch('/downloads/forensic/verify', {method:'POST', body, headers});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Verification failed (HTTP ${response.status})`);
      setResult(data);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  const trail = result?.forensic_audit_trail;
  const date = value => value ? new Date(value).toLocaleString() : 'Not recorded';
  const fields = trail ? [
    ['User name', trail.display_name || 'Not recorded'], ['Email', trail.user_email],
    ['User ID', trail.user_id], ['Request IP', trail.client_ip || 'Not recorded for this historical download'],
    ['Requested', date(trail.requested_at)], ['Packaged', date(trail.packaged_at)],
    ['Delivery started', date(trail.delivery_started_at)], ['Processing', trail.execution_mode || 'Historical worker'],
    ['Document ID', trail.document_id], ['Watermark ID', trail.download_id],
    ['Package ID', trail.job_id], ['Watermarks used', trail.watermark_methods?.join(', ') || 'Not recorded'],
    ['Project', trail.request_details?.project_name], ['Purpose of usage', trail.request_details?.usage_purpose],
    ['Licence expiry', date(trail.request_details?.licence_expiry)],
    ['Metadata CSV', trail.request_details ? (trail.request_details.include_metadata_csv ? 'Included' : 'Not included') : 'Not recorded'],
  ] : [];
  return <section className="nx-panel p-5 sm:p-6 space-y-5" aria-label="Administrator watermark tracker">
    <div className="flex items-start gap-3">
      <span className="p-2.5 rounded-xl bg-nexus-elevated border border-nexus-border text-nexus-brandText"><ShieldCheck size={22}/></span>
      <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-3"><h2 className="text-lg font-semibold">Watermark tracker</h2><span className="text-xs text-nexus-brandText border border-nexus-border rounded-full px-2.5 py-1">Administrator only</span></div>
      <p className="text-sm text-nexus-textMuted mt-1">Trace a downloaded file back to its recorded recipient and download activity.</p></div>
    </div>
    <form onSubmit={trace} className="space-y-4">
      <div onDragOver={e=>{e.preventDefault();if(!busy)setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();choose(e.dataTransfer.files);}}
        className={`relative rounded-xl border-2 border-dashed p-5 sm:p-7 text-center transition-colors focus-within:ring-2 focus-within:ring-nexus-brandText ${dragging ? 'border-nexus-brandText bg-nexus-hover' : 'border-nexus-border bg-nexus-elevated/40'} ${busy ? 'opacity-60' : 'hover:bg-nexus-elevated'}`}>
        <input ref={input} aria-label="Downloaded file to trace" type="file" disabled={busy} onChange={e=>choose(e.target.files)} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-wait" />
        <UploadCloud className="w-8 h-8 text-nexus-brandText mx-auto mb-3"/>
        <p className="font-semibold">Drop a file here, or <span className="text-nexus-brandText underline underline-offset-4">browse files</span></p>
        <p className="text-sm text-nexus-textMuted mt-2">One extracted file · up to 64 MiB · no ZIP archives</p>
      </div>
      {file && <div className="flex items-center gap-3 rounded-xl border border-nexus-border bg-nexus-elevated px-4 py-3">
        <FileText className="w-5 h-5 text-nexus-brandText shrink-0"/><div className="min-w-0 flex-1"><p className="text-sm font-semibold break-all">{file.name}</p><p className="text-xs text-nexus-textMuted mt-1">{(file.size / 1024 ** 2).toFixed(2)} MiB · Ready to trace</p></div>
        <button type="button" aria-label="Remove selected file" disabled={busy} onClick={()=>{choose([]);if(input.current)input.current.value='';}} className="p-2 rounded-lg hover:bg-nexus-hover disabled:opacity-40"><X size={18}/></button>
      </div>}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 justify-between"><p className="text-xs text-nexus-textMuted max-w-xl leading-relaxed">For unchanged CSV, JSON or other unsupported formats, select the accompanying <span className="font-mono text-nexus-textSecondary break-all">.watermark.json</span> sidecar. Files are sent for verification only when you select Trace watermark.</p>
      <button className="nx-button shrink-0 inline-flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed" disabled={!file || busy}>{busy ? <LoaderCircle size={17} className="animate-spin"/> : <ShieldCheck size={17}/>} {busy ? 'Tracing…' : 'Trace watermark'}</button></div>
    </form>
    {error && <p role="alert" className="text-nexus-danger rounded-xl border border-red-800/40 bg-red-950/20 p-3 text-sm">{error}</p>}
    {result && <div className="space-y-4 border-t border-nexus-border pt-5" aria-live="polite">
      <p className={`rounded-xl border p-4 text-sm font-semibold ${result.audit_match && !result.identity_conflict ? 'text-emerald-300 border-emerald-800 bg-emerald-950/30' : 'text-amber-300 border-amber-800 bg-amber-950/20'}`}>{result.identity_conflict ? 'Conflicting watermark identities — attribution withheld.' : result.audit_match ? 'Authenticated watermark matches a recorded package.' : 'No authenticated audit match found.'}</p>
      <p className="text-sm text-nexus-textMuted">Metadata: {result.signature_valid ? 'authenticated' : result.message}. Signal: {result.signal_watermark?.authenticated ? result.signal_watermark.method : result.signal_watermark?.reason || 'not authenticated or unsupported'}.</p>
      {trail && <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{fields.map(([label,value]) => <div key={label} className="min-w-0 rounded-xl border border-nexus-borderSubtle bg-nexus-elevated/50 p-3.5"><dt className="text-xs text-nexus-textMuted mb-1.5">{label}</dt><dd className="text-sm break-all">{value || 'Not recorded'}</dd></div>)}</dl>}
      <p className="text-xs text-nexus-textMuted">A match links the recovered identifier to a package; it does not prove who uploaded this file or that its contents are unchanged. Delivery started does not confirm a completed browser download. IP is the address observed by the gateway and may identify a proxy.</p>
    </div>}
  </section>;
}
