import React, { useState, useEffect } from 'react';
import { Presence, FeedbackMotion } from './Motion';
import { createBatchDownload, getDownloadStatus } from '../services/downloadApi';
import { DownloadIcon, SpinnerIcon, CloseIcon, CheckCircleIcon } from './Icons';

/**
 * DownloadBar — Sticky bottom bar for batch file downloads and status monitoring.
 */
export const DownloadBar = ({
  selectedFileIds = [],
  onClear,
  onShowToast,
  onComplete,
}) => {
  const [downloadStatus, setDownloadStatus] = useState(null); // null | 'building' | 'ready' | 'failed'
  const [activeDownloadId, setActiveDownloadId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [statusError, setStatusError] = useState('');
  const [fileCount, setFileCount] = useState(0);

  // Poll for download readiness if building
  useEffect(() => {
    if (downloadStatus !== 'building' || !activeDownloadId) return;

    const interval = setInterval(async () => {
      try {
        const res = await getDownloadStatus(activeDownloadId);
        if (res.status === 'ready') {
          setDownloadStatus('ready');
          setDownloadUrl(res.download_url || null);
          setStatusError('');
          clearInterval(interval);
          if (onShowToast) {
            onShowToast(res.download_url ? 'Batch download archive is ready!' : res.simulated ? 'Prototype complete — no archive was generated.' : 'Request ready; a download link is not available yet.', 'info');
          }
          if (res.download_url) {
            window.open(res.download_url, '_blank', 'noopener');
          }
        } else if (res.status === 'failed') {
          setDownloadStatus('failed');
          clearInterval(interval);
          if (onShowToast) {
            onShowToast('Batch download archive generation failed', 'error');
          }
        }
      } catch (err) {
        setStatusError(err.message);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [downloadStatus, activeDownloadId, onShowToast]);

  const handleStartDownload = async () => {
    if (selectedFileIds.length === 0) return;
    setLoading(true);
    setFileCount(selectedFileIds.length);
    setStatusError('');
    setDownloadUrl(null);
    setDownloadStatus('building');

    try {
      const data = await createBatchDownload(selectedFileIds);
      setActiveDownloadId(data.download_id);
      setFileCount(data.file_count ?? selectedFileIds.length);
      if (data.status === 'ready') { setDownloadStatus('ready'); setDownloadUrl(data.download_url || null); }
      if (onShowToast) {
        onShowToast(`Preparing batch download archive for ${selectedFileIds.length} files...`, 'info');
      }
    } catch (err) {
      setDownloadStatus('failed');
      if (onShowToast) {
        onShowToast(err.message || 'Failed to initiate batch download', 'error');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setDownloadStatus(null);
    setActiveDownloadId(null);
    if (onClear) onClear();
    if (onComplete) onComplete();
  };

  return (
    <Presence>{(selectedFileIds.length > 0 || downloadStatus) &&
    <div className="download-float" role="status" aria-live="polite">
      <FeedbackMotion className="download-surface max-w-5xl mx-auto flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-nexus-border flex items-center justify-center text-nexus-brandText shrink-0">
            {downloadStatus === 'building' ? (
              <SpinnerIcon className="w-4 h-4 animate-spin" />
            ) : downloadStatus === 'ready' ? (
              <CheckCircleIcon className="w-4 h-4 text-[#4ade80]" />
            ) : (
              <DownloadIcon className="w-4 h-4" />
            )}
          </div>

          <div className="flex flex-col">
            <span className="text-sm font-bold text-nexus-textPrimary">
              {downloadStatus === 'building'
                ? `Preparing ${fileCount} files...`
                : downloadStatus === 'ready'
                ? (downloadUrl ? `Archive ready (${fileCount} files)` : `Request complete (${fileCount} files)`)
                : downloadStatus === 'failed'
                ? 'Download failed'
                : `${selectedFileIds.length} file${selectedFileIds.length !== 1 ? 's' : ''} selected`}
            </span>
            <span className="text-sm text-nexus-textMuted font-mono">
              {downloadStatus === 'building'
                ? (statusError || 'You can follow this request in Downloads')
                : downloadStatus === 'ready'
                ? (downloadUrl ? 'Your files are ready to download' : 'No downloadable archive is available in this prototype')
                : 'Bring these files into your next project'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {downloadStatus !== 'building' && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border text-sm text-nexus-textSecondary hover:text-nexus-textPrimary transition-colors"
            >
              <CloseIcon className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          )}

          {(!downloadStatus || downloadStatus === 'failed') && (
            <button
              type="button"
              onClick={handleStartDownload}
              disabled={loading || selectedFileIds.length === 0}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 text-white text-sm font-semibold rounded-sm border border-nexus-brand transition-colors disabled:opacity-50"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              <span>Download Selected</span>
            </button>
          )}

          {downloadStatus === 'ready' && downloadUrl && <a className="nx-button nx-button--primary" href={downloadUrl} target="_blank" rel="noopener noreferrer">Download archive</a>}
          {downloadStatus === 'ready' && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-[#122a1e] hover:bg-[#183929] border border-[#1f5739] text-[#4ade80] text-sm font-semibold rounded-sm transition-colors"
            >
              <CheckCircleIcon className="w-3.5 h-3.5" />
              <span>Done</span>
            </button>
          )}
        </div>
      </FeedbackMotion>
    </div>
    }</Presence>
  );
};
