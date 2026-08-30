import React, { useEffect, useState } from 'react';
import { getTrending, postSearchEvent } from '../services/searchApi';
import { TrendingIcon } from './Icons';

/**
 * TrendingSearches — Clickable row of trending search terms.
 */
export const TrendingSearches = ({ onSelectTerm }) => {
  const [terms, setTerms] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    getTrending()
      .then((data) => {
        if (isMounted) {
          setTerms(data.terms || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleClick = (queryTerm) => {
    postSearchEvent('SEARCH', { query_terms: queryTerm });
    if (onSelectTerm) onSelectTerm(queryTerm);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 flex-wrap py-2">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-nexus-textMuted flex items-center gap-1">
          <TrendingIcon className="w-3.5 h-3.5 text-nexus-brandText" />
          Trending:
        </span>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-6 w-20 bg-nexus-surface border border-nexus-border rounded-sm animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!terms || terms.length === 0) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap py-1.5">
      <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-nexus-textMuted flex items-center gap-1 shrink-0">
        <TrendingIcon className="w-3.5 h-3.5 text-nexus-brandText" />
        Trending:
      </span>
      {terms.slice(0, 8).map((item, idx) => {
        const queryText = typeof item === 'string' ? item : item.query || item.term;
        return (
          <button
            key={idx}
            type="button"
            onClick={() => handleClick(queryText)}
            className="text-[11px] px-2.5 py-1 rounded-sm bg-nexus-surface hover:bg-nexus-hover border border-nexus-border hover:border-nexus-brand text-nexus-textSecondary hover:text-nexus-brandText transition-colors flex items-center gap-1.5"
          >
            <span>{queryText}</span>
            {item.count && (
              <span className="text-[9px] font-mono text-nexus-textMuted">
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
