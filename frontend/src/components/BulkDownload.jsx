import React, { useEffect, useState } from 'react';
import { planDownload, createBatchDownload, getDownloadStatus } from '../services/downloadApi';
import { saveArchive } from '../services/http';
import { formatBytes } from '../services/sizes';
import { ArchiveParts } from './ArchiveParts';
import { DownloadIcon, SpinnerIcon } from './Icons';

const POLL_MS = 2000;
const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;

// Why a selection does not fit, in the terms the user can act on.
const overLimit = plan => plan.count > plan.limits.max_files
  ? `At most ${plan.limits.max_files.toLocaleString()} files can be downloaded at once.`
  : `This is ${formatBytes(plan.total_bytes)}; the limit is ${formatBytes(plan.limits.max_total_bytes)} per download.`;

/**
 * Download the top N results of the current search. Shows the file count and estimated size
 * before anything is prepared, and how many files fit when the request is too large.
 */
export const BulkDownload = ({ catalog }) => {
  const total = catalog.totalCount;
  const [countText, setCountText] = useState('');
  const count = countText === '' ? null : Number(countText);
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState('');
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const active = catalog.hasSearch && total > 0;
  const searchKey = JSON.stringify(catalog.searchParams);

  useEffect(() => {
    if (!active) { setPlan(null); return undefined; }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPlanError('');
      planDownload(catalog.searchParams, { count, signal: controller.signal })
        .then(setPlan)
        .catch(e => { if (e.name !== 'AbortError') { setPlan(null); setPlanError(e.message); } });
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [searchKey, count, active]);

  useEffect(() => {
    if (job?.status !== 'building') return undefined;
    let stopped = false, timer;
    const poll = async () => {
      try {
        const next = await getDownloadStatus(job.download_id);
        if (stopped) return;
        setJob(next); setError('');
        if (next.status === 'building') timer = setTimeout(poll, POLL_MS);
      } catch (e) { if (!stopped) { setError(e.message); timer = setTimeout(poll, POLL_MS * 2); } }
    };
    timer = setTimeout(poll, POLL_MS);
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.download_id, job?.status]);

  if (!active) return null;

  const start = async () => {
    setBusy(true); setError('');
    try {
      const chosen = await planDownload(catalog.searchParams, { count, includeIds: true });
      if (!chosen.within_limits) throw new Error(overLimit(chosen));
      setJob(await createBatchDownload(chosen.file_ids));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const save = async part => {
    setBusy(true); setError('');
    const partBytes = job.parts?.find(item => item.index === part)?.size_bytes;
    try { await saveArchive(job.download_id, part, job.part_count || 1, partBytes); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const reset = () => { setJob(null); setError(''); };

  const blocked = !plan || !plan.within_limits || busy;
  return (
    <section aria-label="Download results" className="nx-panel p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider font-mono text-nexus-textPrimary">
        <DownloadIcon className="w-4 h-4 text-nexus-brandText" /><span>Download results</span>
      </div>

      {!job && (
        <>
          <div className="flex items-center gap-2 flex-wrap text-sm text-nexus-textSecondary">
            <label htmlFor="bulk-count">Number of files</label>
            <input id="bulk-count" aria-label="Number of files to download" inputMode="numeric" placeholder="All" className="nx-input w-28"
              value={countText} onChange={e => setCountText(e.target.value.replace(/[^0-9]/g, '').slice(0, 7))} />
            <span>of {total.toLocaleString()} results</span>
            {[100, 1000].filter(n => n < total).map(n => (
              <button key={n} type="button" className="nx-button" onClick={() => setCountText(String(n))}>{n.toLocaleString()}</button>
            ))}
            <button type="button" className="nx-button" onClick={() => setCountText('')}>All</button>
          </div>

          <div aria-live="polite" className="text-sm flex flex-col gap-1.5">
            {planError && <p role="alert" className="text-nexus-danger">{planError}</p>}
            {!plan && !planError && <p className="text-nexus-textMuted">Estimating size…</p>}
            {plan && plan.count > 0 && (
              <p className="text-nexus-textPrimary">
                <strong>≈ {formatBytes(plan.total_bytes)} source data</strong> · {plural(plan.count, 'file')}
                {plan.estimated_parts > 1 && ` · ${plan.estimated_parts} archive parts of up to ${formatBytes(plan.limits.part_bytes)}`}
              </p>
            )}
            {plan && plan.count > 0 && <p className="text-xs text-nexus-textMuted">Estimate uses original file sizes; watermarking and ZIP packaging can change the final archive sizes.</p>}
            {plan && plan.count === 0 && (
              <p className="text-nexus-textMuted">
                {plan.oversized_in_scan > 0
                  ? `None of these results can be downloaded: each is larger than ${formatBytes(plan.limits.max_file_bytes)}.`
                  : 'Enter a number greater than 0.'}
              </p>
            )}
            {plan && plan.excluded_oversized > 0 && plan.count > 0 && (
              <p className="text-xs text-nexus-textMuted">{plural(plan.excluded_oversized, 'file')} larger than {formatBytes(plan.limits.max_file_bytes)} {plan.excluded_oversized === 1 ? 'is' : 'are'} left out.</p>
            )}
            {plan && plan.truncated && <p className="text-xs text-nexus-textMuted">Only the top results were scanned; the estimate covers those.</p>}
            {plan && !plan.within_limits && plan.count > 0 && (
              <div role="alert" className="flex items-center gap-3 flex-wrap text-nexus-danger">
                <span>{overLimit(plan)}</span>
                {plan.fit_count > 0 && (
                  <button type="button" className="nx-button" onClick={() => setCountText(String(plan.fit_count))}>Use {plan.fit_count.toLocaleString()} files</button>
                )}
              </div>
            )}
          </div>

          {error && <p role="alert" className="text-sm text-nexus-danger">{error}</p>}
          <div>
            <button type="button" className="nx-button nx-button--primary" onClick={start} disabled={blocked}>
              {busy ? 'Preparing…' : plan?.count ? `Prepare ${plural(plan.count, 'file')}` : 'Prepare download'}
            </button>
          </div>
        </>
      )}

      {job && (
        <div className="flex flex-col gap-2 text-sm">
          {job.status === 'building' && (
            <>
              <p className="flex items-center gap-2 text-nexus-textPrimary"><SpinnerIcon className="w-4 h-4 animate-spin" />Preparing {plural(job.file_count, 'file')}…</p>
              <progress className="w-full" value={job.progress || 0} max={job.file_count || 1} aria-label="Packaging progress" />
              <p className="font-mono text-nexus-textMuted">{(job.progress || 0).toLocaleString()} of {job.file_count.toLocaleString()} packaged · you can leave this page; it continues under Downloads</p>
            </>
          )}
          {job.status === 'ready' && (
            <>
              <p className="text-nexus-textPrimary">Ready · {formatBytes(job.archive_bytes)} in {plural(job.part_count || 1, 'archive')}. Available for one day.</p>
              <ArchiveParts job={job} onSave={save} busy={busy} />
            </>
          )}
          {job.status === 'failed' && <p role="alert" className="text-nexus-danger">{job.error || 'The download could not be prepared.'}</p>}
          {error && <p role="alert" className="text-nexus-danger">{error}</p>}
          {job.status !== 'building' && <div><button type="button" className="nx-button" onClick={reset}>{job.status === 'ready' ? 'Done' : 'Try again'}</button></div>}
        </div>
      )}
    </section>
  );
};
