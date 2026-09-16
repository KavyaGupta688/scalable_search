import React from 'react';
import { createPortal } from 'react-dom';

// Keep overlays outside animated page containers so they follow the viewport.
export function DialogBackdrop({ children, className = '', ...props }) {
  return createPortal(
    <div className={`dialog-backdrop ${className}`} {...props}>{children}</div>,
    document.body,
  );
}
