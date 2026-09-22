import { DialogBackdrop } from './DialogBackdrop';
import React, { useState, useEffect } from 'react';
import {ProtectedPreview} from './ProtectedPreview';
import {getCurrentUser} from '../services/auth';
import { getFile } from '../services/searchApi';
import { createBatchDownload } from '../services/downloadApi';
import { SimilarSearchButton } from './SimilarSearchButton';
import { ModalityBadge } from './ModalityBadge';
import {
  CloseIcon,
  BookmarkIcon,
  CopyIcon,
  DownloadIcon,
  ImageIcon,
  VideoIcon,
  AudioIcon,
  DocumentIcon,
  PlayIcon,
  SpinnerIcon,
} from './Icons';

/**
 * ModalDetail — Inspector drawer for viewing file metadata, neural enrichment tags,
 * vector similarity search, and dispatching download presigned URLs.
 */
export const ModalDetail = ({ docId, onClose, showToast, onSelectResult, filters = {} }) => {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const bookmarkKey = `nexus_saved_docs:${getCurrentUser()?.email || 'session'}`;
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setDoc(null); setError(''); setLoading(true);
    getFile(docId,controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setDoc(data);
      try {setIsSaved(JSON.parse(localStorage.getItem(bookmarkKey) || '[]').includes(docId));} catch {setIsSaved(false);}
    }).catch(err => {if (!controller.signal.aborted) setError(err.message);})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [docId,bookmarkKey]);

  if (!docId) return null;

  const handleToggleSave = () => {
    let savedList; try {savedList = JSON.parse(localStorage.getItem(bookmarkKey) || '[]');} catch {savedList = [];}
    let updated;
    if (savedList.includes(docId)) {
      updated = savedList.filter((id) => id !== docId);
      setIsSaved(false);
      if (showToast) showToast('Removed from saved bookmarks', 'info');
    } else {
      updated = [...savedList, docId];
      setIsSaved(true);
      if (showToast) showToast('Saved file to bookmarks', 'success');
    }
    localStorage.setItem(bookmarkKey, JSON.stringify(updated));
  };

  const handleCopyUri = async () => {
    if (!doc?.sourceUri) return;
    try {await navigator.clipboard.writeText(doc.sourceUri);showToast?.('Copied source URI','success');}
    catch {setError('Unable to copy to clipboard.');}
  };
  const handleDownload = async () => {
    setBusy(true); setError('');
    try {await createBatchDownload([docId]);showToast?.('Download requested. Follow its progress in Downloads.','info');}
    catch (err) {setError(err.message);}
    finally {setBusy(false);}
  };
  const renderMediaViewer = () => <ProtectedPreview documentId={docId} modality={doc.modality} name={doc.filename} text={doc.ocrText}/>;

  return (
    <DialogBackdrop onClose={onClose}
      onClick={onClose}
    >
      <div
        className="detail-dialog max-w-2xl p-6 flex flex-col gap-5 dialog-surface" role="dialog" aria-modal="true" aria-label="File details" tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-nexus-textMuted py-16">
            <SpinnerIcon className="w-6 h-6 animate-spin text-nexus-brandText" />
            <span className="text-sm">Loading file inspector...</span>
          </div>
        ) : !doc ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-nexus-textMuted py-16">
            <span className="text-sm">{error || 'File details could not be retrieved.'}</span>
            <button
              onClick={onClose}
              aria-label="Close dialog" className="mt-2 text-sm px-3 py-1.5 bg-nexus-elevated border border-nexus-border rounded-sm text-nexus-textPrimary"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-start justify-between border-b border-nexus-border pb-3.5">
              <div className="flex flex-col min-w-0 pr-4">
                <ModalityBadge type={doc.modality || doc.content_type} />
                <h2
                  className="text-sm font-bold text-nexus-textPrimary truncate mt-1.5"
                  title={doc.filename || doc.name}
                >
                  {doc.filename || doc.name}
                </h2>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={handleToggleSave} title="Save this file ID in this browser for your account."
                  aria-pressed={isSaved}
                  className={`p-1.5 rounded-xs border text-sm flex items-center gap-1 transition-colors ${
                    isSaved
                      ? 'bg-nexus-brandSubtle border-nexus-border text-nexus-brandText'
                      : 'bg-nexus-elevated border-nexus-border text-nexus-textMuted hover:text-nexus-textPrimary'
                  }`}
                >
                  <BookmarkIcon className="w-3.5 h-3.5" />
                  <span>{isSaved ? 'Saved' : 'Save'}</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close dialog" className="p-1.5 text-nexus-textMuted hover:text-nexus-textPrimary"
                >
                  <CloseIcon className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Media Viewer */}
            {renderMediaViewer()}

            {/* AI Summary */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                AI Summary & Findings
              </span>
              <p className="text-sm text-nexus-textPrimary bg-nexus-elevated p-3 rounded-xs border border-nexus-borderSubtle leading-relaxed">
                {doc.aiDescription || doc.description || 'AI summary unavailable.'}
              </p>
            </div>

            {/* AI Tags */}
            {doc.tags && doc.tags.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                  AI & Vendor Tags
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {doc.tags.map((t) => (
                    <span
                      key={t}
                      className="text-sm px-2 py-0.5 bg-nexus-elevated border border-nexus-border rounded-xs text-nexus-brandText font-medium"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Technical Metadata */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Storage & Technical Details
              </span>
              <div className="grid grid-cols-[130px_1fr] gap-2 text-sm bg-nexus-elevated p-3.5 rounded-sm border border-nexus-borderSubtle">
                <span className="text-nexus-textMuted">File ID:</span>
                <span className="font-mono text-nexus-brandText truncate">{doc.id || docId}</span>

                <span className="text-nexus-textMuted">Storage Location:</span>
                <span className="font-mono text-nexus-textPrimary break-all">
                  {doc.sourceUri || 'Unavailable in the authorized metadata response'}
                </span>

                <span className="text-nexus-textMuted">Data Source:</span>
                <span className="text-nexus-textPrimary">{doc.source || 'Unavailable'}</span>

                {doc.checksum && (
                  <>
                    <span className="text-nexus-textMuted">SHA-256:</span>
                    <span className="font-mono text-nexus-textMuted text-sm truncate">{doc.checksum}</span>
                  </>
                )}

                <span className="text-nexus-textMuted">File Size:</span>
                <span className="font-mono text-nexus-textPrimary">{doc.fileSize || 'Unavailable'}</span>

                {(doc.confidence || doc.score) != null && (
                  <>
                    <span className="text-nexus-textMuted">Confidence:</span>
                    <span className="text-[#4ade80] font-semibold font-mono">
                      {Math.round((doc.confidence || doc.score) * 100)}%
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Similar Vector Search Feature */}
            <div className="pt-1">
              <SimilarSearchButton fileId={doc.id || docId} onSelectResult={onSelectResult} filters={filters}/>
            </div>

            {error && <p role="alert" className="text-sm text-nexus-danger">{error}</p>}
            {/* Actions */}
            <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={handleCopyUri} disabled={!doc.sourceUri} title={!doc.sourceUri ? 'Source URI is not exposed by this endpoint.' : undefined}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border rounded-sm text-sm font-semibold text-nexus-textPrimary transition-colors"
              >
                <CopyIcon className="w-3.5 h-3.5" />
                <span>Copy Source URI</span>
              </button>
              <button
                type="button"
                onClick={handleDownload} disabled={busy}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover text-white rounded-sm text-sm font-semibold transition-colors"
              >
                <DownloadIcon className="w-3.5 h-3.5" />
                <span>Download Object</span>
              </button>
            </div>
          </>
        )}
      </div>
    </DialogBackdrop>
  );
};
