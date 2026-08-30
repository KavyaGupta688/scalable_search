import React, { useState, useEffect, useCallback } from 'react';
import { getDownloadStatus } from '../services/downloadApi';
import { DownloadIcon, ClockIcon, CheckCircleIcon, XCircleIcon, SpinnerIcon } from '../components/Icons';

/**
 * UserDownloadsView — Shows the user's pending and recent downloads.
 * Polls the backend for status of in-progress downloads.
 */
export const UserDownloadsView = ({ showToast }) => {
  const [downloads, setDownloads] = useState(() => {
    const stored = localStorage.getItem('nexus_downloads');
    return stored ? JSON.parse(stored) : [];
  });

  // Persist downloads to local storage
  useEffect(() => {
    localStorage.setItem('nexus_downloads', JSON.stringify(downloads));
  }, [downloads]);

  // Poll for status of building downloads every 4s
  useEffect(() => {
    const building = downloads.filter(d => d.status === 'building');
    if (building.length === 0) return;

    const intervalId = setInterval(async () => {
      const updated = await Promise.all(
        downloads.map(async dl => {
          if (dl.status !== 'building') return dl;
          try {
            const status = await getDownloadStatus(dl.download_id);
            return { ...dl, ...status };
          } catch {
            return dl;
          }
        })
      );
      setDownloads(updated);
    }, 4000);

    return () => clearInterval(intervalId);
  }, [downloads]);

  const handleOpenDownload = useCallback((dl) => {
    if (dl.download_url) {
      window.open(dl.download_url, '_blank', 'noopener');
    } else {
      showToast('Download link not yet ready. Please wait.', 'info');
    }
  }, [showToast]);

  const statusIcon = (status) => {
    if (status === 'building') return <SpinnerIcon className="w-4 h-4 animate-spin text-nexus-brandText" />;
    if (status === 'ready') return <CheckCircleIcon className="w-4 h-4 text-nexus-success" />;
    return <XCircleIcon className="w-4 h-4 text-nexus-danger" />;
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col gap-5 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-nexus-textPrimary">Downloads</h1>
        <span className="text-xs text-nexus-textMuted">{downloads.length} request{downloads.length !== 1 ? 's' : ''}</span>
      </div>

      {downloads.length === 0 && (
        <div className="bg-nexus-surface border border-nexus-border rounded-sm p-12 flex flex-col items-center gap-2 text-center">
          <DownloadIcon className="w-8 h-8 text-nexus-textMuted" />
          <div className="text-sm font-bold text-nexus-textPrimary">No downloads yet</div>
          <p className="text-xs text-nexus-textMuted max-w-xs">
            Select files from the Search view and use the Download button to create a batch.
          </p>
        </div>
      )}

      {downloads.map(dl => (
        <div
          key={dl.download_id}
          className="bg-nexus-surface border border-nexus-border rounded-sm p-4 flex items-center gap-3"
        >
          {/* Status icon */}
          <div className="shrink-0">{statusIcon(dl.status)}</div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-nexus-textPrimary truncate">
              {dl.file_count} file{dl.file_count !== 1 ? 's' : ''}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-nexus-textMuted font-mono mt-0.5">
              <ClockIcon className="w-3 h-3" />
              <span>{formatTime(dl.updated_at)}</span>
              <span className="capitalize">{dl.status}</span>
            </div>
          </div>

          {/* Action */}
          {dl.status === 'ready' && (
            <button
              onClick={() => handleOpenDownload(dl)}
              className="flex items-center gap-1.5 px-3 h-8 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm transition-colors shrink-0"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              <span>Download</span>
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
