import { FileImage, FileVideo, FileAudio, FileText, Table2 } from 'lucide-react';
import React from 'react';
import { ModalityBadge } from './ModalityBadge';
import { CheckSquareIcon } from './Icons';

/**
 * SearchResultCard — Grid card representation of a search result document.
 */
export const SearchResultCard = ({
  result,
  isSelected = false,
  onToggleSelect,
  onOpen,
}) => {
  const fileId = result.file_id || result.id || '';
  const filename = result.name || result.filename || 'Untitled';
  const modality = result.content_type || result.modality || 'document';
  const description = result.description || result.aiDescription || '';
  const PreviewIcon = ({image:FileImage,video:FileVideo,audio:FileAudio,document:FileText,tabular:Table2})[modality] || FileText;
  const tags = result.tags || [];
  const score = result.score != null ? Math.round(result.score * 100) : null;

  return (
    <div
      className={`result-card border overflow-hidden flex flex-col transition-colors cursor-pointer select-none group ${
        isSelected
          ? 'border-nexus-brand bg-nexus-brandSubtle/20'
          : 'border-nexus-border hover:border-nexus-borderStrong'
      }`}
      role="button" tabIndex={0} aria-label={`Preview ${filename}`}
      onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen?.(); } }}
      onClick={onOpen}
    >
      <div className="result-preview"><PreviewIcon/><span className="modality-label">{modality}</span></div>
      {/* Card Header Bar */}
      <div className="p-3 border-b border-nexus-borderSubtle flex items-center justify-between gap-2 bg-nexus-input">
        <ModalityBadge type={modality} />

        <div className="flex items-center gap-2">
          {score != null && (
            <span className="text-sm font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle border border-nexus-border px-1.5 py-0.5 rounded-xs">
              {score}% match
            </span>
          )}

          {/* Selection Checkbox */}
          {onToggleSelect && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect();
              }}
              title={isSelected ? 'Deselect file' : 'Select for batch download'}
              aria-label={isSelected ? 'Deselect file' : 'Select for batch download'}
              aria-pressed={isSelected}
              className={`p-1 rounded-xs border transition-colors ${
                isSelected
                  ? 'bg-nexus-brand text-white border-nexus-brand'
                  : 'bg-nexus-input text-nexus-textMuted border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textPrimary'
              }`}
            >
              <CheckSquareIcon className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Card Body */}
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <h3
          className="text-sm font-bold text-nexus-textPrimary truncate group-hover:text-nexus-brandText transition-colors"
          title={filename}
        >
          {filename}
        </h3>

        {description && (
          <p className="text-sm text-nexus-textSecondary line-clamp-2 leading-relaxed">
            {description}
          </p>
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-2">
            {tags.slice(0, 3).map((tag, idx) => (
              <span
                key={idx}
                className="text-sm font-mono px-1.5 py-0.5 bg-nexus-elevated border border-nexus-borderSubtle text-nexus-textMuted rounded-xs"
              >
                #{tag}
              </span>
            ))}
            {tags.length > 3 && (
              <span className="text-sm font-mono px-1 text-nexus-textMuted">
                +{tags.length - 3}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Card Footer */}
      <div className="px-3 py-2 border-t border-nexus-borderSubtle bg-nexus-input flex items-center justify-between text-sm text-nexus-textMuted font-mono">
        <span className="truncate max-w-[150px]" title={fileId}>
          {fileId.slice(0, 18)}...
        </span>
        {result.fileSize && <span>{result.fileSize}</span>}
      </div>
    </div>
  );
};
