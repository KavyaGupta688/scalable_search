import React, { useState } from 'react';
import { initialMockData } from '../services/mockData';
import { api } from '../services/api';
import { CpuIcon, RefreshIcon, CopyIcon, ImageIcon, VideoIcon, AudioIcon, DocumentIcon, TabularIcon } from '../components/Icons';

export const EnrichmentView = ({ onShowToast }) => {
  const { aiEnrichment, documents } = initialMockData;
  const [selectedDocId, setSelectedDocId] = useState(documents[0].id);
  const [isReEnriching, setIsReEnriching] = useState(false);
  const [activeStepIndex, setActiveStepIndex] = useState(2); // Step 3 is currently active in pipeline by default (0-indexed: 0, 1, 2, 3)

  const selectedDoc = api.getDocument(selectedDocId) || documents[0];

  // Strictly sequential stages definition
  const stages = [
    {
      id: 'step-1',
      num: 'STEP 01',
      name: 'S3 Validated Stream',
      status: activeStepIndex >= 0 ? (activeStepIndex > 0 ? 'completed' : 'active') : 'pending',
      count: '1,840 objects',
      desc: 'MIME validation & SHA-256'
    },
    {
      id: 'step-2',
      num: 'STEP 02',
      name: 'Content Extraction & OCR',
      status: activeStepIndex >= 1 ? (activeStepIndex > 1 ? 'completed' : 'active') : 'pending',
      count: '1,240 objects',
      desc: 'Layout parsing & keyframes'
    },
    {
      id: 'step-3',
      num: 'STEP 03',
      name: 'Vision-LLM & Acoustic Tagging',
      status: activeStepIndex >= 2 ? (activeStepIndex > 2 ? 'completed' : 'active') : 'pending',
      count: '810 objects',
      desc: 'Neural tags & descriptions'
    },
    {
      id: 'step-4',
      num: 'STEP 04',
      name: '1536-d Embedding & Indexing',
      status: activeStepIndex >= 3 ? (activeStepIndex > 3 ? 'completed' : 'active') : 'pending',
      count: '420 objects',
      desc: 'Joint vector indexing'
    }
  ];

  const handleSimulateReEnrichment = async () => {
    setIsReEnriching(true);
    onShowToast(`Starting sequential AI re-enrichment for '${selectedDoc.filename}'`, 'info');

    // Sequential step-by-step animation
    setActiveStepIndex(0);
    await new Promise((r) => setTimeout(r, 400));
    setActiveStepIndex(1);
    await new Promise((r) => setTimeout(r, 400));
    setActiveStepIndex(2);
    await new Promise((r) => setTimeout(r, 400));
    setActiveStepIndex(3);
    await new Promise((r) => setTimeout(r, 400));
    setActiveStepIndex(4); // All completed

    setIsReEnriching(false);
    onShowToast(`Completed step-by-step enrichment: 1536-d vector generated (100% Synced)`, 'success');
  };

  const handleCopyJson = () => {
    const payload = JSON.stringify(
      {
        document_id: selectedDoc.id,
        s3_uri: selectedDoc.sourceUri,
        modality: selectedDoc.modality,
        caption: selectedDoc.canonicalCaption,
        tags: selectedDoc.tags,
        confidence: selectedDoc.confidence,
        vector_dim: 1536
      },
      null,
      2
    );
    if (navigator.clipboard) navigator.clipboard.writeText(payload);
    onShowToast('Copied enriched metadata JSON to clipboard', 'success');
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-prism-brandText uppercase">
            Neural Processing Fabric
          </span>
          <h1 className="text-xl font-bold text-prism-textPrimary tracking-tight">AI Enrichment</h1>
          <p className="text-xs text-prism-textMuted mt-0.5">
            Automated neural tagging, OCR layout analysis, audio transcription, and 1536-d vector embeddings for S3 objects.
          </p>
        </div>
        <button
          onClick={async () => {
            onShowToast('Running model benchmark across active neural cluster...', 'info');
            await new Promise((r) => setTimeout(r, 800));
            onShowToast('Benchmark Completed: Vision-LLM 9.4B (142ms P95), Whisper (480ms P95), ViT-H/14 (24ms P95)', 'success');
          }}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors self-start"
        >
          <CpuIcon className="w-4 h-4" />
          <span>Run Model Benchmark</span>
        </button>
      </div>

      {/* Sequential 4-Stage Pipeline Flow */}
      <div className="bg-prism-surface border border-prism-border p-5 rounded-sm flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-prism-textPrimary">Sequential AI Pipeline Flow</h3>
            <p className="text-[11px] text-prism-textMuted">Strict linear progression: S3 Ingestion → Extraction → Tagging → 1536-d Vector Index</p>
          </div>
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Pipeline Synchronized
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {stages.map((stg) => (
            <div
              key={stg.id}
              className={`p-3.5 rounded-sm border flex flex-col gap-2 transition-all ${
                stg.status === 'completed'
                  ? 'bg-prism-elevated border-emerald-500/30'
                  : stg.status === 'active'
                  ? 'bg-prism-brandSubtle border-[#23426e]'
                  : 'bg-prism-surface border-prism-borderSubtle opacity-60'
              }`}
            >
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="font-bold text-prism-textMuted">{stg.num}</span>
                <span
                  className={`px-1.5 py-0.5 rounded-xs font-semibold uppercase ${
                    stg.status === 'completed'
                      ? 'text-emerald-400 bg-emerald-500/10'
                      : stg.status === 'active'
                      ? 'text-blue-400 bg-blue-500/10 animate-pulse'
                      : 'text-prism-textMuted bg-prism-elevated'
                  }`}
                >
                  {stg.status}
                </span>
              </div>
              <span className="text-xs font-bold text-prism-textPrimary">{stg.name}</span>
              <span className="text-[10px] text-prism-textSecondary">{stg.desc}</span>
              <div className="flex items-center justify-between text-[10px] font-mono text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-auto">
                <span>Queued</span>
                <span className="text-prism-textPrimary">{stg.count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active Multimodal Models Grid */}
      <div className="flex flex-col gap-3">
        <div>
          <h3 className="text-xs font-bold text-prism-textPrimary">Active Multimodal Models</h3>
          <p className="text-[11px] text-prism-textMuted">Dedicated neural cluster engines processing S3 object streams</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {aiEnrichment.activePipelines.map((pipe) => (
            <div key={pipe.id} className="bg-prism-surface border border-prism-border p-4 rounded-sm flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-bold text-prism-textPrimary block">{pipe.name}</span>
                  <span className="text-[10px] text-prism-textMuted font-mono">Latency: {pipe.latencyAvg}</span>
                </div>
                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs font-semibold">
                  {pipe.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 bg-prism-elevated p-2 rounded-xs border border-prism-borderSubtle">
                <div className="flex flex-col">
                  <span className="text-[9px] uppercase text-prism-textMuted font-semibold">Throughput</span>
                  <span className="text-xs font-bold text-prism-brandText font-mono">{pipe.throughput}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] uppercase text-prism-textMuted font-semibold">Queue</span>
                  <span className="text-xs font-bold text-prism-textPrimary font-mono">{pipe.queueSize.toLocaleString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Interactive S3 Object AI Enrichment Inspector */}
      <div className="bg-prism-surface border border-prism-border p-5 rounded-sm flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-prism-border pb-3">
          <div>
            <h3 className="text-xs font-bold text-prism-textPrimary">Interactive S3 Object AI Inspector</h3>
            <p className="text-[11px] text-prism-textMuted">Select an S3 object to inspect its extracted neural metadata and vector representation</p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="inspect-doc-select" className="text-xs text-prism-textMuted">Inspect S3 Object:</label>
            <select
              id="inspect-doc-select"
              value={selectedDocId}
              onChange={(e) => {
                setSelectedDocId(e.target.value);
                setActiveStepIndex(4); // Already completed for indexed documents
              }}
              className="bg-prism-input border border-prism-border text-xs text-prism-textPrimary px-2.5 py-1 rounded-sm outline-none font-mono"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.modality})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-5 items-start">
          {/* Left: Raw S3 Media View & Technical Specs */}
          <div className="bg-prism-elevated border border-prism-borderSubtle p-4 rounded-sm flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-prism-textMuted uppercase font-mono">S3 Input Object</span>
              <span className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-xs bg-blue-500/10 text-blue-400">
                {selectedDoc.modality}
              </span>
            </div>

            <div className="text-xs font-bold text-prism-textPrimary truncate" title={selectedDoc.filename}>
              {selectedDoc.filename}
            </div>

            <div className="font-mono text-[11px] text-prism-brandText bg-prism-surface p-2 rounded-xs border border-prism-borderSubtle truncate">
              {selectedDoc.sourceUri}
            </div>

            {/* Media Sample Box */}
            <div className="h-44 bg-black rounded-sm relative flex items-center justify-center overflow-hidden">
              <div className="text-center text-prism-textMuted flex flex-col items-center gap-1">
                {renderModalityIcon(selectedDoc.modality)}
                <span className="text-[9px] font-mono uppercase tracking-widest">{selectedDoc.modality} RAW STREAM</span>
              </div>
              {selectedDoc.modality === 'image' && selectedDoc.detectedObjects.length > 0 && (
                <div className="absolute top-[20%] left-[55%] w-[32%] h-[38%] border-2 border-red-500 bg-red-500/15 rounded-xs">
                  <span className="absolute -top-4 left-0 bg-red-500 text-white text-[9px] font-bold px-1 py-0.5">
                    Defect (96.8%)
                  </span>
                </div>
              )}
            </div>

            {/* Specs */}
            <div className="grid grid-cols-[110px_1fr] gap-2 text-[11px] bg-prism-surface p-3 rounded-xs border border-prism-borderSubtle">
              <span className="text-prism-textMuted">Document ID:</span>
              <span className="font-mono text-prism-brandText truncate">{selectedDoc.id}</span>
              <span className="text-prism-textMuted">File Size:</span>
              <span className="font-mono text-prism-textPrimary">{selectedDoc.fileSize}</span>
              <span className="text-prism-textMuted">SHA-256:</span>
              <span className="font-mono text-prism-textMuted text-[10px] truncate">{selectedDoc.checksum}</span>
            </div>

            <button
              onClick={handleSimulateReEnrichment}
              disabled={isReEnriching}
              className="mt-1 px-3 py-2 bg-prism-brand hover:bg-prism-brandHover disabled:bg-blue-900 text-white text-xs font-semibold rounded-sm flex items-center justify-center gap-1.5 transition-colors"
            >
              <RefreshIcon className={`w-3.5 h-3.5 ${isReEnriching ? 'animate-spin' : ''}`} />
              <span>{isReEnriching ? 'Running Sequential Pipeline...' : 'Simulate Re-Enrichment'}</span>
            </button>
          </div>

          {/* Right: Extracted Multimodal Intelligence */}
          <div className="bg-prism-elevated border border-prism-borderSubtle p-4 rounded-sm flex flex-col gap-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-prism-textMuted uppercase font-mono">
                Multimodal Extracted Intelligence
              </span>
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-xs font-mono">
                {Math.round(selectedDoc.confidence * 100)}% Model Confidence
              </span>
            </div>

            {/* Caption */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-prism-textMuted uppercase">AI Synthesized Caption:</span>
              <p className="text-xs text-prism-textPrimary bg-prism-surface p-2.5 rounded-xs border border-prism-borderSubtle leading-relaxed">
                {selectedDoc.canonicalCaption}
              </p>
            </div>

            {/* Tags */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-prism-textMuted uppercase">Semantic AI Tags:</span>
              <div className="flex flex-wrap gap-1.5">
                {selectedDoc.tags.map((t) => (
                  <span
                    key={t}
                    className="text-[10px] font-medium px-2 py-0.5 rounded-xs bg-prism-surface border border-prism-border text-prism-brandText"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>

            {/* OCR / Transcript */}
            {selectedDoc.ocrText && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-prism-textMuted uppercase">OCR Extracted Text:</span>
                <div className="font-mono text-[11px] text-prism-textSecondary bg-prism-surface p-2 rounded-xs border border-prism-borderSubtle">
                  {selectedDoc.ocrText}
                </div>
              </div>
            )}

            {selectedDoc.transcript && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-prism-textMuted uppercase">Whisper Audio Transcript:</span>
                <div className="font-mono text-[11px] text-prism-textSecondary bg-prism-surface p-2 rounded-xs border border-prism-borderSubtle">
                  {selectedDoc.transcript}
                </div>
              </div>
            )}

            {/* 1536-d Vector Embedding */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-[10px]">
                <span className="font-semibold text-prism-textMuted uppercase">1536-d Joint Multimodal Vector:</span>
                <span className="font-mono text-prism-brandText font-semibold">ViT-H/14 · L2 Normalized</span>
              </div>
              <div className="flex items-center gap-0.5 h-5 bg-prism-surface p-1 rounded-xs border border-prism-borderSubtle overflow-hidden">
                {Array.from({ length: 48 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex-1 h-full bg-blue-500 rounded-2xs"
                    style={{ opacity: 0.2 + Math.abs(Math.sin(i * 0.5)) * 0.8 }}
                  />
                ))}
              </div>
              <div className="font-mono text-[10px] text-prism-textMuted">
                [-0.0482, 0.1291, 0.0814, -0.0029, 0.2319, -0.1102, 0.0451, ...]
              </div>
            </div>

            {/* Enriched JSON Payload */}
            <div className="flex flex-col gap-1 pt-1">
              <div className="flex items-center justify-between text-[10px]">
                <span className="font-semibold text-prism-textMuted uppercase">Enriched JSON Schema:</span>
                <button
                  onClick={handleCopyJson}
                  className="inline-flex items-center gap-1 text-[10px] text-prism-brandText hover:underline"
                >
                  <CopyIcon className="w-3 h-3" />
                  <span>Copy JSON</span>
                </button>
              </div>
              <pre className="font-mono text-[10px] text-blue-300 bg-prism-surface p-2.5 rounded-xs border border-prism-borderSubtle max-h-24 overflow-y-auto leading-tight">
                {JSON.stringify(
                  {
                    document_id: selectedDoc.id,
                    s3_uri: selectedDoc.sourceUri,
                    modality: selectedDoc.modality,
                    caption: selectedDoc.canonicalCaption,
                    tags: selectedDoc.tags,
                    confidence: selectedDoc.confidence,
                    vector_dim: 1536
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
