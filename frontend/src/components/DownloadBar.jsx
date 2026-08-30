import React, { useState, useEffect } from 'react';
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

  // Poll for download readiness if building
  useEffect(() => {
    if (downloadStatus !== 'building' || !activeDownloadId) return;

    const interval = setInterval(async () => {
      try {
        const res = await getDownloadStatus(activeDownloadId);
        if (res.status === 'ready') {
          setDownloadStatus('ready');
          clearInterval(interval);
          if (onShowToast) {
            onShowToast('Batch download archive is ready!', 'success');
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
        console.error('Polling error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [downloadStatus, activeDownloadId, onShowToast]);

  const handleStartDownload = async () => {
    if (selectedFileIds.length === 0) return;
    setLoading(true);
    setDownloadStatus('building');

    try {
      const data = await createBatchDownload(selectedFileIds);
      setActiveDownloadId(data.download_id);
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

  if (selectedFileIds.length === 0 && !downloadStatus) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-nexus-surface border-t border-nexus-borderStrong shadow-2xl p-4 toast-enter">
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-[#23426e] flex items-center justify-center text-nexus-brandText shrink-0">
            {downloadStatus === 'building' ? (
              <SpinnerIcon className="w-4 h-4 animate-spin" />
            ) : downloadStatus === 'ready' ? (
              <CheckCircleIcon className="w-4 h-4 text-[#4ade80]" />
            ) : (
              <DownloadIcon className="w-4 h-4" />
            )}
          </div>

          <div className="flex flex-col">
            <span className="text-xs font-bold text-nexus-textPrimary">
              {downloadStatus === 'building'
                ? `Building archive for ${selectedFileIds.length} files...`
                : downloadStatus === 'ready'
                ? `Archive ready (${selectedFileIds.length} files)`
                : downloadStatus === 'failed'
                ? 'Download failed'
                : `${selectedFileIds.length} file${selectedFileIds.length !== 1 ? 's' : ''} selected`}
            </span>
            <span className="text-[10px] text-nexus-textMuted font-mono">
              {downloadStatus === 'building'
                ? 'Packaging compressed tar.gz stream on server'
                : downloadStatus === 'ready'
                ? 'Click below if download did not start automatically'
                : 'Batch export via S3 Presigned URLs'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {downloadStatus !== 'building' && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border text-xs text-nexus-textSecondary hover:text-nexus-textPrimary transition-colors"
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
              className="flex items-center gap-1.5 px-4 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 text-white text-xs font-semibold rounded-sm border border-nexus-brand transition-colors disabled:opacity-50"
            >
              <DownloadIcon className="w-3.5 h-3.5" />
              <span>Download Selected</span>
            </button>
          )}

          {downloadStatus === 'ready' && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-[#122a1e] hover:bg-[#183929] border border-[#1f5739] text-[#4ade80] text-xs font-semibold rounded-sm transition-colors"
            >
              <CheckCircleIcon className="w-3.5 h-3.5" />
              <span>Done</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
