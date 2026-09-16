import { Button } from '../components/DesignSystem';
import { Link } from 'react-router-dom';
import React, { useState } from 'react';
import { initialMockData } from '../services/mockData';
import { SearchIcon, S3Icon, CpuIcon, ChevronRightIcon, ImageIcon, VideoIcon, AudioIcon, DocumentIcon } from '../components/Icons';
import { ModalDetail } from '../components/ModalDetail';
import { useNavigate } from 'react-router-dom';

export const OverviewView = ({ showToast }) => {
  const navigate = useNavigate();
  const [activeDocId, setActiveDocId] = useState(null);
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
    <>
      <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Continuous ingestion, neural enrichment, and multimodal discovery across connected Amazon S3 buckets.
          </p>
        </div>
        <button
          onClick={() => navigate('/admin/search')}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors self-start"
        >
          <SearchIcon className="w-4 h-4" />
          <span>Open Search</span>
        </button>
      </div>

      <div className="overview-grid">
      <section className="nx-panel overview-welcome"><h2>Manage your data</h2><p>Connect sources and monitor processing from one place.</p><Button as={Link} to="/admin/data-sources">Manage data sources <ChevronRightIcon/></Button></section>
      {/* 4 Clean KPI Cards */}
      <div className="overview-metrics">
        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">Total S3 Objects</span>
            <span className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-sm">
              Active
            </span>
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">
            {platformOverview.totalIndexedFiles.toLocaleString()}
          </div>
          <div className="text-sm text-nexus-textMuted mt-auto">Across 4 production S3 buckets</div>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">S3 Storage Volume</span>
            <S3Icon className="w-4 h-4 text-nexus-brandText" />
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">
            {platformOverview.totalStorageFormatted}
          </div>
          <div className="text-sm text-nexus-textMuted mt-auto">ap-northeast-2 (Seoul)</div>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">AI Enrichment</span>
            <span className="text-sm font-semibold text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-sm">
              {platformOverview.enrichmentRate}%
            </span>
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">14.6M Enriched</div>
          <div className="text-sm text-nexus-textMuted mt-auto">Vision, OCR, Audio, Vectors</div>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">Search Latency</span>
            <CpuIcon className="w-4 h-4 text-nexus-brandText" />
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">
            {platformOverview.searchLatencyAvgMs} ms
          </div>
          <div className="text-sm text-nexus-textMuted mt-auto">1536-d Vector Index</div>
        </div>
      </div>

      {/* Simplified 3-Step Pipeline Flow */}
      <div className="nx-panel p-6 flex flex-col gap-4 overview-pipeline">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="panel-title">Platform Processing Pipeline</h3>
            <p className="text-sm text-nexus-textMuted">Continuous automated pipeline from Amazon S3 to searchable AI knowledge</p>
          </div>
          <button
            onClick={() => navigate('/admin/ingestion')}
            className="inline-flex items-center gap-1 text-sm text-nexus-brandText hover:underline"
          >
            <span>View Ingestion</span>
            <ChevronRightIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-nexus-elevated border border-nexus-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-sans">
              <span className="font-bold text-nexus-textMuted">STEP 01</span>
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">S3 Stream</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">S3 Ingestion & Validation</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">18.4 GB/s</span> · MIME & SHA-256 Check
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>Connected</span>
              <span className="font-mono text-nexus-textPrimary">4 S3 Buckets</span>
            </div>
          </div>

          <div className="bg-nexus-elevated border border-nexus-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-sans">
              <span className="font-bold text-nexus-textMuted">STEP 02</span>
              <span className="text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Active</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">AI Enrichment & Fusion</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">420 docs/s</span> · Vision & Whisper
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>Confidence</span>
              <span className="font-mono text-nexus-textPrimary">96.8% Avg</span>
            </div>
          </div>

          <div className="bg-nexus-elevated border border-nexus-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-sans">
              <span className="font-bold text-nexus-textMuted">STEP 03</span>
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Indexed</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">Multimodal Search Index</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">14.8M Vectors</span> · Lexical + Vector
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>P95 Speed</span>
              <span className="font-mono text-nexus-textPrimary">38 ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Modality Distribution & Recent S3 Items */}
      <div className="overview-details">
        {/* Modality Breakdown */}
        <div className="nx-panel p-6 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="panel-title">S3 Objects by Modality</h3>
              <p className="text-sm text-nexus-textMuted">Indexed media and documents across all S3 buckets</p>
            </div>
            <button
              onClick={() => navigate('/admin/search')}
              className="inline-flex items-center gap-1 text-sm text-nexus-brandText hover:underline"
            >
              <span>Browse All</span>
              <ChevronRightIcon className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex flex-col gap-2.5 pt-1">
            {platformOverview.modalityDistribution.map((item) => (
              <div key={item.type} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-nexus-textPrimary">{item.label}</span>
                  <span className="font-mono text-sm text-nexus-textMuted">
                    {item.count.toLocaleString()} files ({item.bytes})
                  </span>
                </div>
                <div className="h-1.5 w-full bg-nexus-elevated rounded-full overflow-hidden">
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
        <div className="nx-panel p-6 flex flex-col gap-3">
          <div>
            <h3 className="panel-title">Recent S3 Discoveries</h3>
            <p className="text-sm text-nexus-textMuted">Latest enriched assets ready for search</p>
          </div>

          <div className="flex flex-col gap-2 pt-1">
            {documents.slice(0, 3).map((doc) => (
              <div
                key={doc.id}
                role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveDocId(doc.id); } }} onClick={() => setActiveDocId(doc.id)}
                className="flex items-start gap-3 p-2.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-borderSubtle rounded-sm cursor-pointer transition-colors"
              >
                <div className="p-2 rounded-sm bg-nexus-surface text-nexus-brandText shrink-0">
                  {renderModalityIcon(doc.modality)}
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-sm font-bold text-nexus-textPrimary truncate">{doc.filename}</span>
                  <span className="text-sm text-nexus-textSecondary line-clamp-1">{doc.canonicalCaption}</span>
                  <div className="flex items-center gap-2 text-sm text-nexus-textMuted font-mono mt-1">
                    <span className="text-blue-400">{doc.modality}</span> ·
                    <span>{doc.fileSize}</span> ·
                    <span className="text-nexus-textSecondary truncate">{doc.sourceUri.split('/')[2]}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
    </div>
    {activeDocId && (
      <ModalDetail
        docId={activeDocId}
        onClose={() => setActiveDocId(null)}
        showToast={showToast}
      />
    )}
    </>
  );
};
