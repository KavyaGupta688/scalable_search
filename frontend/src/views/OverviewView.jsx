import React from 'react';
import { initialMockData } from '../services/mockData';
import { SearchIcon, S3Icon, CpuIcon, ChevronRightIcon, ImageIcon, VideoIcon, AudioIcon, DocumentIcon } from '../components/Icons';

export const OverviewView = ({ onNavigate, onOpenDocument }) => {
  const { platformOverview, documents } = initialMockData;

  const renderModalityIcon = (type) => {
    switch (type) {
      case 'image': return <ImageIcon className="w-4 h-4" />;
      case 'video': return <VideoIcon className="w-4 h-4" />;
      case 'audio': return <AudioIcon className="w-4 h-4" />;
      default: return <DocumentIcon className="w-4 h-4" />;
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-prism-brandText uppercase">
            S3 Multimodal Platform
          </span>
          <h1 className="text-xl font-bold text-prism-textPrimary tracking-tight">Overview</h1>
          <p className="text-xs text-prism-textMuted mt-0.5">
            Continuous ingestion, neural enrichment, and multimodal discovery across connected Amazon S3 buckets.
          </p>
        </div>
        <button
          onClick={() => onNavigate('search')}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors self-start"
        >
          <SearchIcon className="w-4 h-4" />
          <span>Open Search</span>
        </button>
      </div>

      {/* 4 Clean KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-prism-textMuted font-medium">Total S3 Objects</span>
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Active
            </span>
          </div>
          <div className="text-2xl font-bold text-prism-textPrimary font-mono">
            {platformOverview.totalIndexedFiles.toLocaleString()}
          </div>
          <div className="text-[10px] text-prism-textMuted mt-auto">Across 4 production S3 buckets</div>
        </div>

        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-prism-textMuted font-medium">S3 Storage Volume</span>
            <S3Icon className="w-4 h-4 text-prism-brandText" />
          </div>
          <div className="text-2xl font-bold text-prism-textPrimary font-mono">
            {platformOverview.totalStorageFormatted}
          </div>
          <div className="text-[10px] text-prism-textMuted mt-auto">ap-northeast-2 (Seoul)</div>
        </div>

        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-prism-textMuted font-medium">AI Enrichment</span>
            <span className="text-[10px] font-semibold text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-sm">
              {platformOverview.enrichmentRate}%
            </span>
          </div>
          <div className="text-2xl font-bold text-prism-textPrimary font-mono">14.6M Enriched</div>
          <div className="text-[10px] text-prism-textMuted mt-auto">Vision, OCR, Audio, Vectors</div>
        </div>

        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-prism-textMuted font-medium">Search Latency</span>
            <CpuIcon className="w-4 h-4 text-prism-brandText" />
          </div>
          <div className="text-2xl font-bold text-prism-textPrimary font-mono">
            {platformOverview.searchLatencyAvgMs} ms
          </div>
          <div className="text-[10px] text-prism-textMuted mt-auto">1536-d Vector Index</div>
        </div>
      </div>

      {/* Simplified 3-Step Pipeline Flow */}
      <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-prism-textPrimary">Platform Processing Pipeline</h3>
            <p className="text-[11px] text-prism-textMuted">Continuous automated pipeline from Amazon S3 to searchable AI knowledge</p>
          </div>
          <button
            onClick={() => onNavigate('ingestion')}
            className="inline-flex items-center gap-1 text-[11px] text-prism-brandText hover:underline"
          >
            <span>View Ingestion</span>
            <ChevronRightIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-prism-elevated border border-prism-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-prism-textMuted">STEP 01</span>
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">S3 Stream</span>
            </div>
            <div className="text-xs font-bold text-prism-textPrimary">S3 Ingestion & Validation</div>
            <div className="text-xs text-prism-textSecondary">
              <span className="font-mono font-bold text-prism-brandText">18.4 GB/s</span> · MIME & SHA-256 Check
            </div>
            <div className="flex items-center justify-between text-[10px] text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-auto">
              <span>Connected</span>
              <span className="font-mono text-prism-textPrimary">4 S3 Buckets</span>
            </div>
          </div>

          <div className="bg-prism-elevated border border-prism-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-prism-textMuted">STEP 02</span>
              <span className="text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Active</span>
            </div>
            <div className="text-xs font-bold text-prism-textPrimary">AI Enrichment & Fusion</div>
            <div className="text-xs text-prism-textSecondary">
              <span className="font-mono font-bold text-prism-brandText">420 docs/s</span> · Vision & Whisper
            </div>
            <div className="flex items-center justify-between text-[10px] text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-auto">
              <span>Confidence</span>
              <span className="font-mono text-prism-textPrimary">96.8% Avg</span>
            </div>
          </div>

          <div className="bg-prism-elevated border border-prism-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-prism-textMuted">STEP 03</span>
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Indexed</span>
            </div>
            <div className="text-xs font-bold text-prism-textPrimary">Multimodal Search Index</div>
            <div className="text-xs text-prism-textSecondary">
              <span className="font-mono font-bold text-prism-brandText">14.8M Vectors</span> · Lexical + Vector
            </div>
            <div className="flex items-center justify-between text-[10px] text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-auto">
              <span>P95 Speed</span>
              <span className="font-mono text-prism-textPrimary">38 ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Modality Distribution & Recent S3 Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Modality Breakdown */}
        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold text-prism-textPrimary">S3 Objects by Modality</h3>
              <p className="text-[11px] text-prism-textMuted">Indexed media and documents across all S3 buckets</p>
            </div>
            <button
              onClick={() => onNavigate('search')}
              className="inline-flex items-center gap-1 text-[11px] text-prism-brandText hover:underline"
            >
              <span>Browse All</span>
              <ChevronRightIcon className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex flex-col gap-2.5 pt-1">
            {platformOverview.modalityDistribution.map((item) => (
              <div key={item.type} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-prism-textPrimary">{item.label}</span>
                  <span className="font-mono text-[11px] text-prism-textMuted">
                    {item.count.toLocaleString()} files ({item.bytes})
                  </span>
                </div>
                <div className="h-1.5 w-full bg-prism-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${item.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent S3 Discoveries */}
        <div className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-3">
          <div>
            <h3 className="text-xs font-bold text-prism-textPrimary">Recent S3 Discoveries</h3>
            <p className="text-[11px] text-prism-textMuted">Latest enriched assets ready for search</p>
          </div>

          <div className="flex flex-col gap-2 pt-1">
            {documents.slice(0, 3).map((doc) => (
              <div
                key={doc.id}
                onClick={() => onOpenDocument(doc.id)}
                className="flex items-start gap-3 p-2.5 bg-prism-elevated hover:bg-prism-hover border border-prism-borderSubtle rounded-sm cursor-pointer transition-colors"
              >
                <div className="p-2 rounded-sm bg-prism-surface text-prism-brandText shrink-0">
                  {renderModalityIcon(doc.modality)}
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-xs font-bold text-prism-textPrimary truncate">{doc.filename}</span>
                  <span className="text-[11px] text-prism-textSecondary line-clamp-1">{doc.canonicalCaption}</span>
                  <div className="flex items-center gap-2 text-[10px] text-prism-textMuted font-mono mt-1">
                    <span className="text-blue-400">{doc.modality}</span> ·
                    <span>{doc.fileSize}</span> ·
                    <span className="text-prism-textSecondary truncate">{doc.sourceUri.split('/')[2]}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
