import {useResource,ResourceState} from '../components/ResourceState';
import {saveArchive} from '../services/http';
import React, { useState } from 'react';
import {WatermarkTracker} from '../components/WatermarkTracker';
import { DownloadIcon, ClockIcon, CheckCircleIcon, XCircleIcon, SpinnerIcon } from '../components/Icons';

/**
 * UserDownloadsView — Shows the user's pending and recent downloads.
 * Polls the backend for status of in-progress downloads.
 */
export const UserDownloadsView = ({ showToast, administrator = false }) => {
  const [page,setPage] = useState(0);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const history = useResource(`/downloads?limit=25&offset=${page*25}`, {poll:4000});
  const downloads = history.data?.downloads || [];
  const handleOpenDownload = async dl => {
    setBusy(true); setError('');
    try {await saveArchive(dl.download_id);} catch (err) {setError(err.message);}
    finally {setBusy(false);}
  };
  const statusIcon = (status) => {
    if (status === 'building') return <SpinnerIcon className="w-4 h-4 animate-spin text-nexus-brandText" />;
    if (status === 'ready') return <CheckCircleIcon className="w-4 h-4 text-nexus-success" />;
    return <XCircleIcon className="w-4 h-4 text-nexus-danger" />;
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    return d.toLocaleString([], { month:'short', day:'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="downloads-page flex flex-col gap-5">
      <header className="downloads-heading">
        <div><h1 className="page-title">Downloads</h1><p className="text-sm text-nexus-textMuted mt-2">Your file packages, progress, and download history.</p></div>
        <span className="text-sm text-nexus-textMuted">{downloads.length} request{downloads.length !== 1 ? 's' : ''} on this page</span>
      </header>
      {administrator && <WatermarkTracker />}

      <ResourceState error={error || history.error} loading={history.loading}/>
      {!history.loading && !history.error && downloads.length === 0 && (
        <div className="nx-panel p-12 flex flex-col items-center gap-2 text-center">
          <DownloadIcon className="w-8 h-8 text-nexus-textMuted" />
          <div className="text-sm font-bold text-nexus-textPrimary">No downloads yet</div>
          <p className="text-sm text-nexus-textMuted max-w-xs">
            Select files from the Search view and use the Download button to create a batch.
          </p>
        </div>
      )}

      {downloads.map(dl => (
        <div
          key={dl.download_id}
          className="nx-panel download-request p-5 flex flex-wrap items-center gap-4"
        >
          {/* Status icon */}
          <div className="shrink-0">{statusIcon(dl.status)}</div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-nexus-textPrimary truncate">
              {dl.file_count} file{dl.file_count !== 1 ? 's' : ''}
            </div>
            <div className="flex items-center gap-2 text-sm text-nexus-textMuted font-mono mt-0.5">
              <ClockIcon className="w-3 h-3" />
              <span>{formatTime(dl.updated_at || dl.created_at)}</span>
              <span className="font-sans capitalize">{dl.status}</span>
            </div>
          </div>

          <div className="download-progress text-sm text-nexus-textMuted"><p>{dl.progress ?? 0}/{dl.file_count} packaged</p>{dl.error && <p role="alert" className="text-nexus-danger">{dl.error}</p>}{dl.items?.filter(i => i.error).map(i => <p key={i.document_id} className="break-all">{i.document_id}: {i.error}</p>)}</div>
          {/* Action */}
          {dl.status === 'ready' && (
            <button
              onClick={() => handleOpenDownload(dl)} disabled={busy}
              className="flex items-center gap-1.5 px-3 h-8 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors shrink-0"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              <span>Download</span>
            </button>
          )}
        </div>
      ))}
      <nav aria-label="Download pages" className="flex justify-between items-center text-sm"><button className="nx-button" disabled={!page || history.loading} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page+1} · up to 25 requests</span><button className="nx-button" disabled={downloads.length < 25 || history.loading} onClick={() => setPage(p => p + 1)}>Next</button></nav>
    </div>
  );
};
