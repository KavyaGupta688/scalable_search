import { DialogBackdrop } from './DialogBackdrop';
import React, { useState, useEffect } from 'react';
import { getFile, postSearchEvent } from '../services/searchApi';
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
export const ModalDetail = ({ docId, onClose, showToast }) => {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (!docId) return;
    setLoading(true);

    // Track FILE_PREVIEW event
    postSearchEvent('FILE_PREVIEW', { file_id: docId });

    getFile(docId)
      .then((data) => {
        setDoc(data);
        // Check saved status in localStorage
        const savedList = JSON.parse(localStorage.getItem('nexus_saved_docs') || '[]');
        setIsSaved(savedList.includes(docId));
      })
      .catch((err) => {
        if (showToast) showToast(`Failed to load file details: ${err.message}`, 'error');
      })
      .finally(() => setLoading(false));
  }, [docId, showToast]);

  if (!docId) return null;

  const handleToggleSave = () => {
    const savedList = JSON.parse(localStorage.getItem('nexus_saved_docs') || '[]');
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
    localStorage.setItem('nexus_saved_docs', JSON.stringify(updated));
  };

  const handleCopyUri = () => {
    const uri = doc?.sourceUri || doc?.endpoint_or_path || `s3://data-lake/${doc?.filename || docId}`;
    if (navigator.clipboard) navigator.clipboard.writeText(uri);
    if (showToast) showToast(`Copied URI: ${uri}`, 'success');
  };

  const handleDownload = async () => {
    if (!doc) return;
    try {
      if (showToast) showToast(`Generating presigned URL for ${doc.filename || doc.name}...`, 'info');
      const data = await createBatchDownload([doc.id || docId]);
      if (data.download_url) {
        window.open(data.download_url, '_blank', 'noopener');
      }
      if (showToast) showToast(data.download_url ? `Download ready for ${doc.filename || doc.name}` : 'Download request added. Follow its progress in Downloads.', 'info');
    } catch (err) {
      if (showToast) showToast(err.message || 'Download request failed', 'error');
    }
  };

  const renderMediaViewer = () => {
    if (!doc) return null;
    const modality = (doc.modality || doc.content_type || 'document').toLowerCase();

    if (modality === 'image') {
      return (
        <div className="h-56 bg-black rounded-sm relative flex items-center justify-center overflow-hidden border border-nexus-borderSubtle">
          {doc.thumbnail_url || doc.preview_url ? (
            <img
              src={doc.thumbnail_url || doc.preview_url}
              alt={doc.filename}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="text-center text-nexus-textMuted flex flex-col items-center gap-1.5">
              <ImageIcon className="w-8 h-8 text-nexus-brandText" />
              <span className="text-sm font-mono uppercase tracking-wider">
                Optical Micrograph Sample
              </span>
            </div>
          )}
          {doc.detectedObjects && doc.detectedObjects.length > 0 && (
            <div className="absolute top-[20%] left-[55%] w-[30%] h-[35%] border-2 border-red-500 bg-red-500/15 rounded-xs">
              <span className="absolute -top-4 left-0 bg-red-500 text-white text-sm font-bold px-1 py-0.5">
                Glass Fissure (96.8%)
              </span>
            </div>
          )}
        </div>
      );
    }

    if (modality === 'video') {
      return (
        <div className="h-48 bg-black rounded-sm flex flex-col items-center justify-center gap-2 border border-nexus-borderSubtle relative">
          <div className="w-11 h-11 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center text-white cursor-pointer transition-colors">
            <PlayIcon className="w-5 h-5 ml-0.5" />
          </div>
          <span className="text-sm text-nexus-textMuted font-mono">
            Inspection Feed (1080p 60fps)
          </span>
        </div>
      );
    }

    if (modality === 'audio') {
      return (
        <div className="bg-nexus-elevated border border-nexus-borderSubtle rounded-sm p-4 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-nexus-brand text-white flex items-center justify-center">
              <PlayIcon className="w-4 h-4 ml-0.5" />
            </div>
            <div>
              <div className="text-sm font-bold text-nexus-textPrimary">
                Acoustic Sensor Audio Stream
              </div>
              <div className="font-mono text-sm text-nexus-textMuted">
                48 kHz · 24-bit PCM WAV
              </div>
            </div>
          </div>
          <div className="h-8 flex items-center gap-0.5">
            {Array.from({ length: 36 }).map((_, i) => (
              <div
                key={i}
                className="flex-1 bg-nexus-brandText rounded-2xs"
                style={{
                  height: `${Math.sin(i * 0.45) * 12 + 16}px`,
                  opacity: i < 16 ? 0.9 : 0.35,
                }}
              />
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className="bg-nexus-elevated border border-nexus-borderSubtle rounded-sm p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm font-bold text-nexus-textPrimary">
          <DocumentIcon className="w-4 h-4 text-nexus-brandText" />
          <span>{doc.filename || doc.name}</span>
        </div>
        <div className="font-mono text-sm text-nexus-textSecondary bg-nexus-surface p-2.5 rounded-xs border border-nexus-borderSubtle leading-relaxed">
          {doc.ocrText || doc.ocr_text || doc.description || 'Extracted document content indexed in multimodal database.'}
        </div>
      </div>
    );
  };

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
            <span className="text-sm">File details could not be retrieved.</span>
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
                  onClick={handleToggleSave}
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
                {doc.aiDescription || doc.description || 'Neural classification completed. Modality vector extracted and indexed in Qdrant cluster.'}
              </p>
            </div>

            {/* AI Tags */}
            {doc.tags && doc.tags.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                  AI Tags
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
                  {doc.sourceUri || doc.endpoint_or_path || `s3://data-fabric/${doc.filename || doc.name}`}
                </span>

                <span className="text-nexus-textMuted">Data Source:</span>
                <span className="text-nexus-textPrimary">{doc.source || 'S3 Production Bucket'}</span>

                {doc.checksum && (
                  <>
                    <span className="text-nexus-textMuted">SHA-256:</span>
                    <span className="font-mono text-nexus-textMuted text-sm truncate">{doc.checksum}</span>
                  </>
                )}

                <span className="text-nexus-textMuted">File Size:</span>
                <span className="font-mono text-nexus-textPrimary">{doc.fileSize || '3.4 MB'}</span>

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
              <SimilarSearchButton fileId={doc.id || docId} />
            </div>

            {/* Actions */}
            <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={handleCopyUri}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border rounded-sm text-sm font-semibold text-nexus-textPrimary transition-colors"
              >
                <CopyIcon className="w-3.5 h-3.5" />
                <span>Copy S3 URI</span>
              </button>
              <button
                type="button"
                onClick={handleDownload}
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
