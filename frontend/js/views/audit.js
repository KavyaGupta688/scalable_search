/**
 * Samsung Prism Enterprise Platform - Audit Log View (Simplified)
 * 
 * Clean, user-friendly audit trail for S3 platform compliance.
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function renderAuditView(container, { onShowToast }) {
  const events = api.getAuditEvents();

  function exportCSV() {
    const headers = ["Timestamp", "User", "Role", "Action", "Target", "Status", "Compliance Code"];
    const rows = events.map(e => [
      `"${e.timestamp}"`,
      `"${e.user}"`,
      `"${e.role}"`,
      `"${e.action}"`,
      `"${e.target}"`,
      `"${e.status}"`,
      `"${e.complianceCode}"`
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `s3_platform_audit_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    onShowToast("Exported S3 audit logs to CSV", "success");
  }

  container.innerHTML = `
    <div class="audit-container">
      <div class="page-header">
        <div class="page-title-group">
          <span class="page-eyebrow">Governance & Security</span>
          <h1 class="page-title">Audit & Activity Trail</h1>
          <p class="page-description">
            Tamper-evident activity logs recording search queries, S3 object inspections, and bucket syncs.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primary" id="btn-export-audit">
            ${renderIcon('download')} Export CSV
          </button>
        </div>
      </div>

      <div class="audit-table-panel">
        <div class="data-table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>User & Role</th>
                <th>Action</th>
                <th>Target S3 Resource</th>
                <th>Status</th>
                <th>Audit Code</th>
              </tr>
            </thead>
            <tbody>
              ${events.map(evt => `
                <tr>
                  <td class="mono-text">${evt.timestamp.replace('T', ' ').slice(0, 19)}</td>
                  <td>
                    <div style="font-weight: 600; color: var(--text-primary);">${evt.user}</div>
                    <div class="mono-text" style="font-size: 10px; color: var(--text-muted);">${evt.role}</div>
                  </td>
                  <td><span class="badge badge-info">${evt.action}</span></td>
                  <td class="mono-text" style="font-size: 11px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${evt.target}">
                    ${evt.target}
                  </td>
                  <td>
                    <span class="badge badge-success">
                      <span class="badge-dot"></span> ${evt.status}
                    </span>
                  </td>
                  <td class="mono-text" style="color: var(--brand-primary-text); font-weight: 600;">${evt.complianceCode}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  container.querySelector('#btn-export-audit').addEventListener('click', exportCSV);
}
