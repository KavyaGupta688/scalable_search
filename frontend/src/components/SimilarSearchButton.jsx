import React, { useState } from 'react';
import { Presence, FeedbackMotion } from './Motion';
import { searchSimilar } from '../services/searchApi';
import { ScanIcon, SpinnerIcon, CloseIcon } from './Icons';
import { ModalityBadge } from './ModalityBadge';

/**
 * SimilarSearchButton — Button and dropdown / results panel for finding similar files to a target file.
 */
export const SimilarSearchButton = ({ fileId, onSelectResult }) => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState('');

  const handleFetchSimilar = async () => {
    if (isOpen) {
      setIsOpen(false);
      return;
    }

    setIsOpen(true);
    setLoading(true);
    setError('');

    try {
      const data = await searchSimilar(fileId, 6);
      setResults(data.results || []);
    } catch (err) {
      setError(err.message || 'Failed to search similar objects');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={handleFetchSimilar}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-nexus-elevated border border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textPrimary text-sm text-nexus-textSecondary transition-colors"
      >
        {loading ? (
          <SpinnerIcon className="w-3.5 h-3.5 animate-spin text-nexus-brandText" />
        ) : (
          <ScanIcon className="w-3.5 h-3.5 text-nexus-brandText" />
        )}
        <span>{isOpen ? 'Hide Similar Files' : 'Find Similar Files'}</span>
      </button>

      <Presence>{isOpen && (
        <FeedbackMotion className="bg-nexus-input border border-nexus-borderStrong rounded-sm p-3 flex flex-col gap-2 mt-1">
          <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-1.5">
            <span className="text-sm font-mono uppercase tracking-wider text-nexus-textMuted font-semibold">
              Similar Vector Matches
            </span>
            <button
              onClick={() => setIsOpen(false)} aria-label="Close similar files"
              className="text-nexus-textMuted hover:text-nexus-textPrimary p-0.5"
            >
              <CloseIcon className="w-3.5 h-3.5" />
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-sm text-nexus-textMuted py-4 justify-center">
              <SpinnerIcon className="w-4 h-4 animate-spin text-nexus-brandText" />
              <span>Querying vector index for nearest neighbors...</span>
            </div>
          )}

          {error && (
            <div className="text-sm text-nexus-danger bg-red-900/20 border border-red-800/40 p-2 rounded-xs">
              {error}
            </div>
          )}

          {!loading && !error && results && results.length === 0 && (
            <div className="text-sm text-nexus-textMuted py-3 text-center">
              No similar files found in current index.
            </div>
          )}

          {!loading && results && results.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {results.map((item) => (
                <div
                  key={item.file_id || item.id}
                  onClick={() => onSelectResult && onSelectResult(item)}
                  className="flex items-center justify-between p-2 rounded-xs bg-nexus-surface hover:bg-nexus-hover border border-nexus-borderSubtle cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <ModalityBadge type={item.content_type || item.modality} />
                    <span className="text-sm font-semibold text-nexus-textPrimary truncate">
                      {item.name || item.filename}
                    </span>
                  </div>
                  {item.score != null && (
                    <span className="text-sm font-mono text-nexus-brandText shrink-0 ml-2">
                      {Math.round(item.score * 100)}% match
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </FeedbackMotion>
      )}</Presence>
    </div>
  );
};
