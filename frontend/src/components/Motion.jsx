import React, { useEffect, useState } from 'react';
import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, useReducedMotion, useIsPresent } from 'motion/react';
import * as m from 'motion/react-m';
import { Outlet, useLocation } from 'react-router-dom';

export const timing = { control: 0.14, surface: 0.22, page: 0.18 };
export const ease = [0.16, 1, 0.3, 1];
export { m, useReducedMotion };

export function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, [query]);
  return matches;
}

export function MotionProvider({ children }) {
  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">{children}</MotionConfig></LazyMotion>;
}

export function Presence({ children }) {
  return <AnimatePresence initial={false}>{children}</AnimatePresence>;
}

export function PageMotion({ as = 'div', children, ...props }) {
  const reduced = useReducedMotion();
  const Tag = as === 'main' ? m.main : m.div;
  return <Tag {...props} initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: reduced ? 0 : timing.page, ease }}>{children}</Tag>;
}

export function PublicMotionLayout() {
  const location = useLocation();
  return <PageMotion key={location.pathname}><Outlet /></PageMotion>;
}

export function Reveal({ children, ...props }) {
  const reduced = useReducedMotion();
  return <m.section {...props} initial={reduced ? false : { opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.08 }} transition={{ duration: reduced ? 0 : timing.surface, ease }}>{children}</m.section>;
}

export function FeedbackMotion({ children, className, ...props }) {
  const reduced = useReducedMotion();
  const present = useIsPresent();
  return <m.div {...props} inert={present ? undefined : ''} aria-hidden={!present || undefined} className={className} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: reduced ? 0 : 4, transition: { duration: reduced ? 0 : timing.control } }} transition={{ duration: reduced ? 0 : timing.surface, ease }}>{children}</m.div>;
}
