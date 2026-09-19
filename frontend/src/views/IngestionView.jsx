import { Presence } from '../components/Motion';
import { DialogBackdrop } from '../components/DialogBackdrop';
import React, { useState } from 'react';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { RefreshIcon, CloseIcon } from '../components/Icons';

export const IngestionView = ({ showToast }) => {
  const [jobs, setJobs] = useState(api.getIngestionJobs());
  const [selectedJob, setSelectedJob] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    setJobs(api.getIngestionJobs());
    await new Promise((r) => setTimeout(r, 400));
    setRefreshing(false);
    if (showToast) showToast('Refreshed ingestion telemetry stream status', 'info');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Ingestion Monitor</h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Automated event streaming, MIME validation, SHA-256 deduplication, and UUID v7 stamping from connected storage buckets.
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

      {/* 3 Telemetry Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Active Ingest Speed</span>
          <span className="text-2xl font-bold text-nexus-brandText font-mono">31.2 GB/s</span>
          <span className="text-sm text-nexus-textMuted">Continuous Event & Kafka feeds</span>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Validated Today</span>
          <span className="text-2xl font-bold text-nexus-textPrimary font-mono">3,561,454</span>
          <span className="text-sm text-[#4ade80]">99.1% checksum & MIME pass rate</span>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-nexus-textMuted">Deduplicated Objects</span>
          <span className="text-2xl font-bold text-amber-400 font-mono">31,566</span>
          <span className="text-sm text-nexus-textMuted">Avoided duplicate neural re-indexing</span>
        </div>
      </div>

      {/* Ingestion Streams Table */}
      <div className="nx-panel flex flex-col">
        <div className="p-4 border-b border-nexus-border flex items-center justify-between">
          <h3 className="panel-title">Active Ingestion Streams</h3>
          <span className="font-mono text-sm text-nexus-textMuted">{jobs.length} Active Streams</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-nexus-border bg-nexus-elevated text-nexus-textMuted font-mono text-sm uppercase">
                <th className="p-3">Stream & Storage Bucket</th>
                <th className="p-3">Status</th>
                <th className="p-3">Throughput</th>
                <th className="p-3">Volume</th>
                <th className="p-3">Validated Objects</th>
                <th className="p-3">Progress</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-borderSubtle">
              {jobs.map((job) => (
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
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="font-mono text-sm text-nexus-textMuted">{job.progress}%</span>
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
                <span className="text-nexus-textMuted">Job ID:</span>
                <span className="font-mono text-nexus-brandText truncate">{selectedJob.id}</span>
                <span className="text-nexus-textMuted">Status:</span>
                <StatusBadge status={selectedJob.status} size="sm" />
                <span className="text-nexus-textMuted">Live Speed:</span>
                <span className="font-mono text-nexus-textPrimary">{selectedJob.currentThroughput}</span>
                <span className="text-nexus-textMuted">Data Volume:</span>
                <span className="font-mono text-nexus-textPrimary">{selectedJob.dataVolume}</span>
                <span className="text-nexus-textMuted">Target Prefix:</span>
                <span className="font-mono text-sm text-nexus-textSecondary">{selectedJob.prefix || '/'}</span>
                <span className="text-nexus-textMuted">Worker Tasks:</span>
                <span className="text-nexus-textPrimary">{selectedJob.activeWorkers || '16 Parallel Celery Workers'}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Pipeline Progression Breakdown
              </span>
              <div className="flex flex-col gap-2 bg-nexus-elevated p-3.5 rounded-sm border border-nexus-borderSubtle text-sm">
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">1. S3 Enumeration & Checksum Validation</span>
                  <span className="text-[#4ade80] font-mono font-semibold">100%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">2. Content Extraction & OCR Analysis</span>
                  <span className="text-[#4ade80] font-mono font-semibold">{selectedJob.progress}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-nexus-textSecondary">3. Neural Embeddings Generation (1536-d)</span>
                  <span className="text-nexus-brandText font-mono font-semibold">
                    {Math.max(0, selectedJob.progress - 12)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={() => {
                  if (showToast) showToast(`Triggered checksum validation for ${selectedJob.bucket}`, 'info');
                }}
                className="px-3.5 py-1.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border rounded-sm text-sm font-semibold text-nexus-textPrimary transition-colors"
              >
                Validate Checksums
              </button>
            </div>
          </div>
        </DialogBackdrop>
      )}</Presence>
    </div>
  );
};
