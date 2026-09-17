import React from 'react';
import { createPortal } from 'react-dom';
import { useIsPresent } from 'motion/react';
import { m, timing, ease, useReducedMotion } from './Motion';
import { useDialog } from './useDialog';

// Keep overlays outside animated page containers so they follow the viewport.
export function DialogBackdrop({ children, className = '', onClose, ...props }) {
  const present = useIsPresent();
  const reduced = useReducedMotion();
  const ref = useDialog(() => { if (present) onClose?.(); });
  const child = React.Children.only(children);
  const Surface = child.type === 'section' ? m.section : m.div;
  const blockClosing = (event) => { if (!present) { event.preventDefault(); event.stopPropagation(); } };
  return createPortal(
    <m.div className={`dialog-backdrop ${className}`} {...props}
      data-closing={!present || undefined}
      onClickCapture={blockClosing} onSubmitCapture={blockClosing}
      onKeyDownCapture={(event) => { if (event.key !== 'Tab') blockClosing(event); }}
      initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: reduced ? 0 : timing.control } }}
      transition={{ duration: reduced ? 0 : timing.surface, ease }}>
      <Surface {...child.props} ref={ref}
        initial={reduced ? false : { opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, transition: { duration: reduced ? 0 : timing.control } }}
        transition={{ duration: reduced ? 0 : timing.surface, ease }} />
    </m.div>,
    document.body,
  );
}
