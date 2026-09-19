import React, { useState, useEffect } from 'react';
import { Presence, FeedbackMotion } from './Motion';
import {saveArchive} from '../services/http';
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
  const [job,setJob] = useState(null);
  const [loading,setLoading] = useState(false);
  const [statusError,setStatusError] = useState('');
  const downloadStatus = job?.status || null;
  const fileCount = job?.file_count ?? selectedFileIds.length;
  const downloadUrl = job?.status === 'ready';
  useEffect(() => {
    if (job?.status !== 'building') return;
    let stopped = false, timer;
    const poll = async () => {
      try {const next=await getDownloadStatus(job.download_id);if (!stopped) {setJob(next);setStatusError('');if(next.status === 'building') timer=setTimeout(poll,2000);}}
      catch (err) {if (!stopped) {setStatusError(err.message);timer=setTimeout(poll,5000);}}
    };
    timer=setTimeout(poll,2000);
    return () => {stopped=true;clearTimeout(timer);};
  }, [job?.download_id,job?.status]);
  const handleStartDownload = async () => {
    setLoading(true);setStatusError('');
    try {setJob(await createBatchDownload(selectedFileIds));}
    catch (err) {setStatusError(err.message);}
    finally {setLoading(false);}
  };
  const handleSave = async () => {
    setLoading(true);setStatusError('');
    try {await saveArchive(job.download_id);} catch (err) {setStatusError(err.message);}
    finally {setLoading(false);}
  };
  const handleReset = () => {setJob(null);setStatusError('');onClear?.();onComplete?.();};

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
                ? (statusError || `${job?.progress ?? 0}/${fileCount} packaged · Follow this request in Downloads`)
                : downloadStatus === 'ready'
                ? (downloadUrl ? 'Your files are ready to download' : 'Archive unavailable')
                : 'Bring these files into your next project'}
            </span>
          </div>
        </div>

        {(statusError || job?.error) && <p role="alert" className="text-sm text-nexus-danger">{statusError || job.error}</p>}
        <div className="flex items-center gap-2.5">
          {(
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

          {downloadStatus === 'ready' && downloadUrl && <button className="nx-button nx-button--primary" onClick={handleSave} disabled={loading}>Save archive</button>}
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
