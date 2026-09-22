import { Presence } from '../components/Motion';
import { DialogBackdrop } from '../components/DialogBackdrop';
import React, { useState } from 'react';
import {useResource, ResourceState} from '../components/ResourceState';
import {connectorView,runView,number} from '../services/presentation';
import { StatusBadge } from '../components/StatusBadge';
import { CopyableId } from '../components/CopyableId';
import { RefreshIcon, CloseIcon } from '../components/Icons';

export const IngestionView = ({ showToast }) => {
  const runs = useResource('/admin/ingestion/runs?limit=50', {poll:10000});
  const sources = useResource('/admin/connectors?limit=100');
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const summary = useResource(`/api/admin/ingestion-summary?timezone=${encodeURIComponent(timezone)}`, {poll:5000});
  const jobs = (runs.data || []).map(r => runView(r, (sources.data || []).map(connectorView)));
  const [selected, setSelectedJob] = useState(null);
  const detail = useResource(selected ? `/admin/ingestion/runs/${selected.id}` : null, {poll:5000});
  const selectedJob = selected ? runView(detail.data || jobs.find(j => j.id === selected.id) || selected, (sources.data || []).map(connectorView)) : null;
  const pipeline = useResource(selected ? `/api/admin/ingestion-runs/${selected.id}/pipeline` : null, {poll:5000});
  const items = useResource(selected ? `/admin/ingestion/runs/${selected.id}/items?page_size=100` : null, {poll:5000});
  const stageCounts = counts => Object.entries(counts || {}).map(([status,count]) => `${count} ${status.replaceAll('_',' ')}`).join(' · ') || 'No canonical documents linked yet';
  const refreshing = runs.loading;
  const handleRefresh = () => {runs.reload(); sources.reload(); summary.reload(); detail.reload(); pipeline.reload(); items.reload();};

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Ingestion Monitor</h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Manual scan history with validation outcomes and source provenance.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-nexus-surface hover:bg-nexus-hover border border-nexus-border text-nexus-textPrimary text-sm font-semibold rounded-sm transition-colors self-start"
        >
          <RefreshIcon className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span>Refresh Streams</span>
        </button>
      </div>

      <ResourceState error={runs.error || sources.error} loading={runs.loading}/>{/* Original telemetry cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Recent Ingest Speed</span>
          <span className="text-2xl font-bold text-nexus-brandText font-mono">{summary.data ? `${summary.data.recent_mib_per_second.toFixed(2)} MiB/s` : '—'}</span>
          <span className="text-sm text-nexus-textMuted">Completed-file bytes over the last 60 seconds · {number(summary.data?.active_runs)} active runs</span>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Validated Today</span>
          <span className="text-2xl font-bold text-nexus-textPrimary font-mono">{number(summary.data?.validated_today)}</span>
          <span className="text-sm text-nexus-textMuted">New files + checksum duplicates since midnight ({timezone}); unchanged skips excluded</span>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Duplicates Detected</span>
          <span className="text-2xl font-bold text-amber-400 font-mono">{number(summary.data?.duplicates)}</span>
          <span className="text-sm text-nexus-textMuted">Checksum duplicate outcomes across all recorded runs</span>
        </div>
      </div>
      <ResourceState error={summary.error} loading={summary.loading}/>

      {/* Ingestion Streams Table */}
      <div className="nx-panel flex flex-col">
        <div className="p-4 border-b border-nexus-border flex items-center justify-between">
          <h3 className="panel-title">Recent Ingestion Runs</h3>
          <span className="font-mono text-sm text-nexus-textMuted">{jobs.length} runs · latest 50</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-nexus-border bg-nexus-elevated text-nexus-textMuted font-mono text-sm uppercase">
                <th className="p-3">Stream & Storage Bucket</th>
                <th className="p-3">Status</th>
                <th className="p-3">Run average</th>
                <th className="p-3">Volume</th>
                <th className="p-3">New / Discovered</th>
                <th className="p-3">Progress</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-borderSubtle">
              {!runs.loading && jobs.length === 0 && <tr><td colSpan={7} className="p-8 text-nexus-textMuted">{runs.error ? 'Run history unavailable.' : 'No ingestion runs yet.'}</td></tr>}{jobs.map((job) => (
                <tr
                  key={job.id}
                  role="button" tabIndex={0} onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setSelectedJob(job); } }} onClick={() => setSelectedJob(job)}
                  className="hover:bg-nexus-hover cursor-pointer transition-colors"
                >
                  <td className="p-3">
                    <strong className="text-nexus-textPrimary block">{job.name}</strong>
                    <span className="font-mono text-sm text-nexus-textMuted">{job.bucket}</span>
                  </td>
                  <td className="p-3">
                    <StatusBadge status={job.status} size="sm" />
                  </td>
                  <td className="p-3 font-mono font-bold text-nexus-brandText">{job.currentThroughput}</td>
                  <td className="p-3 font-mono text-nexus-textSecondary">{job.dataVolume}</td>
                  <td className="p-3 font-mono text-nexus-textSecondary">
                    {job.validatedCount.toLocaleString()} / {job.discoveredCount.toLocaleString()}
                  </td>
                  <td className="p-3 min-w-[140px]">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-nexus-elevated h-1.5 rounded-full overflow-hidden border border-nexus-borderSubtle">
                        <div
                          className="bg-nexus-brand h-full rounded-full transition-all duration-300"
                          style={{ width: `${job.progress == null ? '—' : `${job.progress ?? 0}%`}` }}
                        />
                      </div>
                      <span className="font-mono text-sm text-nexus-textMuted">{job.progress == null ? '—' : `${job.progress ?? 0}%`}</span>
                    </div>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedJob(job);
                      }}
                      className="text-sm font-medium text-nexus-brandText hover:underline"
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stream details */}
      <Presence>{selectedJob && (
        <DialogBackdrop onClose={() => setSelectedJob(null)}
          onClick={() => setSelectedJob(null)}
        >
          <div
            className="detail-dialog max-w-xl p-6 flex flex-col gap-5 dialog-surface" role="dialog" aria-modal="true" aria-label="Ingestion details" tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-nexus-border pb-3">
              <div>
                <h3 className="panel-title">{selectedJob.name}</h3>
                <span className="text-sm text-nexus-textMuted font-mono">{selectedJob.bucket}</span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                aria-label="Close details" className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Stream Pipeline Configuration
              </span>
              <div className="grid grid-cols-[130px_1fr] gap-2.5 text-sm bg-nexus-elevated p-3.5 rounded-sm border border-nexus-borderSubtle">
                <span className="text-nexus-textMuted">Run ID:</span>
                <CopyableId label="run ID" value={selectedJob.id} />
                <span className="text-nexus-textMuted">Connector ID:</span>
                <CopyableId label="connector ID" value={selectedJob.connector_id} />
                <span className="text-nexus-textMuted">Started:</span>
                <span className="text-nexus-textPrimary">{selectedJob.triggered_at ? new Date(selectedJob.triggered_at).toLocaleString() : 'Unavailable'}</span>
                <span className="text-nexus-textMuted">Status:</span>
                <StatusBadge status={selectedJob.status} size="sm" />
                <span className="text-nexus-textMuted">Run average:</span>
                <span className="font-mono text-nexus-textPrimary">{selectedJob.currentThroughput}</span>
                <span className="text-nexus-textMuted">Data Volume:</span>
                <span className="font-mono text-nexus-textPrimary">{selectedJob.dataVolume}</span>
                <span className="text-nexus-textMuted">{selectedJob.source_type === 'S3' ? 'Target Prefix:' : 'Source Folder:'}</span>
                <span className="font-mono text-sm text-nexus-textSecondary break-all min-w-0">{selectedJob.prefix || '/'}</span>
                <span className="text-nexus-textMuted">Remaining Items:</span>
                <span className="text-nexus-textPrimary">{selectedJob.remainingItems} discovered files awaiting an outcome</span>
              </div>
              <ResourceState error={detail.error} loading={detail.loading}/>
              {selectedJob.error_detail && <p role="alert" className="text-nexus-danger">{selectedJob.error_detail}</p>}
              <p className="text-sm text-nexus-textMuted">{number(selectedJob.succeeded_count)} new · {number(selectedJob.duplicate_count)} duplicates · {number(selectedJob.skipped_count)} unchanged skips · {number(selectedJob.rejected_count)} rejected · {number(selectedJob.failed_count)} failed</p>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Pipeline Progression Breakdown
              </span>
              <div className="flex flex-col gap-2 bg-nexus-elevated p-3.5 rounded-sm border border-nexus-borderSubtle text-sm">
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">1. Source Enumeration & Checksum Validation</span>
                  <span className="text-[#4ade80] font-mono font-semibold">{number(selectedJob.terminal_count)} processed</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">2. Content Extraction & OCR Analysis</span>
                  <span className="text-nexus-textPrimary font-mono text-right">{pipeline.data ? stageCounts(pipeline.data.extraction) : pipeline.loading ? 'Loading…' : 'Could not load'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">3. Search Index Projection (512-d)</span>
                  <span className="text-nexus-brandText font-mono font-semibold">
                    {pipeline.data ? `${pipeline.data.indexed} / ${pipeline.data.canonical_documents} indexed` : pipeline.loading ? 'Loading…' : 'Could not load'}
                  </span>
                </div>
              </div>
              <ResourceState error={pipeline.error} loading={pipeline.loading}/>
              {pipeline.data && <div className="text-sm text-nexus-textMuted space-y-2"><p>AI: {stageCounts(pipeline.data.ai_statuses)}</p><p>{pipeline.data.published} published search records. AI enrichment and indexing continue after ingestion completes. Completed extraction does not necessarily mean text was found.</p><p>{pipeline.data.scope}</p>{pipeline.data.errors.map(e => <p key={e.document_id} role="alert" className="text-nexus-danger break-all">{e.document_id}: {e.message}</p>)}</div>}
            </div>

            <section className="text-sm"><h4 className="font-semibold">Run items · first 100</h4><ResourceState error={items.error} loading={items.loading} empty={items.data?.length === 0}/>{items.data?.map(item => <div key={item.source_ref} className="border-b border-nexus-borderSubtle py-2 break-all"><strong>{item.source_ref}</strong><p>{item.outcome || 'Pending'} · {item.last_error || ''}</p></div>)}</section>
          </div>
        </DialogBackdrop>
      )}</Presence>
    </div>
  );
};
