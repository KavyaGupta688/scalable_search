import React from 'react';
import { CheckIcon, AlertIcon } from '../Icons';

export const ToastContainer = ({ toasts }) => {
  return (
    <div role="status" aria-live="polite" className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-center gap-2.5 px-3.5 py-2.5 rounded-sm bg-nexus-elevated border text-sm text-nexus-textPrimary max-w-sm toast-enter ${
            toast.type === 'success'
              ? 'border-emerald-500/40 text-emerald-300'
              : toast.type === 'warning'
              ? 'border-amber-500/40 text-amber-300'
              : 'border-blue-500/40 text-blue-300'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckIcon className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : (
            <AlertIcon className="w-4 h-4 shrink-0 text-blue-400" />
          )}
          <span className="leading-snug">{toast.message}</span>
        </div>
      ))}
    </div>
  );
};
