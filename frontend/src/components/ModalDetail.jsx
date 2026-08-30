import React, { useState } from 'react';
import { api } from '../services/api';
import {
  CloseIcon,
  BookmarkIcon,
  CopyIcon,
  DownloadIcon,
  ImageIcon,
  VideoIcon,
  AudioIcon,
  DocumentIcon,
  TabularIcon,
  PlayIcon
} from './Icons';

export const ModalDetail = ({ docId, onClose, onShowToast }) => {
  const doc = api.getDocument(docId);
  if (!doc) return null;

  const [isSaved, setIsSaved] = useState(api.isDocumentSaved(doc.id));

  const handleToggleSave = () => {
    const saved = api.toggleSaveDocument(doc.id);
    setIsSaved(saved);
    onShowToast(saved ? 'Saved S3 object to bookmarks' : 'Removed from bookmarks', 'info');
  };

  const handleCopyUri = () => {
    if (navigator.clipboard) navigator.clipboard.writeText(doc.sourceUri);
    onShowToast(`Copied S3 URI: ${doc.sourceUri}`, 'success');
  };

  const handleDownload = () => {
    onShowToast(`Dispatched secure presigned URL for ${doc.filename}`, 'success');
  };

  const renderMediaViewer = () => {
    if (doc.modality === 'image') {
      return (
        <div className="h-60 bg-black rounded-sm relative flex items-center justify-center overflow-hidden border border-prism-borderSubtle">
          <div className="text-center text-prism-textMuted flex flex-col items-center gap-1">
            <ImageIcon className="w-8 h-8" />
            <span className="text-[10px] font-mono uppercase tracking-wider">Optical Micrograph Sample</span>
          </div>
          {doc.detectedObjects && doc.detectedObjects.length > 0 && (
            <div className="absolute top-[20%] left-[55%] w-[30%] h-[35%] border-2 border-red-500 bg-red-500/15 rounded-xs">
              <span className="absolute -top-4 left-0 bg-red-500 text-white text-[9px] font-bold px-1 py-0.5">
                Glass Fissure (96.8%)
              </span>
            </div>
          )}
        </div>
      );
    }

    if (doc.modality === 'video') {
      return (
        <div className="h-52 bg-black rounded-sm flex flex-col items-center justify-center gap-2 border border-prism-borderSubtle relative">
          <div className="w-11 h-11 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center text-white cursor-pointer transition-colors">
            <PlayIcon className="w-5 h-5 ml-0.5" />
          </div>
          <span className="text-[11px] text-prism-textMuted font-mono">Line 02 Robotic Feed (1080p 60fps)</span>
        </div>
      );
    }

    if (doc.modality === 'audio') {
      return (
        <div className="bg-prism-elevated border border-prism-borderSubtle rounded-sm p-4 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-prism-brand text-white flex items-center justify-center">
              <PlayIcon className="w-4 h-4 ml-0.5" />
            </div>
            <div>
              <div className="text-xs font-bold text-prism-textPrimary">Acoustic Vibration Track</div>
              <div className="font-mono text-[10px] text-prism-textMuted">48 kHz · 24-bit PCM WAV</div>
            </div>
          </div>
          <div className="h-9 flex items-center gap-0.5">
            {Array.from({ length: 42 }).map((_, i) => (
              <div
                key={i}
                className="flex-1 bg-blue-500 rounded-2xs"
                style={{
                  height: `${Math.sin(i * 0.4) * 14 + 18}px`,
                  opacity: i < 18 ? 0.9 : 0.3
                }}
              />
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className="bg-prism-elevated border border-prism-borderSubtle rounded-sm p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs font-bold text-prism-textPrimary">
          <DocumentIcon className="w-4 h-4 text-prism-brandText" />
          <span>{doc.filename}</span>
        </div>
        <div className="font-mono text-[11px] text-prism-textSecondary bg-prism-surface p-2.5 rounded-xs border border-prism-borderSubtle leading-relaxed">
          {doc.ocrText || 'Extracted document content indexed in multimodal database.'}
        </div>
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 flex justify-end backdrop-enter"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-prism-surface border-l border-prism-borderStrong h-full p-6 flex flex-col gap-5 overflow-y-auto drawer-enter"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-prism-border pb-3.5">
          <div className="flex flex-col min-w-0 pr-4">
            <span className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-xs bg-blue-500/10 text-blue-400 self-start">
              {doc.modality}
            </span>
            <h2 className="text-sm font-bold text-prism-textPrimary truncate mt-1" title={doc.filename}>
              {doc.filename}
            </h2>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={handleToggleSave}
              className={`p-1.5 rounded-xs border text-xs flex items-center gap-1 transition-colors ${
                isSaved
                  ? 'bg-prism-brandSubtle border-[#23426e] text-prism-brandText'
                  : 'bg-prism-elevated border-prism-border text-prism-textMuted hover:text-prism-textPrimary'
              }`}
            >
              <BookmarkIcon className="w-3.5 h-3.5" />
              <span>{isSaved ? 'Saved' : 'Save'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-prism-textMuted hover:text-prism-textPrimary"
            >
              <CloseIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Media Preview Box */}
        {renderMediaViewer()}

        {/* AI Summary */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
            AI Summary & Findings
          </span>
          <p className="text-xs text-prism-textPrimary bg-prism-elevated p-3 rounded-xs border border-prism-borderSubtle leading-relaxed">
            {doc.aiDescription}
          </p>
        </div>

        {/* AI Tags */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
            AI Tags
          </span>
          <div className="flex flex-wrap gap-1.5">
            {doc.tags.map((t) => (
              <span
                key={t}
                className="text-[11px] px-2 py-0.5 bg-prism-elevated border border-prism-border rounded-xs text-prism-brandText font-medium"
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* Technical Specs List */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
            S3 Technical Details
          </span>
          <div className="grid grid-cols-[130px_1fr] gap-2.5 text-xs bg-prism-elevated p-3.5 rounded-sm border border-prism-borderSubtle">
            <span className="text-prism-textMuted">Document ID:</span>
            <span className="font-mono text-prism-brandText truncate">{doc.id}</span>
            <span className="text-prism-textMuted">S3 Location:</span>
            <span className="font-mono text-prism-textPrimary break-all">{doc.sourceUri}</span>
            <span className="text-prism-textMuted">S3 Bucket:</span>
            <span className="text-prism-textPrimary">{doc.source}</span>
            <span className="text-prism-textMuted">SHA-256 Checksum:</span>
            <span className="font-mono text-prism-textMuted text-[10px] truncate">{doc.checksum}</span>
            <span className="text-prism-textMuted">File Size:</span>
            <span className="font-mono text-prism-textPrimary">{doc.fileSize}</span>
            <span className="text-prism-textMuted">AI Confidence:</span>
            <span className="text-emerald-400 font-semibold">{Math.round(doc.confidence * 100)}%</span>
            <span className="text-prism-textMuted">Governance:</span>
            <span className="text-prism-textPrimary">{doc.governance}</span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-prism-border pt-4">
          <button
            onClick={handleCopyUri}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-prism-elevated hover:bg-prism-hover border border-prism-border rounded-sm text-xs font-semibold text-prism-textPrimary transition-colors"
          >
            <CopyIcon className="w-3.5 h-3.5" />
            <span>Copy S3 URI</span>
          </button>
          <button
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-prism-brand hover:bg-prism-brandHover text-white rounded-sm text-xs font-semibold transition-colors"
          >
            <DownloadIcon className="w-3.5 h-3.5" />
            <span>Download S3 Object</span>
          </button>
        </div>
      </div>
    </div>
  );
};
