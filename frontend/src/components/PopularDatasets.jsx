import React, { useEffect, useState } from 'react';
import { getPopularDatasets, postSearchEvent } from '../services/searchApi';
import { DatasetsIcon, ChevronRightIcon } from './Icons';

/**
 * PopularDatasets — Vertical list of top trending and viewed datasets across the platform.
 */
export const PopularDatasets = ({ onBrowse }) => {
  const [datasets, setDatasets] = useState([]);
  const [error,setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    getPopularDatasets()
      .then((data) => {
        if (isMounted) {
          setDatasets(data.datasets || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleBrowse = (ds) => {
    // Feeds the popularity ranking. Analytics must never block browsing.
    postSearchEvent('DATASET_OPEN', { dataset_id: ds.id }).catch((err) =>
      console.warn('Dataset view was not recorded:', err.message)
    );
    if (onBrowse) onBrowse(ds.id, ds.name);
  };

  if (loading) {
    return (
      <div className="nx-panel p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider font-mono text-nexus-textMuted">
          <DatasetsIcon className="w-4 h-4 text-nexus-brandText" />
          <span>Popular Datasets</span>
        </div>
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-nexus-elevated rounded-xs animate-pulse" />
          ))}
        </div>
      </div>
    );
  }



  return (
    <div className="nx-panel p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider font-mono text-nexus-textPrimary">
        <DatasetsIcon className="w-4 h-4 text-nexus-brandText" />
        <span>Popular Datasets</span>
      </div>

      <div className="divide-y divide-nexus-borderSubtle flex flex-col">
        <p role={error ? 'alert' : undefined} className="text-sm text-nexus-textMuted">{error || (!datasets.length ? 'No published datasets.' : '')}</p>{datasets.map((ds) => (
          <div
            key={ds.id}
            className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0 gap-4"
          >
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold text-nexus-textPrimary truncate">
                {ds.name}
              </span>
              <div className="flex items-center gap-3 text-sm font-mono text-nexus-textMuted mt-0.5">
                <span>
                  {typeof ds.file_count === 'number'
                    ? `${ds.file_count.toLocaleString()} files`
                    : ds.file_count || '0 files'}
                </span>
                {ds.view_count_7d > 0 && (
                  <span>· {ds.view_count_7d.toLocaleString()} views this week</span>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={() => handleBrowse(ds)}
              className="flex items-center gap-1 text-sm font-medium px-2.5 py-1 rounded-sm bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border hover:border-nexus-brand text-nexus-textSecondary hover:text-nexus-brandText transition-colors shrink-0"
            >
              <span>Browse</span>
              <ChevronRightIcon className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
