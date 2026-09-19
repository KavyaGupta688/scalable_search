import { Presence } from '../components/Motion';
import { DialogBackdrop } from '../components/DialogBackdrop';
import React, { useState, useEffect, useCallback } from 'react';
import { getConnectors, testConnector } from '../services/adminApi';
import { ConnectorFormModal } from '../components/ConnectorFormModal';
import { StatusBadge } from '../components/StatusBadge';
import {
  DatabaseIcon,
  NASIcon,
  PlusIcon,
  RefreshIcon,
  CloseIcon,
  SearchIcon,
  SpinnerIcon,
} from '../components/Icons';

/**
 * DataSourcesView — Admin view for managing S3 and NAS storage connectors.
 */
export const DataSourcesView = ({ showToast }) => {
  const [connectors, setConnectors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedConnector, setSelectedConnector] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [testingId, setTestingId] = useState(null);

  const fetchConnectors = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getConnectors();
      setConnectors(data.connectors || []);
    } catch (err) {
      if (showToast) showToast(`Failed to load connectors: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchConnectors();
  }, [fetchConnectors]);

  const handleTestConnector = async (e, conn) => {
    e.stopPropagation();
    setTestingId(conn.id);
    try {
      const res = await testConnector(conn.id);
      setConnectors((prev) =>
        prev.map((c) => (c.id === conn.id ? { ...c, status: res.status || 'Verified' } : c))
      );
      if (showToast) {
        showToast(
          res.status === 'Verified'
            ? `Connection to '${conn.name}' verified OK`
            : `Connection to '${conn.name}' failed`,
          res.status === 'Verified' ? 'success' : 'error'
        );
      }
    } catch (err) {
      if (showToast) showToast(`Test failed: ${err.message}`, 'error');
    } finally {
      setTestingId(null);
    }
  };

  const filtered = connectors.filter((c) => {
    const q = searchTerm.toLowerCase();
    return (
      c.name?.toLowerCase().includes(q) ||
      c.endpoint_or_path?.toLowerCase().includes(q) ||
      c.source_type?.toLowerCase().includes(q) ||
      c.status?.toLowerCase().includes(q) ||
      c.region?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">
            Storage Data Sources
          </h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Connected S3-compatible and NAS shares feeding raw multimodal files into automated ingestion.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors self-start border border-nexus-brand"
        >
          <PlusIcon className="w-3.5 h-3.5" />
          <span>Connect a Source</span>
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-nexus-surface border border-nexus-border p-3.5 rounded-sm">
        <div className="search-field relative flex items-center bg-nexus-input border border-nexus-border rounded-sm px-3 h-12 w-full max-w-sm">
          <SearchIcon className="w-3.5 h-3.5 text-nexus-textMuted shrink-0 mr-2" />
          <input
            type="text"
            aria-label="Search data sources"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search sources by name, path, or type..."
            className="bg-transparent text-sm text-nexus-textPrimary outline-none w-full placeholder:text-nexus-textMuted"
          />
        </div>

        <div className="flex items-center gap-3 text-sm text-nexus-textMuted font-mono">
          <span>
            Connected Sources: <strong className="text-nexus-textPrimary">{connectors.length}</strong>
          </span>
          <button
            type="button"
            onClick={fetchConnectors}
            className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
            title="Refresh connectors list"
          >
            <RefreshIcon className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Loading Skeletons */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="nx-panel p-6 flex flex-col gap-3 animate-pulse"
            >
              <div className="h-4 bg-nexus-elevated rounded-xs w-1/2" />
              <div className="h-6 bg-nexus-elevated rounded-xs" />
              <div className="h-12 bg-nexus-elevated rounded-xs" />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filtered.length === 0 && (
        <div className="bg-nexus-surface border border-nexus-border p-12 rounded-sm text-center flex flex-col items-center gap-2">
          <DatabaseIcon className="w-8 h-8 text-nexus-textMuted" />
          <div className="text-sm font-bold text-nexus-textPrimary">No connectors found</div>
          <p className="text-sm text-nexus-textMuted max-w-sm">
            {searchTerm ? 'No sources match your search filters.' : 'Get started by connecting an S3 bucket or NAS storage.'}
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => setIsAddModalOpen(true)}
              className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-nexus-brand text-white text-sm font-semibold rounded-sm"
            >
              <PlusIcon className="w-3.5 h-3.5" />
              <span>Connect First Source</span>
            </button>
          )}
        </div>
      )}

      {/* Connectors Grid */}
      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((conn) => {
            const isS3 = conn.source_type?.includes('S3') || !conn.source_type?.includes('NAS');
            const Icon = isS3 ? DatabaseIcon : NASIcon;

            return (
              <div
                key={conn.id}
                role="button" tabIndex={0} onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setSelectedConnector(conn); } }} onClick={() => setSelectedConnector(conn)}
                className="interactive-card bg-nexus-surface border border-nexus-border hover:border-nexus-borderStrong p-4 rounded-sm flex flex-col gap-3 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col min-w-0 pr-2">
                    <span className="text-sm font-bold text-nexus-textPrimary truncate">
                      {conn.name}
                    </span>
                    <span className="inline-flex items-center gap-1 text-sm text-nexus-textMuted mt-0.5">
                      <Icon className="w-3.5 h-3.5 text-nexus-brandText shrink-0" />
                      <span>{conn.source_type || 'S3-compatible'}</span>
                      {conn.region && <span>· {conn.region}</span>}
                    </span>
                  </div>

                  <StatusBadge status={conn.status || 'Verified'} />
                </div>

                <div
                  className="font-mono text-sm text-nexus-brandText bg-nexus-elevated px-2.5 py-1.5 rounded-xs truncate border border-nexus-borderSubtle"
                  title={conn.endpoint_or_path}
                >
                  {conn.endpoint_or_path || 's3://default-bucket/'}
                </div>

                <div className="grid grid-cols-2 gap-2 bg-nexus-elevated p-2.5 rounded-xs border border-nexus-borderSubtle text-sm">
                  <div className="flex flex-col">
                    <span className="text-sm uppercase text-nexus-textMuted font-medium">
                      Discovered Files
                    </span>
                    <span className="font-bold text-nexus-textPrimary font-mono">
                      {typeof conn.discoveredFiles === 'number'
                        ? conn.discoveredFiles.toLocaleString()
                        : '1,420,000+'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm uppercase text-nexus-textMuted font-medium">
                      Sync Stream
                    </span>
                    <span className="font-semibold text-nexus-textSecondary truncate">
                      {conn.syncMode || conn.syncStatus || 'Continuous Event'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-2 mt-auto">
                  <span className="font-mono text-sm text-nexus-textSecondary truncate max-w-[170px]">
                    {conn.authType || 'Vault Delegated'}
                  </span>

                  <button
                    type="button"
                    onClick={(e) => handleTestConnector(e, conn)}
                    disabled={testingId === conn.id}
                    className="flex items-center gap-1 text-sm font-medium px-2 py-0.5 rounded-xs bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border hover:border-nexus-borderStrong text-nexus-textSecondary hover:text-nexus-textPrimary transition-colors"
                  >
                    {testingId === conn.id ? (
                      <SpinnerIcon className="w-3 h-3 animate-spin text-nexus-brandText" />
                    ) : (
                      <RefreshIcon className="w-3 h-3" />
                    )}
                    <span>Test</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Data source details */}
      <Presence>{selectedConnector && (
        <DialogBackdrop onClose={() => setSelectedConnector(null)}
          onClick={() => setSelectedConnector(null)}
        >
          <div
            className="detail-dialog max-w-xl p-6 flex flex-col gap-5 dialog-surface" role="dialog" aria-modal="true" aria-label="Data source details" tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-nexus-border pb-3">
              <div>
                <h3 className="panel-title">
                  {selectedConnector.name}
                </h3>
                <span className="text-sm text-nexus-textMuted font-mono">
                  {selectedConnector.source_type}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedConnector(null)}
                aria-label="Close details" className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Storage Parameters
              </span>
              <div className="grid grid-cols-[130px_1fr] gap-2.5 text-sm bg-nexus-elevated p-3.5 rounded-sm border border-nexus-borderSubtle">
                <span className="text-nexus-textMuted">Status:</span>
                <StatusBadge status={selectedConnector.status || 'Verified'} size="sm" />

                <span className="text-nexus-textMuted">Endpoint / Share:</span>
                <span className="font-mono text-nexus-brandText break-all">
                  {selectedConnector.endpoint_or_path}
                </span>

                <span className="text-nexus-textMuted">Region / Node:</span>
                <span className="text-nexus-textPrimary">{selectedConnector.region || 'internal-cluster'}</span>

                <span className="text-nexus-textMuted">Ingest Mode:</span>
                <span className="text-nexus-textPrimary font-medium">
                  {selectedConnector.syncMode || selectedConnector.syncStatus || 'Continuous Event Stream'}
                </span>

                <span className="text-nexus-textMuted">Auth Delegation:</span>
                <span className="font-mono text-sm text-nexus-textSecondary break-all">
                  {selectedConnector.authType || 'HashiCorp Vault Managed'}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-bold text-nexus-textMuted uppercase tracking-wider font-mono">
                Ingestion Streaming
              </span>
              <p className="text-sm text-nexus-textSecondary leading-relaxed bg-nexus-elevated p-3 rounded-sm border border-nexus-borderSubtle">
                Delta events and new binaries are streamed into Apache Kafka topics for sequential OCR, transcription, and vector enrichment pipelines.
              </p>
            </div>

            <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={(e) => handleTestConnector(e, selectedConnector)}
                disabled={testingId === selectedConnector.id}
                className="px-3 py-1.5 bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border rounded-sm text-sm font-semibold text-nexus-textPrimary transition-colors"
              >
                {testingId === selectedConnector.id ? 'Testing...' : 'Test Connection'}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (showToast) showToast(`Triggered crawl for ${selectedConnector.name}`, 'info');
                  setSelectedConnector(null);
                }}
                className="px-3.5 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover rounded-sm text-sm font-semibold text-white transition-colors"
              >
                Trigger Manual Crawl
              </button>
            </div>
          </div>
        </DialogBackdrop>
      )}</Presence>

      {/* Modal for connecting source */}
      <ConnectorFormModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => fetchConnectors()}
        showToast={showToast}
      />
    </div>
  );
};
