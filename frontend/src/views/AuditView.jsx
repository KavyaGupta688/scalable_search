import React, { useState, useEffect, useCallback } from 'react';
import { getAuditLogs } from '../services/adminApi';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { DownloadIcon, RefreshIcon, FilterIcon, SpinnerIcon } from '../components/Icons';

const ACTION_TYPES = [
  '',
  'SEARCH',
  'DOWNLOAD',
  'LOGIN',
  'CONNECTOR_CREATED',
  'FILE_PREVIEW',
  'SIMILAR_SEARCH',
  'INGESTION_TRIGGERED',
];

/**
 * AuditView — Admin view for browsing, filtering, and exporting compliance audit logs.
 */
export const AuditView = ({ showToast }) => {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);

  // Filter states
  const [actionType, setActionType] = useState('');
  const [userIdFilter, setUserIdFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const fetchLogs = useCallback(async (targetPage = 1) => {
    setLoading(true);
    try {
      const res = await getAuditLogs({
        action_type: actionType || undefined,
        user_id: userIdFilter || undefined,
        date_range_start: startDate || undefined,
        date_range_end: endDate || undefined,
        page: targetPage,
        page_size: pageSize,
      });

      setEvents(res.events || []);
      setTotal(res.total || 0);
      setPage(targetPage);
    } catch (err) {
      if (showToast) showToast(`Failed to load audit logs: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [actionType, userIdFilter, startDate, endDate, pageSize, showToast]);

  useEffect(() => {
    fetchLogs(1);
  }, [fetchLogs]);

  const handleApplyFilters = (e) => {
    e.preventDefault();
    fetchLogs(1);
  };

  const handleResetFilters = () => {
    setActionType('');
    setUserIdFilter('');
    setStartDate('');
    setEndDate('');
  };

  const handleExportCSV = () => {
    if (events.length === 0) {
      if (showToast) showToast('No audit records to export', 'info');
      return;
    }

    const headers = ['Timestamp', 'User', 'Role', 'Action', 'Target', 'Status', 'Compliance Code'];
    const rows = events.map((e) => [
      `"${e.timestamp || ''}"`,
      `"${e.user || e.user_id || ''}"`,
      `"${e.role || 'user'}"`,
      `"${e.action || e.action_type || ''}"`,
      `"${e.target || e.file_id || ''}"`,
      `"${e.status || 'Success'}"`,
      `"${e.complianceCode || e.compliance_code || 'SOC2-CC6.1'}"`,
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `nexus_audit_logs_p${page}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (showToast) showToast(`Exported page ${page} audit records to CSV`, 'success');
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-nexus-brandText uppercase">
            Governance & Compliance
          </span>
          <h1 className="text-xl font-bold text-nexus-textPrimary tracking-tight">
            Audit & Activity Trail
          </h1>
          <p className="text-xs text-nexus-textMuted mt-0.5">
            Tamper-evident activity logs capturing search queries, S3 inspects, batch downloads, and connector operations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fetchLogs(page)}
            className="p-2 bg-nexus-surface hover:bg-nexus-hover border border-nexus-border rounded-sm text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
            title="Refresh logs"
          >
            <RefreshIcon className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm transition-colors border border-nexus-brand"
          >
            <DownloadIcon className="w-3.5 h-3.5" />
            <span>Export Page CSV</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <form
        onSubmit={handleApplyFilters}
        className="bg-nexus-surface border border-nexus-border p-4 rounded-sm flex flex-col gap-3 text-xs"
      >
        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-nexus-textPrimary font-mono">
          <FilterIcon className="w-3.5 h-3.5 text-nexus-brandText" />
          <span>Filter Audit Trail</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Action Type */}
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-nexus-textMuted">Action Type</label>
            <select
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              className="h-8 px-2.5 bg-nexus-input border border-nexus-border focus:border-nexus-brand rounded-sm text-xs text-nexus-textPrimary outline-none"
            >
              <option value="">All Action Types</option>
              {ACTION_TYPES.filter(Boolean).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* User ID / Email */}
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-nexus-textMuted">User ID / Email</label>
            <input
              type="text"
              value={userIdFilter}
              onChange={(e) => setUserIdFilter(e.target.value)}
              placeholder="Search user..."
              className="h-8 px-2.5 bg-nexus-input border border-nexus-border focus:border-nexus-brand rounded-sm text-xs text-nexus-textPrimary outline-none font-mono"
            />
          </div>

          {/* Date Start */}
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-nexus-textMuted">From Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="h-8 px-2.5 bg-nexus-input border border-nexus-border focus:border-nexus-brand rounded-sm text-xs text-nexus-textPrimary outline-none font-mono"
            />
          </div>

          {/* Date End */}
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-nexus-textMuted">To Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="h-8 px-2.5 bg-nexus-input border border-nexus-border focus:border-nexus-brand rounded-sm text-xs text-nexus-textPrimary outline-none font-mono"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={handleResetFilters}
            className="px-3 py-1.5 rounded-sm bg-nexus-elevated hover:bg-nexus-hover border border-nexus-border text-xs text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
          >
            Clear Filters
          </button>
          <button
            type="submit"
            className="px-4 py-1.5 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm transition-colors border border-nexus-brand"
          >
            Apply Filters
          </button>
        </div>
      </form>

      {/* Audit Log Table */}
      <div className="bg-nexus-surface border border-nexus-border rounded-sm overflow-hidden flex flex-col">
        <div className="p-4 border-b border-nexus-border flex items-center justify-between">
          <h3 className="text-xs font-bold text-nexus-textPrimary">Logged Events</h3>
          <span className="font-mono text-[11px] text-nexus-textMuted">
            Total {total.toLocaleString()} Records Recorded
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-nexus-border bg-nexus-elevated text-nexus-textMuted font-mono text-[10px] uppercase">
                <th className="p-3">Timestamp (UTC)</th>
                <th className="p-3">User & Identity</th>
                <th className="p-3">Action Type</th>
                <th className="p-3">Target Resource / Query</th>
                <th className="p-3">Status</th>
                <th className="p-3">Compliance Code</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-borderSubtle">
              {loading && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-nexus-textMuted">
                    <div className="flex items-center justify-center gap-2">
                      <SpinnerIcon className="w-4 h-4 animate-spin text-nexus-brandText" />
                      <span>Fetching compliance audit records...</span>
                    </div>
                  </td>
                </tr>
              )}

              {!loading && events.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-nexus-textMuted">
                    No audit events match these filters.
                  </td>
                </tr>
              )}

              {!loading &&
                events.map((evt) => (
                  <tr key={evt.id || `${evt.timestamp}-${evt.action_type}`} className="hover:bg-nexus-hover transition-colors">
                    <td className="p-3 font-mono text-nexus-textSecondary whitespace-nowrap">
                      {evt.timestamp ? evt.timestamp.replace('T', ' ').slice(0, 19) : '—'}
                    </td>
                    <td className="p-3">
                      <strong className="text-nexus-textPrimary block font-mono text-[11px]">
                        {evt.user || evt.user_id || 'system'}
                      </strong>
                      <span className="text-[10px] text-nexus-textMuted capitalize">
                        {evt.role || 'service'}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className="text-[10px] font-mono font-semibold text-nexus-brandText bg-nexus-brandSubtle border border-[#23426e] px-1.5 py-0.5 rounded-xs">
                        {evt.action || evt.action_type}
                      </span>
                    </td>
                    <td
                      className="p-3 font-mono text-[11px] text-nexus-textSecondary max-w-xs truncate"
                      title={evt.target || evt.file_id || evt.query_terms}
                    >
                      {evt.target || evt.file_id || evt.query_terms || '—'}
                    </td>
                    <td className="p-3">
                      <StatusBadge status={evt.status || 'Success'} size="sm" />
                    </td>
                    <td className="p-3 font-mono text-[11px] text-nexus-textMuted">
                      {evt.complianceCode || evt.compliance_code || 'SOC2-CC6.1'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-3 bg-nexus-elevated border-t border-nexus-border">
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={(newPage) => fetchLogs(newPage)}
            totalItems={total}
            pageSize={pageSize}
          />
        </div>
      </div>
    </div>
  );
};
