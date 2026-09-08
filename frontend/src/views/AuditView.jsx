import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { DownloadIcon } from '../components/Icons';

export const AuditView = ({ onShowToast }) => {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('prism-token') : null;
    fetch('/downloads/audit/events', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Audit access denied')))
      .then((payload) => setEvents(payload.events.map((event) => ({
        id: event.event_id,
        timestamp: event.occurred_at,
        user: event.actor,
        role: 'admin',
        action: event.action,
        target: `${event.entity_type}:${event.entity_id}`,
        status: 'Recorded',
        complianceCode: event.device_code || event.location_code || 'AUDIT'
      }))))
      .catch(() => setEvents(api.getAuditEvents()));
  }, []);

  const handleExportCSV = () => {
    const headers = ["Timestamp", "User", "Role", "Action", "Target", "Status", "Compliance Code"];
    const rows = events.map((e) => [
      `"${e.timestamp}"`,
      `"${e.user}"`,
      `"${e.role}"`,
      `"${e.action}"`,
      `"${e.target}"`,
      `"${e.status}"`,
      `"${e.complianceCode}"`
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `s3_platform_audit_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    onShowToast("Exported S3 audit logs to CSV", "success");
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-prism-brandText uppercase">
            Governance & Security
          </span>
          <h1 className="text-xl font-bold text-prism-textPrimary tracking-tight">Audit & Activity Trail</h1>
          <p className="text-xs text-prism-textMuted mt-0.5">
            Tamper-evident activity logs recording search queries, S3 object inspections, and bucket syncs.
          </p>
        </div>
        <button
          onClick={handleExportCSV}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors self-start"
        >
          <DownloadIcon className="w-3.5 h-3.5" />
          <span>Export CSV</span>
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="bg-prism-surface border border-prism-border rounded-sm overflow-hidden flex flex-col">
        <div className="p-4 border-b border-prism-border flex items-center justify-between">
          <h3 className="text-xs font-bold text-prism-textPrimary">Recent Platform Events</h3>
          <span className="font-mono text-[11px] text-prism-textMuted">{events.length} Events Logged</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-prism-border bg-prism-elevated text-prism-textMuted font-mono text-[10px] uppercase">
                <th className="p-3">Timestamp (UTC)</th>
                <th className="p-3">User & Role</th>
                <th className="p-3">Action</th>
                <th className="p-3">Target S3 Resource</th>
                <th className="p-3">Status</th>
                <th className="p-3">Compliance Code</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-prism-borderSubtle">
              {events.map((evt) => (
                <tr key={evt.id} className="hover:bg-prism-hover transition-colors">
                  <td className="p-3 font-mono text-prism-textSecondary">
                    {evt.timestamp.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="p-3">
                    <strong className="text-prism-textPrimary block">{evt.user}</strong>
                    <span className="text-[10px] text-prism-textMuted font-mono">{evt.role}</span>
                  </td>
                  <td className="p-3">
                    <span className="text-[10px] font-semibold text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-xs">
                      {evt.action}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-[11px] text-prism-textSecondary max-w-xs truncate" title={evt.target}>
                    {evt.target}
                  </td>
                  <td className="p-3">
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      {evt.status}
                    </span>
                  </td>
                  <td className="p-3 font-mono font-bold text-prism-brandText">{evt.complianceCode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
