import React from 'react';
import { CheckCircleIcon, XCircleIcon, ClockIcon, SpinnerIcon } from './Icons';

/**
 * StatusBadge — Displays status indicator (Verified, Unverified, Failed, Processing, Completed, Queued)
 * with consistent design system colors and icons.
 */
export const StatusBadge = ({ status = 'Unverified', size = 'sm' }) => {
  const norm = String(status).toLowerCase();

  let colorClasses = 'text-nexus-textMuted bg-nexus-elevated border-nexus-borderSubtle';
  let Icon = ClockIcon;
  let animate = false;

  if (norm === 'verified' || norm === 'connected' || norm === 'completed' || norm === 'success' || norm === 'synced' || norm === 'ready') {
    colorClasses = 'text-[#4ade80] bg-[#122a1e] border-[#1f5739]';
    Icon = CheckCircleIcon;
  } else if (norm === 'unverified' || norm === 'queued' || norm === 'pending' || norm === 'warning' || norm === 'paused') {
    colorClasses = 'text-[#f59e0b] bg-[#2b200b] border-[#593d14]';
    Icon = ClockIcon;
  } else if (norm === 'failed' || norm === 'error' || norm === 'offline') {
    colorClasses = 'text-[#f87171] bg-[#2b1414] border-[#592323]';
    Icon = XCircleIcon;
  } else if (norm === 'processing' || norm === 'building' || norm === 'active' || norm === 'in_progress' || norm === 'running') {
    colorClasses = 'text-[#60a5fa] bg-nexus-brandSubtle border-[#23426e]';
    Icon = SpinnerIcon;
    animate = true;
  }

  const isMd = size === 'md';
  const sizeClasses = isMd ? 'text-xs px-2.5 py-1 gap-1.5' : 'text-[10px] px-1.5 py-0.5 gap-1';
  const iconSize = isMd ? 'w-3.5 h-3.5' : 'w-3 h-3';

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded-xs border select-none shrink-0 ${sizeClasses} ${colorClasses}`}
    >
      <Icon className={`${iconSize} ${animate ? 'animate-spin' : ''}`} />
      <span className="capitalize">{status}</span>
    </span>
  );
};
