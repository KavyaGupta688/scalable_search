import React, { useState, useEffect } from 'react';
import {useResource,ResourceState} from '../components/ResourceState';
import {tags,pipelineGroups} from '../services/presentation';
import {request} from '../services/http';
import {StatusBadge} from '../components/StatusBadge';
import {ProtectedPreview} from '../components/ProtectedPreview';
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
  const [page,setPage] = useState(0);
  const tasks = useResource(`/ai/tasks?limit=25&offset=${page*25}`, {poll:5000});
  const [selectedDocId,setSelectedDocId] = useState('');
  const [isReEnriching,setIsReEnriching] = useState(false);
  const [actionError,setActionError] = useState('');
  const selectedTask = tasks.data?.tasks.find(t => t.document_id === selectedDocId);
  useEffect(() => {if (tasks.data && !tasks.data.tasks.some(t => t.document_id === selectedDocId)) setSelectedDocId(tasks.data.tasks[0]?.document_id || '');},[tasks.data,selectedDocId]);
  const status = useResource(selectedTask ? `/ai/status/${selectedDocId}` : null, {poll:5000});
  const metadata = useResource(selectedTask ? `/ai/metadata/${selectedDocId}` : null, {poll:10000});
  const documents = (tasks.data?.tasks || []).map(t => ({id:t.document_id, filename:t.document_id, modality:t.mime_type || 'Unknown'}));
  const selectedDoc = {
    id:selectedDocId, filename:selectedDocId || 'No task selected', sourceUri:'Source location unavailable',
    modality:selectedTask?.mime_type?.split('/')[0],
    canonicalCaption:metadata.data?.short_description || metadata.data?.long_description || 'Generated description unavailable',
    tags:tags(metadata.data?.generated_tags),
  };
  const stages = pipelineGroups(status.data);
  const aiEnrichment = {activePipelines: ['Vision and tagging','OCR and documents','Audio and transcription','Shared CLIP embeddings'].map((name,i) => ({id:i,name,latencyAvg:'Unavailable',status:'Not reported',throughput:'—',queueSize:'—'}))};
  const canRetry = ['partial','needs_review','failed_terminal','queue_failed'].includes(selectedTask?.status);
  const handleRetry = async () => {
    if (!canRetry) return;
    setIsReEnriching(true);setActionError('');
    try {await request(`/ai/retry/${selectedDocId}`,{method:'POST'});tasks.reload();status.reload();metadata.reload();showToast?.('Retry queued. Follow the persisted task status.','info');}
    catch (err) {setActionError(err.message);}
    finally {setIsReEnriching(false);}
  };
  const handleCopyJson = async () => {
    try {await navigator.clipboard.writeText(JSON.stringify(metadata.data,null,2));showToast?.('Copied versioned metadata','success');}
    catch {setActionError('Unable to copy metadata.');}
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
            AI processing and administrator review
          </span>
          <span>
            Task status comes from the AI service. Model telemetry is unavailable; missing models appear in task errors. Review-required content is excluded from discovery.
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">AI Enrichment</h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Automated neural tagging, OCR layout analysis, audio transcription, and 512-d vector embeddings.
          </p>
        </div>
        <button
          type="button"
          disabled title="Model benchmarking is not exposed by the integrated API."
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
            <p className="text-sm text-nexus-textMuted">Persisted AI stages grouped by preparation, extraction, generation, and persistence. Indexing runs separately.</p>
          </div>
          <StatusBadge status={status.data?.status || 'Unavailable'}/>
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
                <span>Recorded</span>
                <span className="text-nexus-textPrimary">{stg.count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <ResourceState error={tasks.error || actionError} loading={tasks.loading}/>
      <p role={selectedTask?.error ? 'alert' : 'status'} className="text-sm text-nexus-textMuted">{tasks.data?.total ?? '—'} tasks · {selectedTask?.status || 'No task selected'} {selectedTask?.error || ''}</p>
      <nav aria-label="Task pages" className="flex justify-between text-sm"><button className="nx-button" disabled={!page} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page+1}</span><button className="nx-button" disabled={!tasks.data || (page+1)*25 >= tasks.data.total} onClick={() => setPage(p => p + 1)}>Next</button></nav>
      {/* Active Multimodal Models Grid */}
      <div className="flex flex-col gap-3">
        <div>
          <h3 className="panel-title">Active Multimodal Models</h3>
          <p className="text-sm text-nexus-textMuted">Model groups · runtime health, throughput, latency, and queue telemetry are not exposed</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {aiEnrichment.activePipelines.map((pipe) => (
            <div key={pipe.id} className="nx-panel p-6 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-sm font-bold text-nexus-textPrimary block">{pipe.name}</span>
                  <span className="text-sm text-nexus-textMuted font-mono">Latency: {pipe.latencyAvg}</span>
                </div>
                <span className="text-sm text-nexus-textMuted bg-nexus-elevated border border-nexus-borderSubtle px-1.5 py-0.5 rounded-xs font-semibold">
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

              }}
              className="bg-nexus-elevated border border-nexus-border rounded-sm text-sm text-nexus-textPrimary px-2.5 py-1 outline-none"
            >
              <option value="" disabled>Select a task</option>{documents.map((d) => (
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
            {selectedDocId ? <ProtectedPreview documentId={selectedDocId} modality={selectedDoc.modality} name={selectedDoc.filename}/> : <div className="h-52 bg-nexus-elevated border border-nexus-borderSubtle flex items-center justify-center text-sm text-nexus-textMuted">No task selected</div>}

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
                {selectedDoc.tags.length === 0 && <span className="text-sm text-nexus-textMuted">Tags unavailable</span>}{selectedDoc.tags.map((t) => (
                  <span key={t} className="text-sm font-mono px-2 py-0.5 bg-nexus-elevated border border-nexus-border text-nexus-brandText rounded-xs">
                    #{t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: 512-d Vector Embedding & JSON Spec */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-nexus-textPrimary">512-d Vector Embedding</span>
                <span className="text-sm font-sans text-nexus-textMuted bg-nexus-elevated border border-nexus-borderSubtle px-1.5 py-0.2 rounded-xs">Index state unavailable</span>
              </div>
              <button
                type="button"
                onClick={handleCopyJson} disabled={!metadata.data}
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
                <span className="text-nexus-brandText font-semibold">512 dimensions configured</span>
              </div>
              <div className="text-sm text-blue-300 break-all leading-tight font-mono">
                Embedding values are not exposed by this endpoint.
              </div>
              <div className="h-6 flex items-center gap-0.5 mt-1">
                <span className="text-nexus-textMuted">Vector visualization unavailable</span>
              </div>
            </div>

            <ResourceState error={metadata.error || status.error} loading={metadata.loading}/>
            <details className="text-sm"><summary className="cursor-pointer font-semibold">Versioned AI metadata</summary><pre className="mt-2 whitespace-pre-wrap break-all text-xs bg-nexus-input p-3 max-h-80 overflow-auto">{metadata.data ? JSON.stringify(metadata.data,null,2) : 'Generated metadata unavailable'}</pre></details>
            {/* Re-Enrichment Trigger Action */}
            <div className="mt-auto flex items-center justify-between bg-nexus-elevated p-3 rounded-sm border border-nexus-borderSubtle">
              <div className="flex flex-col">
                <span className="text-sm font-bold text-nexus-textPrimary">Sequential Re-Enrichment</span>
                <span className="text-sm text-nexus-textMuted">Retry eligible tasks from their persisted checkpoints</span>
              </div>
              <button
                type="button"
                onClick={handleRetry}
                disabled={isReEnriching || !canRetry} title={!canRetry ? 'Only failed, partial, review-required, or queue-failed tasks can be retried.' : undefined}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover disabled:opacity-50 text-white rounded-sm text-sm font-semibold transition-colors border border-nexus-brand"
              >
                <RefreshIcon className={`w-3.5 h-3.5 ${isReEnriching ? 'animate-spin' : ''}`} />
                <span>{isReEnriching ? 'Queueing retry...' : 'Retry AI Processing'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
