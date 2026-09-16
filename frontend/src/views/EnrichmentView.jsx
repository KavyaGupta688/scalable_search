import React, { useState } from 'react';
import { initialMockData } from '../services/mockData';
import { api } from '../services/api';
import {
  CpuIcon,
  RefreshIcon,
  CopyIcon,
  ImageIcon,
  VideoIcon,
  AudioIcon,
  DocumentIcon,
  TabularIcon,
  AlertCircleIcon,
} from '../components/Icons';

export const EnrichmentView = ({ showToast }) => {
  const { aiEnrichment, documents } = initialMockData;
  const [selectedDocId, setSelectedDocId] = useState(documents[0]?.id || 'doc-001');
  const [isReEnriching, setIsReEnriching] = useState(false);
  const [activeStepIndex, setActiveStepIndex] = useState(2); // Step 3 active (0=step1 active, 1=step2 active, 2=step3 active, 3=step4 active, 4=all completed)

  const selectedDoc = api.getDocument(selectedDocId) || documents[0];

  // Strictly sequential stages definition (1 -> 2 -> 3 -> 4)
  const stages = [
    {
      id: 'step-1',
      num: 'STEP 01',
      name: 'Storage Validated Stream',
      status: activeStepIndex >= 0 ? (activeStepIndex > 0 ? 'completed' : 'active') : 'pending',
      count: '1,840 objects',
      desc: 'MIME validation & SHA-256',
    },
    {
      id: 'step-2',
      num: 'STEP 02',
      name: 'Content Extraction & OCR',
      status: activeStepIndex >= 1 ? (activeStepIndex > 1 ? 'completed' : 'active') : 'pending',
      count: '1,240 objects',
      desc: 'Layout parsing & keyframes',
    },
    {
      id: 'step-3',
      num: 'STEP 03',
      name: 'Vision-LLM & Acoustic Tagging',
      status: activeStepIndex >= 2 ? (activeStepIndex > 2 ? 'completed' : 'active') : 'pending',
      count: '810 objects',
      desc: 'Neural tags & descriptions',
    },
    {
      id: 'step-4',
      num: 'STEP 04',
      name: '1536-d Embedding & Indexing',
      status: activeStepIndex >= 3 ? (activeStepIndex > 3 ? 'completed' : 'active') : 'pending',
      count: '420 objects',
      desc: 'Joint vector indexing',
    },
  ];

  const handleSimulateReEnrichment = async () => {
    setIsReEnriching(true);
    if (showToast) showToast(`Starting sequential AI re-enrichment for '${selectedDoc.filename}'`, 'info');

    // Sequential step-by-step animation (strictly 0 -> 1 -> 2 -> 3 -> 4)
    setActiveStepIndex(0);
    await new Promise((r) => setTimeout(r, 450));
    setActiveStepIndex(1);
    await new Promise((r) => setTimeout(r, 450));
    setActiveStepIndex(2);
    await new Promise((r) => setTimeout(r, 450));
    setActiveStepIndex(3);
    await new Promise((r) => setTimeout(r, 450));
    setActiveStepIndex(4); // All completed

    setIsReEnriching(false);
    if (showToast) showToast(`Completed sequential enrichment: 1536-d vector generated`, 'success');
  };

  const handleCopyJson = () => {
    const payload = JSON.stringify(
      {
        document_id: selectedDoc.id,
        source_uri: selectedDoc.sourceUri,
        modality: selectedDoc.modality,
        caption: selectedDoc.canonicalCaption,
        tags: selectedDoc.tags,
        confidence: selectedDoc.confidence,
        vector_dim: 1536,
      },
      null,
      2
    );
    if (navigator.clipboard) navigator.clipboard.writeText(payload);
    if (showToast) showToast('Copied enriched metadata JSON to clipboard', 'success');
  };

  const renderModalityIcon = (mod) => {
    switch (mod) {
      case 'image': return <ImageIcon className="w-4 h-4" />;
      case 'video': return <VideoIcon className="w-4 h-4" />;
      case 'audio': return <AudioIcon className="w-4 h-4" />;
      case 'tabular': return <TabularIcon className="w-4 h-4" />;
      default: return <DocumentIcon className="w-4 h-4" />;
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Notice Banner: Stub notification per Milestone 12 */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-sm bg-[#1a1c29] border border-[#2d324d] text-nexus-textSecondary text-sm">
        <AlertCircleIcon className="w-4 h-4 text-nexus-brandText shrink-0" />
        <div>
          <span className="font-mono text-sm font-bold text-nexus-brandText uppercase mr-2">
            [Stub — AI module integration pending]
          </span>
          <span>
            This screen displays mockup telemetry. Live integration will wire to the AI Tagging module specification once published.
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">AI Enrichment</h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Automated neural tagging, OCR layout analysis, audio transcription, and 1536-d vector embeddings.
          </p>
        </div>
        <button
          type="button"
          onClick={async () => {
            if (showToast) showToast('Running model benchmark across active neural cluster...', 'info');
            await new Promise((r) => setTimeout(r, 800));
            if (showToast) showToast('Benchmark Completed: Vision-LLM (142ms P95), Whisper (480ms P95), ViT-H/14 (24ms P95)', 'success');
          }}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors self-start border border-nexus-brand"
        >
          <CpuIcon className="w-4 h-4" />
          <span>Run Model Benchmark</span>
        </button>
      </div>

      {/* Sequential 4-Stage Pipeline Flow */}
      <div className="nx-panel p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="panel-title">Sequential AI Pipeline Flow</h3>
            <p className="text-sm text-nexus-textMuted">Strict linear progression: Ingestion → Extraction → Tagging → 1536-d Vector Index</p>
          </div>
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#4ade80] bg-[#122a1e] border border-[#1f5739] px-2 py-0.5 rounded-xs">
            Pipeline Synchronized
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {stages.map((stg) => (
            <div
              key={stg.id}
              className={`p-3.5 rounded-sm border flex flex-col gap-2 transition-all ${
                stg.status === 'completed'
                  ? 'bg-nexus-elevated border-[#1f5739]'
                  : stg.status === 'active'
                  ? 'bg-nexus-brandSubtle border-nexus-border'
                  : 'bg-nexus-surface border-nexus-borderSubtle opacity-60'
              }`}
            >
              <div className="flex items-center justify-between text-sm font-mono">
                <span className="font-bold text-nexus-textMuted">{stg.num}</span>
                <span
                  className={`px-1.5 py-0.5 rounded-xs font-sans font-semibold uppercase ${
                    stg.status === 'completed'
                      ? 'text-[#4ade80] bg-[#122a1e] border border-[#1f5739]'
                      : stg.status === 'active'
                      ? 'text-[#60a5fa] bg-nexus-brandSubtle border border-nexus-border animate-pulse'
                      : 'text-nexus-textMuted bg-nexus-elevated'
                  }`}
                >
                  {stg.status}
                </span>
              </div>
              <span className="text-sm font-bold text-nexus-textPrimary">{stg.name}</span>
              <span className="text-sm text-nexus-textSecondary">{stg.desc}</span>
              <div className="flex items-center justify-between text-sm font-mono text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
                <span>Queued</span>
                <span className="text-nexus-textPrimary">{stg.count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active Multimodal Models Grid */}
      <div className="flex flex-col gap-3">
        <div>
          <h3 className="panel-title">Active Multimodal Models</h3>
          <p className="text-sm text-nexus-textMuted">Dedicated neural cluster engines processing object streams</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {aiEnrichment.activePipelines.map((pipe) => (
            <div key={pipe.id} className="nx-panel p-6 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-sm font-bold text-nexus-textPrimary block">{pipe.name}</span>
                  <span className="text-sm text-nexus-textMuted font-mono">Latency: {pipe.latencyAvg}</span>
                </div>
                <span className="text-sm text-[#4ade80] bg-[#122a1e] border border-[#1f5739] px-1.5 py-0.5 rounded-xs font-semibold">
                  {pipe.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 bg-nexus-elevated p-2 rounded-xs border border-nexus-borderSubtle">
                <div className="flex flex-col">
                  <span className="text-sm uppercase text-nexus-textMuted font-semibold">Throughput</span>
                  <span className="text-sm font-bold text-nexus-brandText font-mono">{pipe.throughput}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-sm uppercase text-nexus-textMuted font-semibold">Queue</span>
                  <span className="text-sm font-bold text-nexus-textPrimary font-mono">{pipe.queueSize.toLocaleString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Interactive S3 Object AI Enrichment Inspector */}
      <div className="nx-panel p-6 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-nexus-border pb-3">
          <div>
            <h3 className="panel-title">Interactive Object AI Inspector</h3>
            <p className="text-sm text-nexus-textMuted">Select an object to inspect its extracted neural metadata and vector representation</p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="inspect-doc-select" className="text-sm text-nexus-textMuted">Inspect Object:</label>
            <select
              id="inspect-doc-select"
              value={selectedDocId}
              onChange={(e) => {
                setSelectedDocId(e.target.value);
                setActiveStepIndex(2); // Reset to standard pipeline state
              }}
              className="bg-nexus-elevated border border-nexus-border rounded-sm text-sm text-nexus-textPrimary px-2.5 py-1 outline-none"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.modality})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Inspector Detail Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Left Column: Media & Vision AI Detection Box */}
          <div className="flex flex-col gap-3">
            <div className="h-52 bg-black rounded-sm relative flex items-center justify-center overflow-hidden border border-nexus-borderSubtle">
              <div className="text-center text-nexus-textMuted flex flex-col items-center gap-1.5">
                {renderModalityIcon(selectedDoc.modality)}
                <span className="text-sm font-mono uppercase tracking-wider">{selectedDoc.filename}</span>
                <span className="text-sm text-nexus-textMuted">{selectedDoc.sourceUri}</span>
              </div>

              {selectedDoc.detectedObjects && selectedDoc.detectedObjects.length > 0 && (
                <div className="absolute top-[22%] left-[48%] w-[38%] h-[40%] border-2 border-red-500 bg-red-500/20 rounded-xs">
                  <span className="absolute -top-4 left-0 bg-red-500 text-white text-sm font-bold px-1 py-0.5">
                    {selectedDoc.detectedObjects[0].label} ({Math.round(selectedDoc.detectedObjects[0].confidence * 100)}%)
                  </span>
                </div>
              )}
            </div>

            {/* Neural Canonical Caption */}
            <div className="flex flex-col gap-1 bg-nexus-elevated p-3 rounded-xs border border-nexus-borderSubtle">
              <span className="text-sm font-mono uppercase font-bold text-nexus-brandText">Canonical AI Caption</span>
              <p className="text-sm text-nexus-textPrimary leading-relaxed italic">
                &ldquo;{selectedDoc.canonicalCaption || selectedDoc.description}&rdquo;
              </p>
            </div>

            {/* AI Tags */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-mono uppercase font-bold text-nexus-textMuted">Extracted Semantic Tags</span>
              <div className="flex flex-wrap gap-1.5">
                {selectedDoc.tags.map((t) => (
                  <span key={t} className="text-sm font-mono px-2 py-0.5 bg-nexus-elevated border border-nexus-border text-nexus-brandText rounded-xs">
                    #{t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: 1536-d Vector Embedding & JSON Spec */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-nexus-textPrimary">1536-d Vector Embedding</span>
                <span className="text-sm font-sans text-[#4ade80] bg-[#122a1e] border border-[#1f5739] px-1.5 py-0.2 rounded-xs">Qdrant Indexed</span>
              </div>
              <button
                type="button"
                onClick={handleCopyJson}
                className="flex items-center gap-1 text-sm text-nexus-textMuted hover:text-nexus-brandText transition-colors"
              >
                <CopyIcon className="w-3 h-3" />
                <span>Copy JSON</span>
              </button>
            </div>

            {/* Embedding Vector Visualizer Matrix */}
            <div className="bg-nexus-input p-3 rounded-sm border border-nexus-border font-mono text-sm text-nexus-textMuted flex flex-col gap-2">
              <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-1.5">
                <span>Dense Float32 Embedding Array</span>
                <span className="text-nexus-brandText font-semibold">1536 Float32 Numbers</span>
              </div>
              <div className="text-sm text-blue-300 break-all leading-tight font-mono">
                [ 0.0418, -0.0892, 0.1245, 0.0091, -0.2104, 0.0812, 0.3189, -0.0541, 0.1872, -0.0128, 0.0984, -0.1432, 0.0571, -0.0389, ... +1,522 dims ]
              </div>
              <div className="h-6 flex items-center gap-0.5 mt-1">
                {Array.from({ length: 48 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-2xs"
                    style={{
                      height: `${Math.abs(Math.sin(i * 0.5)) * 18 + 4}px`,
                      backgroundColor: i % 3 === 0 ? '#38bdf8' : i % 2 === 0 ? '#1428a0' : '#4ade80',
                      opacity: 0.8,
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Re-Enrichment Trigger Action */}
            <div className="mt-auto flex items-center justify-between bg-nexus-elevated p-3 rounded-sm border border-nexus-borderSubtle">
              <div className="flex flex-col">
                <span className="text-sm font-bold text-nexus-textPrimary">Sequential Re-Enrichment</span>
                <span className="text-sm text-nexus-textMuted">Run 4 stages sequentially for this object</span>
              </div>
              <button
                type="button"
                onClick={handleSimulateReEnrichment}
                disabled={isReEnriching}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover disabled:opacity-50 text-white rounded-sm text-sm font-semibold transition-colors border border-nexus-brand"
              >
                <RefreshIcon className={`w-3.5 h-3.5 ${isReEnriching ? 'animate-spin' : ''}`} />
                <span>{isReEnriching ? 'Processing 4 Stages...' : 'Re-Run 4-Stage AI'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
