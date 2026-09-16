import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Download, Eye, FileText, Image, Music, Search, Table2, Video, X } from 'lucide-react';
import { Brand, Button } from '../components/DesignSystem';
import { useDialog } from '../components/useDialog';
import { DialogBackdrop } from '../components/DialogBackdrop';
import { useAuth } from '../contexts/AuthContext';
import { initialMockData } from '../services/mockData';

const modalityIcons = { image: Image, video: Video, document: FileText, audio: Music, tabular: Table2 };
const heroRecords = ['image', 'document', 'tabular', 'video', 'audio'].map((type) => initialMockData.documents.find((doc) => doc.modality === type));
const popularRecords = [...heroRecords.slice(3), ...heroRecords.slice(0, 3), initialMockData.documents.find((doc) => doc.modality === 'image' && doc.id !== heroRecords[0].id)].filter(Boolean);

function RotatingDatasets({ records, compact = false, onPreview, suspended }) {
  const [offset, setOffset] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const viewportRef = useRef(null);
  const trackRef = useRef(null);
  const animationRef = useRef(null);
  const cardAnimationsRef = useRef([]);
  const [layout, setLayout] = useState({ step: 0, visible: 3 });
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const label = compact ? 'sample' : 'popular';

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  useLayoutEffect(() => {
    const measure = () => {
      const card = trackRef.current.firstElementChild.getBoundingClientRect();
      const gap = parseFloat(getComputedStyle(trackRef.current).gap);
      const visible = Number(getComputedStyle(viewportRef.current).getPropertyValue('--visible-count'));
      const step = (compact ? card.height : card.width) + gap;
      setLayout((previous) => previous.step === step && previous.visible === visible ? previous : { step, visible });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(viewportRef.current);
    measure();
    return () => observer.disconnect();
  }, [compact]);

  // Each loop advances exactly one card, then resets the track without a visual jump.
  useLayoutEffect(() => {
    const start = compact ? `translateY(-${layout.step}px)` : 'translateX(0px)';
    const end = compact ? 'translateY(0px)' : `translateX(-${layout.step}px)`;
    trackRef.current.style.transform = start;
    if (!layout.step || reducedMotion) return;
    const animateTransform = (element, from, to) => {
      const motion = element.animate([
        { transform: from, offset: 0 },
        { transform: from, offset: 0.8, easing: 'cubic-bezier(.4,0,.2,1)' },
        { transform: to, offset: 1 },
      ], { duration: 5000, fill: 'forwards' });
      motion.pause();
      return motion;
    };
    const animation = animateTransform(trackRef.current, start, end);
    const cardAnimations = compact ? Array.from(trackRef.current.children, (slide, slot) =>
      animateTransform(slide.firstElementChild, `scale(${slot === 2 ? 1 : 0.9})`, `scale(${slot === 1 ? 1 : 0.9})`)
    ) : [];
    cardAnimationsRef.current = cardAnimations;
    animationRef.current = animation;
    animation.onfinish = () => setOffset((value) => (value + (compact ? -1 : 1) + records.length) % records.length);
    return () => {
      animation.onfinish = null;
      animation.cancel();
      cardAnimations.forEach((motion) => motion.cancel());
      animationRef.current = null;
      cardAnimationsRef.current = [];
    };
  }, [offset, layout.step, compact, records.length, reducedMotion]);

  useLayoutEffect(() => {
    const animation = animationRef.current;
    if (!animation) return;
    const motions = [animation, ...cardAnimationsRef.current];
    // Hover may finish the current slide, but must never strand partial cards.
    // Keyboard interaction settles at the start so the focused card stays mounted.
    if (focused || suspended || reducedMotion) {
      motions.forEach((motion) => { motion.pause(); motion.currentTime = 0; });
    } else if (hovered && animation.currentTime < 4000) {
      motions.forEach((motion) => motion.pause());
    } else motions.forEach((motion) => motion.play());
  }, [hovered, focused, suspended, reducedMotion, offset, layout.step, compact]);

  return (
    <div ref={viewportRef} className={`dataset-rotation dataset-carousel--${compact ? 'vertical' : 'horizontal'}`} role="region" aria-label={`Explore ${label} datasets`}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}>
      <div ref={trackRef} className={`dataset-carousel-track ${compact ? 'hero-datasets' : 'landing-dataset-grid'}`}>
        {Array.from({ length: layout.visible + 1 }, (_, slot) => {
          const doc = records[(offset + slot - (compact ? 1 : 0) + records.length) % records.length];
          const offscreen = compact ? slot === 0 : slot === layout.visible;
          return <div className="dataset-slide" key={doc.id} aria-hidden={offscreen || undefined} inert={offscreen ? '' : undefined}><DatasetCard doc={doc} compact={compact} onPreview={onPreview} /></div>;
        })}
      </div>
    </div>
  );
}

function DatasetCard({ doc, onPreview, compact = false }) {
  const Icon = modalityIcons[doc.modality] || FileText;
  return (
    <article className={`landing-dataset-card${compact ? ' is-compact' : ''}`}>
      <span className={`dataset-file-icon dataset-file-icon--${doc.modality}`}><Icon size={24} aria-hidden="true" /></span>
      <div className="dataset-card-content">
        <h3 title={doc.filename}>{doc.filename}</h3>
        <p className="dataset-meta"><span>{doc.modality === 'tabular' ? 'Table' : doc.modality}</span><span aria-hidden="true">·</span>{doc.fileSize}</p>
        {!compact && <p className="dataset-description">{doc.canonicalCaption}</p>}
      </div>
      <button type="button" className="dataset-preview-link" onClick={() => onPreview(doc)} aria-label={`Preview ${doc.filename}`} title={`Preview ${doc.filename}`}>
        <Eye size={17} aria-hidden="true" /><span>Preview</span>
      </button>
    </article>
  );
}

