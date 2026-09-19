import React from 'react';

/**
 * Pagination — Clean pagination controls with page indicators and previous/next actions.
 */
export const Pagination = ({
  page = 1,
  totalPages = 1,
  onPageChange,
  totalItems,
  pageSize = 50,
}) => {
  if (totalPages <= 1 && !totalItems) return null;

  const startItem = (page - 1) * pageSize + 1;
  const endItem = totalItems ? Math.min(page * pageSize, totalItems) : page * pageSize;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm text-nexus-textMuted pt-3 border-t border-nexus-borderSubtle">
      <div>
        {totalItems != null ? (
          <span>
            Showing <strong className="text-nexus-textPrimary font-mono">{startItem}</strong> to{' '}
            <strong className="text-nexus-textPrimary font-mono">{endItem}</strong> of{' '}
            <strong className="text-nexus-textPrimary font-mono">{totalItems}</strong> entries
          </span>
        ) : (
          <span>
            Page <strong className="text-nexus-textPrimary font-mono">{page}</strong> of{' '}
            <strong className="text-nexus-textPrimary font-mono">{Math.max(1, totalPages)}</strong>
          </span>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-2.5 py-1 rounded-sm bg-nexus-surface border border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textPrimary disabled:opacity-40 disabled:pointer-events-none text-nexus-textSecondary transition-colors"
        >
          Previous
        </button>

        <span className="px-2 py-1 font-mono text-sm text-nexus-brandText bg-nexus-brandSubtle border border-nexus-border rounded-sm">
          {page} / {Math.max(1, totalPages)}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-2.5 py-1 rounded-sm bg-nexus-surface border border-nexus-border hover:border-nexus-borderStrong hover:text-nexus-textPrimary disabled:opacity-40 disabled:pointer-events-none text-nexus-textSecondary transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
};
