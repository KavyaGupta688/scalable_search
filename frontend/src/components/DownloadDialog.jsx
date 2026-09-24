import React, { useEffect, useState } from 'react';
import { DialogBackdrop } from './DialogBackdrop';
import { ArchiveDownload, PreparationStats } from './ArchiveDownload';
import { CloseIcon, DownloadIcon } from './Icons';
import { createBatchDownload, getDownloadStatus, planDownload, previewDownload } from '../services/downloadApi';
import { formatBytes } from '../services/sizes';

const date = value => value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
const labelStyle = 'text-xs font-semibold uppercase tracking-wider text-nexus-textMuted';
const Stat = ({ label, children }) => <div className="nx-panel p-4"><p className={labelStyle}>{label}</p><div className="mt-3 text-nexus-textPrimary">{children}</div></div>;

export function DownloadDialog({ fileIds, searchParams, onClose, onCreated }) {
  const [countText, setCountText] = useState('');
  const [project, setProject] = useState('');
  const [purpose, setPurpose] = useState('');
  const [csv, setCsv] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const key = JSON.stringify({ fileIds, searchParams, countText });
  const current = data?.key === key ? data : null;
  const sourceContext = searchParams ? `Search: ${searchParams.query}` : 'Selected files';

  useEffect(() => {
    if (job) return undefined;
    const controller = new AbortController();
    setError('');
    const timer = setTimeout(async () => {
      try {
        const count = countText === '' ? null : Number(countText);
        if (count !== null && (!Number.isInteger(count) || count < 1)) throw new Error('Enter a positive whole number of files.');
        let ids, available, availableBytes, plan;
        if (searchParams) {
          plan = await planDownload(searchParams, { count, includeIds: true, signal: controller.signal });
          ids = plan.file_ids || [];
          available = plan.available;
          availableBytes = plan.available_bytes;
        } else {
          const allIds = [...new Set(fileIds || [])];
          const all = await previewDownload(allIds, controller.signal);
          available = allIds.length;
          availableBytes = all.total_bytes;
          ids = count === null ? allIds : allIds.slice(0, count);
        }
        const summary = ids.length ? await previewDownload(ids, controller.signal) : null;
        if (!controller.signal.aborted) setData({ key, ids, available, availableBytes, plan, summary });
      } catch (err) { if (!controller.signal.aborted) { setData(null); setError(err.message); } }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [key, job]);

  useEffect(() => {
    if (job?.status !== 'building') return undefined;
    let stopped = false, timer;
    const poll = async () => {
      try {
        const next = await getDownloadStatus(job.download_id);
        if (!stopped) { setJob(next); setError(''); if (next.status === 'building') timer = setTimeout(poll, 2000); }
      } catch (err) { if (!stopped) { setError(err.message); timer = setTimeout(poll, 5000); } }
    };
    timer = setTimeout(poll, 2000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.download_id, job?.status]);

  const submit = async event => {
    event.preventDefault();
    if (busy || !current?.summary?.within_limits || !project.trim() || !purpose.trim()) return;
    setBusy(true); setError('');
    try {
      const next = await createBatchDownload(current.ids, {
        project_name: project.trim(), usage_purpose: purpose.trim(), include_metadata_csv: csv,
        source_context: sourceContext.slice(0, 500),
        displayed_available_count: current.available, displayed_available_bytes: current.availableBytes,
      });
      setJob(next); onCreated?.(next);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const close = () => { if (!busy) onClose(); };
  const summary = current?.summary;
  return <DialogBackdrop onClose={close} onClick={close}>
    <section role="dialog" aria-modal="true" aria-labelledby="download-title" tabIndex={-1}
      className="detail-dialog dialog-surface w-full max-w-3xl p-6 sm:p-8 overflow-y-auto max-h-[90vh]" onClick={e => e.stopPropagation()}>
      <div className="flex justify-between items-start gap-4 mb-5">
        <div><h2 id="download-title" className="text-2xl font-bold text-nexus-textPrimary">Download</h2>
          <p className="text-sm text-nexus-textSecondary mt-2">{searchParams ? 'Download from current search / filters as ZIP' : 'Download selected files as ZIP'}</p>
          <p className="text-sm text-nexus-brandText mt-2 break-words">{summary?.datasets?.join(' · ') || sourceContext}</p></div>
        <button type="button" className="nx-button" aria-label="Close download" disabled={busy} onClick={close}><CloseIcon className="w-5 h-5" /></button>
      </div>
      {job ? <div className="flex flex-col gap-4 text-nexus-textPrimary">
        <p>{job.status === 'building' ? `Preparing ${job.file_count} files…` : job.status === 'ready' ? 'Your download is ready' : 'Download failed'}</p>
        {job.status === 'building' && <><progress className="w-full" value={job.progress || 0} max={job.file_count} /><p className="text-sm text-nexus-textMuted">{job.progress || 0} of {job.file_count} packaged. You can also follow this request in Downloads.</p></>}
        {job.status === 'ready' && <><p>{formatBytes(job.archive_bytes)} · {job.part_count} archive part(s)</p><ArchiveDownload job={job} /></>}
        <PreparationStats job={job} />
        {(job.error || error) && <p role="alert" className="text-nexus-danger">{job.error || error}</p>}
        <button type="button" className="nx-button self-end" disabled={busy} onClick={close}>Close</button>
      </div> : <form onSubmit={submit} className="flex flex-col gap-5">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Stat label="Available"><p className="text-3xl font-bold text-nexus-brandText">{current ? current.available.toLocaleString() : '—'}</p><p className="text-sm text-nexus-textMuted">files</p><div className="border-t border-nexus-border mt-4 pt-3"><strong>{current ? formatBytes(current.availableBytes) : '—'}</strong><p className="text-xs text-nexus-textMuted">total source size</p></div></Stat>
          <Stat label="Download"><label htmlFor="download-count" className="sr-only">Number of files</label><input id="download-count" type="number" min="1" max={current?.available || undefined} placeholder={current?.available?.toString() || "All"} className="nx-input w-full text-2xl font-bold" value={countText} onChange={e => setCountText(e.target.value)} /><p className="text-sm text-nexus-textMuted mt-2">files · of {current?.available.toLocaleString() ?? '…'} available</p></Stat>
          <Stat label="Est. ZIP size"><p className="text-2xl font-bold">{summary ? `≈ ${formatBytes(summary.total_bytes)}` : '—'}</p><p className="text-xs text-nexus-textMuted mt-2">Based on source bytes. Compression and watermarking change the final size.</p><p className="text-xs text-nexus-textMuted border-t border-nexus-border mt-3 pt-3">avg {summary ? formatBytes(summary.average_bytes) : '—'} / file</p></Stat>
        </div>
        {!current && !error && <p role="status" className="text-sm text-nexus-textMuted">Loading download details…</p>}
        {current?.plan?.truncated && <p className="text-sm text-nexus-textMuted">Availability covers the top results scanned.</p>}
        {current && !summary && <p className="text-sm text-nexus-textMuted">No downloadable files in this selection.</p>}
        {summary && (summary.count > summary.limits.max_files || summary.total_bytes > summary.limits.max_total_bytes) && <p role="alert" className="text-sm text-nexus-danger">This request exceeds {summary.limits.max_files.toLocaleString()} files or {formatBytes(summary.limits.max_total_bytes)} total. Choose fewer files.</p>}
        <label className="nx-panel p-4 flex justify-between items-center gap-4 cursor-pointer"><span><strong className="text-nexus-textPrimary">Include Metadata CSV</strong><span className="block text-sm text-nexus-textMuted mt-1">Title, tags, category, dimensions, dataset and licence expiry.</span></span><span className="relative shrink-0"><input type="checkbox" role="switch" aria-label="Include Metadata CSV" checked={csv} onChange={e => setCsv(e.target.checked)} className="sr-only peer" /><span className="block w-12 h-7 rounded-full bg-nexus-borderStrong peer-checked:bg-nexus-brand peer-focus-visible:ring-2 peer-focus-visible:ring-nexus-brandText"><span className="absolute top-1 left-1 h-5 w-5 rounded-full bg-white transition-transform" style={{transform: csv ? "translateX(20px)" : "none"}} /></span></span></label>
        <p className="text-xs text-nexus-textMuted">Each ZIP includes <strong>SHA256SUMS.txt</strong> for its watermarked files. Verify after extracting with <code>sha256sum -c SHA256SUMS.txt</code>.</p>
        <label className="text-sm font-semibold text-nexus-textPrimary">Project Name <span className="text-nexus-danger">* required</span><input required maxLength={200} value={project} onChange={e => setProject(e.target.value)} className="nx-input w-full mt-2" placeholder="e.g. Wildlife Campaign 2026" /></label>
        <label className="text-sm font-semibold text-nexus-textPrimary">Purpose of Usage <span className="text-nexus-danger">* required</span><textarea required maxLength={2000} rows={3} value={purpose} onChange={e => setPurpose(e.target.value)} className="nx-input w-full mt-2 resize-y" placeholder="Describe how these files will be used…" /></label>
        <div className="nx-panel p-4 grid grid-cols-2 gap-4"><div><p className={labelStyle}>Date</p><p className="text-nexus-textPrimary mt-2">{date(summary?.requested_at)}</p></div><div><p className={labelStyle}>Licence expiry</p><p className="text-nexus-textPrimary mt-2">{date(summary?.licence_expiry)}</p>{summary?.licence_expiry !== summary?.latest_licence_expiry && <p className="text-xs text-nexus-textMuted mt-1">Earliest expiry; individual files have different licences.</p>}</div></div>
        {error && <p role="alert" className="text-sm text-nexus-danger">{error}</p>}
        <div className="flex justify-end gap-3"><button type="button" className="nx-button" disabled={busy} onClick={close}>Cancel</button><button type="submit" className="nx-button nx-button--primary flex items-center gap-2" disabled={busy || !summary?.within_limits || !project.trim() || !purpose.trim()}><DownloadIcon className="w-4 h-4" />{busy ? 'Starting…' : 'Start Download'}</button></div>
      </form>}
    </section>
  </DialogBackdrop>;
}
