import { Presence } from '../components/Motion';
import { Button } from '../components/DesignSystem';
import { Link } from 'react-router-dom';
import React, { useState } from 'react';
import {useResource, ResourceState} from '../components/ResourceState';
import {number,bytes} from '../services/presentation';
import { SearchIcon, S3Icon, CpuIcon, ChevronRightIcon, ImageIcon, VideoIcon, AudioIcon, DocumentIcon } from '../components/Icons';
import { ModalDetail } from '../components/ModalDetail';
import { useNavigate } from 'react-router-dom';

export const OverviewView = ({ showToast }) => {
  const navigate = useNavigate();
  const [activeDocId, setActiveDocId] = useState(null);
  const summary = useResource('/api/admin/overview', {poll:15000});
  const data = summary.data;
  const enriched = data ? (data.enrichment.completed || 0) + (data.enrichment.partial || 0) : null;
  const platformOverview = {
    totalIndexedFiles: number(data?.documents), totalStorageFormatted:bytes(data?.bytes),
    searchLatencyAvgMs:data?.search_latency?.mean_ms?.toFixed(0) ?? '—',
    modalityDistribution: [['image','Images'],['video','Videos'],['document','Documents'],['audio','Audio and transcripts'],['tabular','Tabular data']].map(([type,label]) => {
      const row = data?.modalities?.find(r => r.modality === type);
      return {type,label,count:data ? row?.count || 0 : '—',bytes:data ? bytes(row?.bytes || 0) : 'loading',percentage:data?.documents ? (row?.count || 0)/data.documents*100 : 0};
    }),
  };
  const documents = (data?.recent || []).map(d => ({id:d.file_id,filename:d.file_name,modality:d.file_type,
    canonicalCaption:d.description,fileSize:bytes(d.file_size),source:d.dataset_name}));

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
            Manual source scans, AI enrichment, and multimodal discovery across connected S3 and NAS sources.
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
      <ResourceState error={summary.error} loading={summary.loading}/>{/* Original KPI layout */}
      <div className="overview-metrics">
        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">Ingested Documents</span>
            <span className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-sm">
              {summary.error ? 'Unavailable' : summary.loading ? 'Loading' : 'Recorded'}
            </span>
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">
            {platformOverview.totalIndexedFiles.toLocaleString()}
          </div>
          <div className="text-sm text-nexus-textMuted mt-auto">Across {number(data?.sources)} configured sources</div>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">Source Storage Volume</span>
            <S3Icon className="w-4 h-4 text-nexus-brandText" />
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">
            {platformOverview.totalStorageFormatted}
          </div>
          <div className="text-sm text-nexus-textMuted mt-auto">Unique ingested bytes · originals stay at source</div>
        </div>

        <div className="nx-panel p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nexus-textMuted font-medium">AI Enrichment</span>
            <span className="text-sm font-semibold text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-sm">
              {enriched == null ? '—' : 'Recorded'}
            </span>
          </div>
          <div className="text-2xl font-bold text-nexus-textPrimary font-mono">{number(enriched)} Enriched</div>
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
          <div className="text-sm text-nexus-textMuted mt-auto">Recorded search mean · last 24 hours · {number(data?.search_latency?.samples)} samples</div>
        </div>
      </div>

      {/* Simplified 3-Step Pipeline Flow */}
      <div className="nx-panel p-6 flex flex-col gap-4 overview-pipeline">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="panel-title">Platform Processing Pipeline</h3>
            <p className="text-sm text-nexus-textMuted">Manual scans feed automated enrichment and search publication</p>
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
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Manual scans</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">Source Ingestion & Validation</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">{number(data?.documents)} documents</span> · MIME & SHA-256 Check
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>Connected</span>
              <span className="font-mono text-nexus-textPrimary">{number(data?.sources)} sources</span>
            </div>
          </div>

          <div className="bg-nexus-elevated border border-nexus-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-sans">
              <span className="font-bold text-nexus-textMuted">STEP 02</span>
              <span className="text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-xs font-semibold">{data ? `${data.enrichment.in_progress || 0} processing` : 'Loading'}</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">AI Enrichment & Fusion</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">{number(enriched)} enriched</span> · Vision & Whisper
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>Confidence</span>
              <span className="font-mono text-nexus-textPrimary">{data?.confidence == null ? 'No samples' : `${(data.confidence*100).toFixed(1)}% mean`}</span>
            </div>
          </div>

          <div className="bg-nexus-elevated border border-nexus-borderSubtle p-3.5 rounded-sm flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-sans">
              <span className="font-bold text-nexus-textMuted">STEP 03</span>
              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">Publication</span>
            </div>
            <div className="text-sm font-bold text-nexus-textPrimary">Multimodal Search Index</div>
            <div className="text-sm text-nexus-textSecondary">
              <span className="font-mono font-bold text-nexus-brandText">{number(data?.published)} published</span> · Lexical + Vector
            </div>
            <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
              <span>P95 Speed</span>
              <span className="font-mono text-nexus-textPrimary">{data?.search_latency?.p95_ms == null ? 'No samples' : `${data.search_latency.p95_ms.toFixed(0)} ms`}</span>
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
              <h3 className="panel-title">Objects by Modality</h3>
              <p className="text-sm text-nexus-textMuted">Unique ingested documents across all sources</p>
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

        {/* Recent Discoveries */}
        <div className="nx-panel p-6 flex flex-col gap-3">
          <div>
            <h3 className="panel-title">Recent Discoveries</h3>
            <p className="text-sm text-nexus-textMuted">Most recently ingested files currently available in Search</p>
          </div>

          <div className="flex flex-col gap-2 pt-1">
            {!summary.loading && !summary.error && documents.length === 0 && <p className="text-sm text-nexus-textMuted">No published files yet.</p>}{documents.slice(0, 3).map((doc) => (
              <div
                key={doc.id}
                role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveDocId(doc.id); } }} onClick={() => setActiveDocId(doc.id)}
                className="interactive-card flex items-start gap-3 p-2.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-borderSubtle rounded-sm cursor-pointer transition-colors"
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
                    <span className="text-nexus-textSecondary truncate">{doc.source}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
    </div>
    <Presence>{activeDocId && (
      <ModalDetail
        docId={activeDocId}
        onClose={() => setActiveDocId(null)}
        showToast={showToast}
      />
    )}</Presence>
    </>
  );
};
