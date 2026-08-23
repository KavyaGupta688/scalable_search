import React, { useState } from 'react';
import { api } from '../services/api';
import { RefreshIcon, CloseIcon } from '../components/Icons';

export const IngestionView = ({ onShowToast }) => {
  const [jobs] = useState(api.getIngestionJobs());
  const [selectedJob, setSelectedJob] = useState(null);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-prism-brandText uppercase">
            Object Storage Connectors
          </span>
          <h1 className="text-xl font-bold text-prism-textPrimary tracking-tight">S3 Ingestion Monitor</h1>
          <p className="text-xs text-prism-textMuted mt-0.5">
            Automated event streaming, MIME validation, SHA-256 deduplication, and UUID v7 stamping from connected Amazon S3 buckets.
          </p>
        </div>
        <button
          onClick={() => onShowToast('Refreshed S3 ingestion telemetry', 'info')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-prism-surface hover:bg-prism-hover border border-prism-border text-prism-textPrimary text-xs font-semibold rounded-sm transition-colors self-start"
        >
          <RefreshIcon className="w-3.5 h-3.5" />
          <span>Refresh Streams</span>
        </button>
      </div>

      {/* 3 Telemetry Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold text-prism-textMuted">Active S3 Ingest Speed</span>
          <span className="text-2xl font-bold text-prism-brandText font-mono">31.2 GB/s</span>
          <span className="text-[10px] text-prism-textMuted">Continuous S3 EventBridge & SQS feeds</span>
        </div>

        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold text-prism-textMuted">Validated Today</span>
          <span className="text-2xl font-bold text-prism-textPrimary font-mono">3,561,454</span>
          <span className="text-[10px] text-emerald-400">99.1% checksum & MIME pass rate</span>
        </div>

        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold text-prism-textMuted">Deduplicated Objects</span>
          <span className="text-2xl font-bold text-amber-400 font-mono">31,566</span>
          <span className="text-[10px] text-prism-textMuted">Avoided duplicate AI re-indexing</span>
        </div>
      </div>

      {/* Ingestion Streams Table */}
      <div className="bg-prism-surface border border-prism-border rounded-sm flex flex-col">
        <div className="p-4 border-b border-prism-border flex items-center justify-between">
          <h3 className="text-xs font-bold text-prism-textPrimary">Active S3 Ingestion Streams</h3>
          <span className="font-mono text-[11px] text-prism-textMuted">{jobs.length} Active Streams</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-prism-border bg-prism-elevated text-prism-textMuted font-mono text-[10px] uppercase">
                <th className="p-3">Stream & S3 Bucket</th>
                <th className="p-3">Status</th>
                <th className="p-3">Throughput</th>
                <th className="p-3">Volume</th>
                <th className="p-3">Validated Objects</th>
                <th className="p-3">Progress</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-prism-borderSubtle">
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className="hover:bg-prism-hover cursor-pointer transition-colors"
                >
                  <td className="p-3">
                    <strong className="text-prism-textPrimary block">{job.name}</strong>
                    <span className="font-mono text-[10px] text-prism-textMuted">{job.bucket}</span>
                  </td>
                  <td className="p-3">
                    <span
                      className={`text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-xs ${
                        job.status === 'Completed'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-blue-500/10 text-blue-400'
                      }`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="p-3 font-mono font-bold text-prism-brandText">{job.currentThroughput}</td>
                  <td className="p-3 font-mono text-prism-textSecondary">{job.dataVolume}</td>
                  <td className="p-3 font-mono text-prism-textSecondary">
                    {job.validatedCount.toLocaleString()} / {job.discoveredCount.toLocaleString()}
                  </td>
                  <td className="p-3 min-w-[140px]">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 bg-prism-elevated rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            job.status === 'Completed' ? 'bg-emerald-500' : 'bg-blue-500'
                          }`}
                          style={{ width: job.status === 'Completed' ? '100%' : '88%' }}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-prism-textMuted">
                        {job.status === 'Completed' ? '100%' : '88%'}
                      </span>
                    </div>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedJob(job);
                      }}
                      className="px-2.5 py-1 bg-prism-elevated hover:bg-prism-hover border border-prism-borderSubtle text-prism-textSecondary hover:text-prism-textPrimary rounded-xs text-[11px] transition-colors"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ingestion Stream Inspection Modal */}
      {selectedJob && (
        <div
          className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4 backdrop-enter"
          onClick={() => setSelectedJob(null)}
        >
          <div
            className="w-full max-w-lg bg-prism-surface border border-prism-borderStrong rounded-sm p-5 flex flex-col gap-4 modal-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-prism-border pb-3">
              <div>
                <h3 className="text-sm font-bold text-prism-textPrimary">{selectedJob.name}</h3>
                <span className="text-xs text-prism-textMuted font-mono">S3 Bucket: {selectedJob.bucket}</span>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="p-1 text-prism-textMuted hover:text-prism-textPrimary"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 bg-prism-elevated p-3.5 rounded-sm border border-prism-borderSubtle text-xs">
              <div>
                <span className="text-prism-textMuted block text-[10px] uppercase">Status:</span>
                <span className="text-emerald-400 font-semibold">{selectedJob.status}</span>
              </div>
              <div>
                <span className="text-prism-textMuted block text-[10px] uppercase">Current Speed:</span>
                <span className="font-mono font-bold text-prism-brandText">{selectedJob.currentThroughput}</span>
              </div>
              <div>
                <span className="text-prism-textMuted block text-[10px] uppercase">Data Volume:</span>
                <span className="font-mono text-prism-textPrimary">{selectedJob.dataVolume}</span>
              </div>
              <div>
                <span className="text-prism-textMuted block text-[10px] uppercase">Validated Objects:</span>
                <span className="font-mono text-prism-textPrimary">
                  {selectedJob.validatedCount.toLocaleString()} / {selectedJob.discoveredCount.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
                Ingestion Stages
              </span>
              <div className="flex flex-col gap-2">
                {selectedJob.stages.map((stg) => (
                  <div
                    key={stg.name}
                    className="flex items-center justify-between text-xs bg-prism-elevated p-2.5 rounded-xs border border-prism-borderSubtle"
                  >
                    <span className="font-semibold text-prism-textPrimary">{stg.name}</span>
                    <div className="flex items-center gap-2 w-44">
                      <div className="h-1.5 flex-1 bg-prism-surface rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            stg.status === 'completed' ? 'bg-emerald-500' : 'bg-blue-500'
                          }`}
                          style={{ width: `${stg.progress}%` }}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-prism-textMuted w-8 text-right">
                        {stg.progress}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-prism-border">
              <button
                onClick={() => setSelectedJob(null)}
                className="px-3 py-1.5 text-xs text-prism-textMuted hover:text-prism-textPrimary"
              >
                Close
              </button>
              <button
                onClick={() => {
                  onShowToast(`Triggered S3 checksum validation for ${selectedJob.bucket}`, 'info');
                  setSelectedJob(null);
                }}
                className="px-3.5 py-1.5 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors"
              >
                Trigger Verification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