function DatasetPreview({ doc, onClose }) {
  const dialogRef = useDialog(onClose);
  const { isAuthenticated, role } = useAuth();
  const Icon = modalityIcons[doc.modality] || FileText;
  return (
    <DialogBackdrop onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="nx-panel landing-preview-dialog" role="dialog" aria-modal="true" aria-labelledby="dataset-preview-title" tabIndex={-1}>
        <header><span className="panel-title">Dataset preview</span><button type="button" className="icon-button" onClick={onClose} aria-label="Close preview"><X size={20} /></button></header>
        <div className="preview-file-heading">
          <span className={`dataset-file-icon dataset-file-icon--${doc.modality}`}><Icon size={30} aria-hidden="true" /></span>
          <h2 id="dataset-preview-title">{doc.filename}</h2>
          <p className="preview-file-meta"><span>{doc.modality === 'tabular' ? 'Table' : doc.modality}</span><span>{doc.fileSize}</span></p>
        </div>
        <p className="preview-description">{doc.aiDescription}</p>
        <ul className="dataset-tags" aria-label="Dataset tags">{doc.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul>
        <footer className="preview-actions"><Button as={Link} to={isAuthenticated ? (role === 'admin' ? '/admin/search' : '/user/search') : '/login/user'}>{isAuthenticated ? 'Open catalog' : 'Sign in to explore'} <ArrowRight size={18} aria-hidden="true" /></Button></footer>
      </section>
    </DialogBackdrop>
  );
}

export const LandingView = () => {
  const { isAuthenticated, role } = useAuth();
  const [previewDoc, setPreviewDoc] = useState(null);
  const workspacePath = role === 'admin' ? '/admin/overview' : '/user/search';
  const searchPath = isAuthenticated ? (role === 'admin' ? '/admin/search' : '/user/search') : '/login/user';

  return (
    <div className="landing-page min-h-screen bg-nexus-bg text-nexus-textPrimary">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <div className="landing-masthead">
        <header className="landing-nav">
          <Link to="/" aria-label="Nexus home"><Brand /></Link>
          <nav aria-label="Explore Nexus"><a href="#benefits">Why Nexus</a><a href="#popular-datasets">Discover datasets</a></nav>
          <div className="landing-nav-actions">{!isAuthenticated && <Link to="/register" className="landing-register">Create account</Link>}<Link to={isAuthenticated ? workspacePath : '/login/user'} className="landing-signin">{isAuthenticated ? 'Back to workspace' : 'Sign in'} <ArrowRight size={18} aria-hidden="true" /></Link></div>
        </header>
      </div>
      <main id="main-content">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="hero-copy">
            <h1 id="landing-title">Find the data<br />you <em>need.</em></h1>
            <p>Search and download images, videos, audio, documents, and tables from one place.</p>
            <div className="hero-actions"><Button as={Link} to={searchPath} id="hero-launch-search">Search datasets <ArrowRight size={18} aria-hidden="true" /></Button><Link to={isAuthenticated ? workspacePath : '/login/admin'} id="hero-admin-console" className="hero-admin-link">{isAuthenticated ? 'Your workspace' : 'Admin sign in'} <ArrowRight size={16} aria-hidden="true" /></Link></div>
          </div>
          <RotatingDatasets records={heroRecords} compact onPreview={setPreviewDoc} suspended={Boolean(previewDoc)} />
        </section>

        <section id="benefits" className="landing-benefits" aria-label="Benefits">
          {[
            { icon: Search, title: 'Search naturally', copy: 'Describe what you need in your own words.' },
            { icon: Eye, title: 'Preview before downloading', copy: 'Check file details to find the right match.' },
            { icon: Download, title: 'Download selected datasets', copy: 'Choose the files you need and download them together.' },
          ].map(({ icon: Icon, title, copy }) => <div key={title}><Icon size={23} aria-hidden="true" /><h2>{title}</h2><p>{copy}</p></div>)}
        </section>

        <section id="popular-datasets" className="landing-popular" aria-labelledby="popular-title">
          <div className="landing-section-heading"><h2 id="popular-title">Popular datasets</h2><Link to={searchPath}>Browse catalog <ArrowRight size={17} aria-hidden="true" /></Link></div>
          <RotatingDatasets records={popularRecords} onPreview={setPreviewDoc} suspended={Boolean(previewDoc)} />
        </section>

        <section className="landing-cta" aria-labelledby="get-started-title">
          <h2 id="get-started-title">Your next dataset is waiting.</h2>
          <div><Button as={Link} to="/login/user">Start exploring <ArrowRight size={18} aria-hidden="true" /></Button></div>
        </section>
      </main>
      <footer className="landing-footer"><Brand /><span>Search. Preview. Download.</span></footer>
      {previewDoc && <DatasetPreview doc={previewDoc} onClose={() => setPreviewDoc(null)} />}
    </div>
  );
};
