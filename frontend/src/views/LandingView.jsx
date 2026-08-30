import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// ── Crisp Technical SVG Icons (Custom Handcrafted — No Third-Party Icon Font) ──

const SvgIcon = ({ children, className = 'w-4 h-4' }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    {children}
  </svg>
);

const NexusMark = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polygon points="12 2 22 20 2 20 12 2" strokeWidth="2" />
  </SvgIcon>
);

const SearchIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </SvgIcon>
);

const DatabaseIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </SvgIcon>
);

const CpuIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <rect x="9" y="9" width="6" height="6" />
    <line x1="9" y1="1" x2="9" y2="4" />
    <line x1="15" y1="1" x2="15" y2="4" />
    <line x1="9" y1="20" x2="9" y2="23" />
    <line x1="15" y1="20" x2="15" y2="23" />
    <line x1="20" y1="9" x2="23" y2="9" />
    <line x1="20" y1="14" x2="23" y2="14" />
    <line x1="1" y1="9" x2="4" y2="9" />
    <line x1="1" y1="14" x2="4" y2="14" />
  </SvgIcon>
);

const CloudDownloadIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
    <path d="M12 12v9" />
    <path d="m8 17 4 4 4-4" />
  </SvgIcon>
);

const ShieldIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </SvgIcon>
);

const LayersIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </SvgIcon>
);

const HardDriveIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <line x1="22" y1="12" x2="2" y2="12" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    <line x1="6" y1="16" x2="6.01" y2="16" />
    <line x1="10" y1="16" x2="10.01" y2="16" />
  </SvgIcon>
);

const ArrowRightIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </SvgIcon>
);

const ImageIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <polyline points="21 15 16 10 5 21" />
  </SvgIcon>
);

const VideoIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polygon points="23 7 16 12 23 17 23 7" />
    <rect x="1" y="5" width="15" height="14" rx="2" />
  </SvgIcon>
);

const AudioIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <path d="M2 10v3" />
    <path d="M6 6v11" />
    <path d="M10 3v18" />
    <path d="M14 8v7" />
    <path d="M18 5v13" />
    <path d="M22 10v3" />
  </SvgIcon>
);

const DocumentIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </SvgIcon>
);

const TabularIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" />
  </SvgIcon>
);

const FilterIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </SvgIcon>
);

const CheckSquareIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polyline points="9 11 12 14 22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </SvgIcon>
);

const ActivityIcon = ({ className = 'w-4 h-4' }) => (
  <SvgIcon className={className}>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </SvgIcon>
);

// ── Sample Demonstration Dataset for Live Preview ────────────────────────────

const PREVIEW_RECORDS = [
  {
    id: 'DOC-0491',
    filename: 'optical_micrograph_defect_die_7a.tiff',
    modality: 'image',
    modalityLabel: 'Image',
    score: 98,
    category: 'Inspection Imagery',
    description: 'High-resolution surface scan showing micro-fracture propagation across semiconductor substrate interconnect layers.',
    tags: ['micro-fracture', 'substrate', 'die-inspection', 'defect-analysis'],
    timestamp: '2 mins ago',
    size: '14.8 MB',
    vectorStatus: 'Embedded · 1536 dim',
    icon: ImageIcon,
    colorClass: 'text-modality-image bg-[#0c2a3c] border-[#0e3a54]',
  },
  {
    id: 'DOC-0492',
    filename: 'cleanroom_robotics_feed_cam04.mp4',
    modality: 'video',
    modalityLabel: 'Video',
    score: 94,
    category: 'Motion Capture',
    description: 'Assembly line continuous vision capture documenting automated pick-and-place precision calibration variance.',
    tags: ['assembly-line', 'robotics', 'calibration', 'motion-telemetry'],
    timestamp: '14 mins ago',
    size: '184.2 MB',
    vectorStatus: 'Embedded · Frame-level',
    icon: VideoIcon,
    colorClass: 'text-modality-video bg-[#22173b] border-[#382663]',
  },
  {
    id: 'DOC-0493',
    filename: 'q4_fab_quality_failure_analysis.pdf',
    modality: 'document',
    modalityLabel: 'Document',
    score: 91,
    category: 'Technical Reports',
    description: 'Comprehensive metallurgical failure log containing extracted OCR tables, chemical composition curves, and root causes.',
    tags: ['metallurgy', 'quality-report', 'ocr-extracted', 'yield-loss'],
    timestamp: '1 hour ago',
    size: '6.4 MB',
    vectorStatus: 'Embedded · Chunked (14)',
    icon: DocumentIcon,
    colorClass: 'text-modality-document bg-[#321d10] border-[#532e18]',
  },
  {
    id: 'DOC-0494',
    filename: 'vacuum_chamber_pump_spectral_anomaly.wav',
    modality: 'audio',
    modalityLabel: 'Audio',
    score: 87,
    category: 'Acoustic Diagnostics',
    description: 'Acoustic telemetry audio recording during chamber depressurization identifying cavitation frequency harmonic spikes.',
    tags: ['acoustic-signature', 'depressurization', 'cavitation', 'spectral'],
    timestamp: '3 hours ago',
    size: '2.1 MB',
    vectorStatus: 'Embedded · Spectrogram',
    icon: AudioIcon,
    colorClass: 'text-modality-audio bg-[#0e2a1e] border-[#154630]',
  },
];

export const LandingView = () => {
  const navigate = useNavigate();
  const { isAuthenticated, role, login } = useAuth();
  const [demoLoading, setDemoLoading] = useState(false);

  // State for the interactive search UI preview
  const [previewQuery, setPreviewQuery] = useState('Micro-fracture interconnect propagation');
  const [previewMode, setPreviewMode] = useState('vector'); // 'vector' | 'text' | 'similar'
  const [selectedModality, setSelectedModality] = useState('all');
  const [selectedRecordId, setSelectedRecordId] = useState('DOC-0491');

  // Redirect already authenticated users
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(role === 'admin' ? '/admin/overview' : '/user/search', { replace: true });
    }
  }, [isAuthenticated, role, navigate]);

  const handleQuickDemo = async (demoRole) => {
    setDemoLoading(true);
    try {
      if (demoRole === 'admin') {
        await login('admin@platform.internal', 'admin123', 'admin');
        navigate('/admin/overview', { replace: true });
      } else {
        await login('user@platform.internal', 'user123', 'user');
        navigate('/user/search', { replace: true });
      }
    } catch (err) {
      console.error('Demo sign in failed:', err);
    } finally {
      setDemoLoading(false);
    }
  };

  // Filter preview records based on active modality
  const filteredRecords = PREVIEW_RECORDS.filter((rec) => {
    if (selectedModality === 'all') return true;
    return rec.modality === selectedModality;
  });

  const activeRecord = PREVIEW_RECORDS.find((r) => r.id === selectedRecordId) || PREVIEW_RECORDS[0];

  return (
    <div className="min-h-screen w-full bg-nexus-bg text-nexus-textPrimary font-sans flex flex-col selection:bg-nexus-brand selection:text-white">
      
      {/* ── 1. Top Navigation Bar ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 h-16 border-b border-nexus-border bg-[#0d131a] px-6 lg:px-12 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0 border border-[#23426e]">
            <NexusMark className="w-4 h-4" />
          </div>
          <span className="text-sm font-bold text-nexus-textPrimary tracking-normal font-sans">
            Nexus
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-8 text-xs text-nexus-textSecondary font-medium">
          <a href="#pipeline" className="hover:text-nexus-textPrimary transition-colors py-1">
            Pipeline Architecture
          </a>
          <a href="#preview" className="hover:text-nexus-textPrimary transition-colors py-1">
            Search Interface
          </a>
          <a href="#capabilities" className="hover:text-nexus-textPrimary transition-colors py-1">
            Capabilities
          </a>
          <a href="#infrastructure" className="hover:text-nexus-textPrimary transition-colors py-1">
            Security & Storage
          </a>
        </nav>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/register')}
            className="hidden sm:flex px-3 h-9 text-xs font-medium text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover rounded-sm transition-colors items-center gap-1"
          >
            Register
          </button>
          <button
            onClick={() => navigate('/login/user')}
            className="px-3.5 h-9 text-xs font-medium text-nexus-textPrimary hover:bg-nexus-hover bg-nexus-surface border border-nexus-borderStrong rounded-sm transition-colors flex items-center gap-1.5"
          >
            User Sign In
          </button>
          <button
            onClick={() => navigate('/login/admin')}
            className="px-3.5 h-9 text-xs font-semibold text-white bg-nexus-brand hover:bg-nexus-brandHover border border-[#284470] rounded-sm transition-colors flex items-center gap-1.5"
          >
            <ShieldIcon className="w-3.5 h-3.5" />
            <span>Admin Console</span>
          </button>
        </div>
      </header>

      {/* ── 2. Hero Section ───────────────────────────────────────────────── */}
      <section className="relative px-6 py-16 lg:py-24 max-w-7xl mx-auto w-full flex flex-col items-center text-center">
        
        {/* Eyebrow badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-nexus-surface border border-nexus-borderStrong rounded-xs mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-nexus-success animate-pulse" />
          <span className="text-[11px] font-semibold text-nexus-brandText font-mono">
            Enterprise Multimodal Retrieval Engine
          </span>
        </div>

        {/* Primary Value-Proposition Headline */}
        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-display font-medium text-nexus-textPrimary leading-tight max-w-4xl tracking-tight">
          Unified semantic intelligence across images, audio, video, and documents at scale.
        </h1>

        {/* Subheading with Concrete Detail */}
        <p className="mt-6 text-sm sm:text-base text-nexus-textSecondary max-w-2xl leading-relaxed">
          Ingest unstructured object streams from S3 buckets and enterprise NAS shares. Extract OCR text, acoustic features, and frame-level embeddings into high-dimensional vector indexes for instant, cross-modal discovery.
        </p>

        {/* Primary CTAs & 1-Click Demo */}
        <div className="mt-10 flex flex-col items-center gap-4 w-full max-w-lg">
          <div className="flex flex-col sm:flex-row gap-3.5 w-full justify-center">
            <button
              id="hero-launch-search"
              onClick={() => navigate('/login/user')}
              className="h-11 px-6 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm border border-[#284470] transition-colors flex items-center justify-center gap-2"
            >
              <SearchIcon className="w-4 h-4" />
              <span>Launch User Search</span>
              <ArrowRightIcon className="w-3.5 h-3.5" />
            </button>

            <button
              id="hero-admin-console"
              onClick={() => navigate('/login/admin')}
              className="h-11 px-6 bg-nexus-surface hover:bg-nexus-elevated text-nexus-textPrimary text-xs font-semibold rounded-sm border border-nexus-borderStrong transition-colors flex items-center justify-center gap-2"
            >
              <ShieldIcon className="w-4 h-4 text-nexus-textMuted" />
              <span>Administrator Console</span>
            </button>
          </div>

          {/* Quick Demo Access Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
            <span className="text-[11px] text-nexus-textMuted font-mono">Instant 1-Click Access:</span>
            <button
              type="button"
              disabled={demoLoading}
              onClick={() => handleQuickDemo('user')}
              className="px-2.5 py-1 bg-nexus-surface hover:bg-nexus-elevated border border-nexus-border hover:border-nexus-borderStrong rounded-xs text-[11px] text-nexus-brandText font-mono font-medium flex items-center gap-1.5 transition-colors"
            >
              <SearchIcon className="w-3 h-3" />
              <span>Demo User</span>
            </button>
            <button
              type="button"
              disabled={demoLoading}
              onClick={() => handleQuickDemo('admin')}
              className="px-2.5 py-1 bg-nexus-surface hover:bg-nexus-elevated border border-nexus-border hover:border-nexus-borderStrong rounded-xs text-[11px] text-nexus-brandText font-mono font-medium flex items-center gap-1.5 transition-colors"
            >
              <ShieldIcon className="w-3 h-3" />
              <span>Demo Admin</span>
            </button>
            <span className="text-nexus-borderStrong hidden sm:inline">|</span>
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="text-[11px] text-nexus-textSecondary hover:text-nexus-textPrimary hover:underline font-mono"
            >
              Register Account
            </button>
          </div>
        </div>

        {/* System Technical Indicator Strip */}
        <div className="mt-16 w-full max-w-5xl border-y border-nexus-borderSubtle py-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-left">
          <div className="flex flex-col gap-0.5 px-3">
            <span className="text-[10px] font-mono uppercase text-nexus-textMuted font-semibold">5 Modalities</span>
            <span className="text-xs font-bold text-nexus-textPrimary">Image · Audio · Video · Doc · CSV</span>
          </div>
          <div className="flex flex-col gap-0.5 px-3 border-l border-nexus-borderSubtle">
            <span className="text-[10px] font-mono uppercase text-nexus-textMuted font-semibold">Ingestion Protocol</span>
            <span className="text-xs font-bold text-nexus-textPrimary">S3 SigV4 · SMB / NFS Shares</span>
          </div>
          <div className="flex flex-col gap-0.5 px-3 border-l border-nexus-borderSubtle">
            <span className="text-[10px] font-mono uppercase text-nexus-textMuted font-semibold">Index Engine</span>
            <span className="text-xs font-bold text-nexus-textPrimary">Qdrant Vector + PostgreSQL Hybrid</span>
          </div>
          <div className="flex flex-col gap-0.5 px-3 border-l border-nexus-borderSubtle">
            <span className="text-[10px] font-mono uppercase text-nexus-textMuted font-semibold">Query Latency</span>
            <span className="text-xs font-bold text-nexus-textPrimary">Sub-50ms Approximate Nearest Neighbor</span>
          </div>
        </div>
      </section>

      {/* ── 3. Pipeline Visual Section ─────────────────────────────────────── */}
      <section id="pipeline" className="border-t border-nexus-border bg-nexus-surface/40 py-16 px-6 lg:px-12">
        <div className="max-w-7xl mx-auto">
          
          <div className="flex flex-col items-center text-center mb-12">
            <span className="text-[10px] font-bold font-mono tracking-widest uppercase text-nexus-brandText">
              End-to-End Processing Architecture
            </span>
            <h2 className="text-2xl sm:text-3xl font-display font-medium text-nexus-textPrimary mt-2">
              From Raw Storage to Vector Intelligence
            </h2>
            <p className="text-xs sm:text-sm text-nexus-textSecondary max-w-xl mt-3 leading-relaxed">
              How heterogeneous unstructured data flows through automated enumeration, multi-stage AI feature extraction, dual-store indexing, and unified natural language retrieval.
            </p>
          </div>

          {/* Pipeline Steps Flow (2-column layout on desktop, stacked on mobile) */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            
            {/* Step 1: Ingestion */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle px-2 py-0.5 rounded-xs border border-[#23426e]">
                    STAGE 01
                  </span>
                  <DatabaseIcon className="w-4 h-4 text-nexus-textMuted" />
                </div>
                <h3 className="text-sm font-bold text-nexus-textPrimary">Source Connector Ingest</h3>
                <p className="text-xs text-nexus-textSecondary mt-2 leading-relaxed">
                  Continuous enumeration and incremental sync from S3-compatible vendor stores and on-premise NAS (SMB/NFS) shares with Vault-backed credential management.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-nexus-borderSubtle flex flex-col gap-1.5 font-mono text-[10px] text-nexus-textMuted">
                <div className="flex items-center justify-between">
                  <span>Protocols:</span>
                  <span className="text-nexus-textPrimary">S3, SMB, NFS</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Auth:</span>
                  <span className="text-nexus-textPrimary">SigV4, IAM, Kerberos</span>
                </div>
              </div>
            </div>

            {/* Step 2: Extraction & AI Enrichment */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle px-2 py-0.5 rounded-xs border border-[#23426e]">
                    STAGE 02
                  </span>
                  <CpuIcon className="w-4 h-4 text-nexus-textMuted" />
                </div>
                <h3 className="text-sm font-bold text-nexus-textPrimary">Multimodal Enrichment</h3>
                <p className="text-xs text-nexus-textSecondary mt-2 leading-relaxed">
                  Deep automated content extraction: OCR on technical documents, acoustic signature extraction on audio, keyframe vision embeddings on video streams.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-nexus-borderSubtle flex flex-col gap-1.5 font-mono text-[10px] text-nexus-textMuted">
                <div className="flex items-center justify-between">
                  <span>OCR Engine:</span>
                  <span className="text-nexus-textPrimary">Tesseract / Vision</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Audio Analysis:</span>
                  <span className="text-nexus-textPrimary">Spectral & STT</span>
                </div>
              </div>
            </div>

            {/* Step 3: Dual-Index Engine */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle px-2 py-0.5 rounded-xs border border-[#23426e]">
                    STAGE 03
                  </span>
                  <LayersIcon className="w-4 h-4 text-nexus-textMuted" />
                </div>
                <h3 className="text-sm font-bold text-nexus-textPrimary">Dual-Store Hybrid Index</h3>
                <p className="text-xs text-nexus-textSecondary mt-2 leading-relaxed">
                  Embeddings are written to Qdrant for dense semantic similarity search, while relational metadata, tags, and document text are indexed in PostgreSQL.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-nexus-borderSubtle flex flex-col gap-1.5 font-mono text-[10px] text-nexus-textMuted">
                <div className="flex items-center justify-between">
                  <span>Vector DB:</span>
                  <span className="text-nexus-textPrimary">Qdrant (Cosine)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Relational:</span>
                  <span className="text-nexus-textPrimary">PostgreSQL GIN</span>
                </div>
              </div>
            </div>

            {/* Step 4: Semantic Retrieval */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle px-2 py-0.5 rounded-xs border border-[#23426e]">
                    STAGE 04
                  </span>
                  <SearchIcon className="w-4 h-4 text-nexus-textMuted" />
                </div>
                <h3 className="text-sm font-bold text-nexus-textPrimary">Unified Query & Retrieval</h3>
                <p className="text-xs text-nexus-textSecondary mt-2 leading-relaxed">
                  Query across all 5 modalities simultaneously. Execute natural language semantic lookups, exact keyword matches, or reverse similarity queries with batch export.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-nexus-borderSubtle flex flex-col gap-1.5 font-mono text-[10px] text-nexus-textMuted">
                <div className="flex items-center justify-between">
                  <span>Modes:</span>
                  <span className="text-nexus-textPrimary">Neural, Exact, Similar</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Export:</span>
                  <span className="text-nexus-textPrimary">Batch Archive API</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 4. Visual Proof / Live Interactive Search Preview ──────────────── */}
      <section id="preview" className="py-20 px-6 lg:px-12 max-w-7xl mx-auto w-full">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
          <div>
            <span className="text-[10px] font-bold font-mono tracking-widest uppercase text-nexus-brandText">
              Live Interface Demonstration
            </span>
            <h2 className="text-2xl sm:text-3xl font-display font-medium text-nexus-textPrimary mt-2">
              The Multimodal Discovery Workspace
            </h2>
            <p className="text-xs sm:text-sm text-nexus-textSecondary mt-2 max-w-xl leading-relaxed">
              Explore how users query complex visual anomalies, audio diagnostics, video streams, and failure analysis documents using natural language and modality filters.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-nexus-textMuted">Preview Mode:</span>
            <span className="text-[11px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle px-2 py-0.5 rounded-xs border border-[#23426e]">
              Interactive Showcase
            </span>
          </div>
        </div>

        {/* Representative UI Mockup Shell */}
        <div className="bg-nexus-surface border border-nexus-borderStrong rounded-sm overflow-hidden flex flex-col">
          
          {/* Mock Window Top Bar */}
          <div className="px-4 py-3 bg-[#0a0f15] border-b border-nexus-border flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-nexus-textPrimary">Nexus Search Workspace</span>
              <span className="text-[10px] font-mono text-nexus-textMuted bg-nexus-elevated px-2 py-0.5 rounded-xs border border-nexus-border">
                CLUSTER: PROD-US-EAST · 1,480 OBJECTS
              </span>
            </div>

            {/* Mode selection tabs */}
            <div className="flex items-center gap-1 bg-nexus-elevated p-0.5 rounded-xs border border-nexus-border">
              <button
                onClick={() => setPreviewMode('vector')}
                className={`px-2.5 py-1 rounded-xs text-[11px] font-medium transition-colors ${
                  previewMode === 'vector'
                    ? 'bg-nexus-brand text-white'
                    : 'text-nexus-textSecondary hover:text-nexus-textPrimary'
                }`}
              >
                Natural Language (Vector)
              </button>
              <button
                onClick={() => setPreviewMode('text')}
                className={`px-2.5 py-1 rounded-xs text-[11px] font-medium transition-colors ${
                  previewMode === 'text'
                    ? 'bg-nexus-brand text-white'
                    : 'text-nexus-textSecondary hover:text-nexus-textPrimary'
                }`}
              >
                Exact Keyword (Text)
              </button>
              <button
                onClick={() => setPreviewMode('similar')}
                className={`px-2.5 py-1 rounded-xs text-[11px] font-medium transition-colors ${
                  previewMode === 'similar'
                    ? 'bg-nexus-brand text-white'
                    : 'text-nexus-textSecondary hover:text-nexus-textPrimary'
                }`}
              >
                Similar Object (Reverse)
              </button>
            </div>
          </div>

          {/* Search Query & Filter Bar */}
          <div className="p-4 bg-nexus-surface border-b border-nexus-borderSubtle flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1 flex items-center">
                <SearchIcon className="w-4 h-4 text-nexus-textMuted absolute left-3.5" />
                <input
                  type="text"
                  value={previewQuery}
                  onChange={(e) => setPreviewQuery(e.target.value)}
                  placeholder="Type a natural language description across all modalities..."
                  className="w-full h-10 pl-10 pr-4 bg-nexus-input border border-nexus-border rounded-sm text-xs text-nexus-textPrimary focus:outline-none focus:border-nexus-brandText transition-colors font-mono"
                />
              </div>
              <button
                onClick={() => navigate('/login/user')}
                className="h-10 px-4 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm transition-colors shrink-0 flex items-center gap-1.5"
              >
                <span>Execute Search</span>
                <ArrowRightIcon className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Modality Filter Chips */}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-[10px] font-mono uppercase text-nexus-textMuted flex items-center gap-1">
                <FilterIcon className="w-3 h-3" />
                <span>Filter Modality:</span>
              </span>

              {[
                { id: 'all', label: 'All Modalities', count: 4 },
                { id: 'image', label: 'Image', count: 1 },
                { id: 'video', label: 'Video', count: 1 },
                { id: 'document', label: 'Document', count: 1 },
                { id: 'audio', label: 'Audio', count: 1 },
              ].map((chip) => {
                const isActive = selectedModality === chip.id;
                return (
                  <button
                    key={chip.id}
                    onClick={() => setSelectedModality(chip.id)}
                    className={`px-2.5 py-1 rounded-xs text-[11px] font-medium border transition-colors flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-nexus-brandSubtle text-nexus-brandText border-[#284470] font-semibold'
                        : 'bg-nexus-elevated text-nexus-textSecondary border-nexus-borderSubtle hover:border-nexus-border hover:text-nexus-textPrimary'
                    }`}
                  >
                    <span>{chip.label}</span>
                    <span className="text-[9px] font-mono text-nexus-textMuted bg-nexus-input px-1 py-0.2 rounded-xs">
                      {chip.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Results Grid + Detail Drawer Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-nexus-borderSubtle min-h-[460px]">
            
            {/* Left: Result Cards List (8 Cols) */}
            <div className="lg:col-span-7 p-4 flex flex-col gap-3 overflow-y-auto max-h-[520px]">
              <div className="flex items-center justify-between text-[11px] text-nexus-textMuted font-mono px-1">
                <span>Displaying {filteredRecords.length} high-confidence matches</span>
                <span>Sorted by Vector Similarity Score</span>
              </div>

              {filteredRecords.map((item) => {
                const isSelected = item.id === selectedRecordId;
                const IconComponent = item.icon;
                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedRecordId(item.id)}
                    className={`p-3.5 bg-nexus-surface border rounded-sm transition-colors cursor-pointer flex flex-col gap-2 ${
                      isSelected
                        ? 'border-nexus-brand bg-nexus-brandSubtle/20'
                        : 'border-nexus-border hover:border-nexus-borderStrong hover:bg-nexus-elevated/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${item.colorClass}`}>
                          <IconComponent className="w-3 h-3" />
                          <span>{item.modalityLabel}</span>
                        </span>
                        <span className="text-xs font-bold text-nexus-textPrimary truncate font-mono">
                          {item.filename}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono font-bold text-nexus-brandText bg-nexus-brandSubtle border border-[#23426e] px-1.5 py-0.5 rounded-xs">
                          {item.score}% match
                        </span>
                        <div className="p-1 rounded-xs border border-nexus-border bg-nexus-input text-nexus-textMuted">
                          <CheckSquareIcon className="w-3.5 h-3.5" />
                        </div>
                      </div>
                    </div>

                    <p className="text-[11px] text-nexus-textSecondary leading-relaxed line-clamp-2">
                      {item.description}
                    </p>

                    <div className="flex flex-wrap items-center gap-1.5 mt-1">
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-1.5 py-0.5 bg-nexus-input border border-nexus-borderSubtle rounded-xs text-[10px] text-nexus-textMuted font-mono"
                        >
                          #{tag}
                        </span>
                      ))}
                      <span className="text-[10px] text-nexus-textMuted font-mono ml-auto">
                        {item.size} · {item.timestamp}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Right: Selected Document Detail Inspector (5 Cols) */}
            <div className="lg:col-span-5 p-5 bg-[#0e141c] flex flex-col justify-between">
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-3">
                  <div>
                    <span className="text-[10px] font-mono uppercase text-nexus-textMuted font-semibold">
                      INSPECTION DRAWER
                    </span>
                    <h4 className="text-xs font-bold text-nexus-textPrimary font-mono mt-0.5">
                      {activeRecord.id}
                    </h4>
                  </div>
                  <span className="text-[10px] font-mono text-nexus-success bg-nexus-success/10 border border-nexus-success/20 px-2 py-0.5 rounded-xs">
                    Status: Verified
                  </span>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-mono text-nexus-textMuted uppercase">File Name</span>
                  <span className="text-xs font-mono font-medium text-nexus-textPrimary break-all">
                    {activeRecord.filename}
                  </span>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-mono text-nexus-textMuted uppercase">Extracted Semantic Summary</span>
                  <p className="text-xs text-nexus-textSecondary leading-relaxed bg-nexus-surface p-3 border border-nexus-borderSubtle rounded-xs">
                    {activeRecord.description}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 font-mono text-[11px]">
                  <div className="p-2.5 bg-nexus-surface border border-nexus-borderSubtle rounded-xs flex flex-col gap-1">
                    <span className="text-[10px] text-nexus-textMuted uppercase">Vector Embedding</span>
                    <span className="text-nexus-brandText font-bold">{activeRecord.vectorStatus}</span>
                  </div>
                  <div className="p-2.5 bg-nexus-surface border border-nexus-borderSubtle rounded-xs flex flex-col gap-1">
                    <span className="text-[10px] text-nexus-textMuted uppercase">Modality Category</span>
                    <span className="text-nexus-textPrimary font-medium">{activeRecord.category}</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-nexus-borderSubtle flex flex-col gap-2">
                <button
                  onClick={() => navigate('/login/user')}
                  className="w-full h-9 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm transition-colors flex items-center justify-center gap-1.5"
                >
                  <CloudDownloadIcon className="w-3.5 h-3.5" />
                  <span>Download Object & Verification Manifest</span>
                </button>
                <span className="text-[10px] text-nexus-textMuted text-center font-mono">
                  Full API access requires authorized bearer token
                </span>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 5. Core Capabilities Section (2x2 Grid — NOT 3 in a row) ───────── */}
      <section id="capabilities" className="py-16 px-6 lg:px-12 border-t border-nexus-border bg-nexus-surface/30">
        <div className="max-w-7xl mx-auto">
          
          <div className="flex flex-col items-center text-center mb-12">
            <span className="text-[10px] font-bold font-mono tracking-widest uppercase text-nexus-brandText">
              Core Platform Capabilities
            </span>
            <h2 className="text-2xl sm:text-3xl font-display font-medium text-nexus-textPrimary mt-2">
              Purpose-Built for Industrial Scale Unstructured Data
            </h2>
            <p className="text-xs sm:text-sm text-nexus-textSecondary max-w-xl mt-3 leading-relaxed">
              Every component is designed for high reliability, strict access control, and low-latency discovery across enterprise repositories.
            </p>
          </div>

          {/* 2x2 Feature Grid (Avoids 3-in-a-row constraint) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            
            {/* Capability 1 */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-6 flex flex-col justify-between">
              <div>
                <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-[#23426e] flex items-center justify-center text-nexus-brandText mb-4">
                  <SearchIcon className="w-4 h-4" />
                </div>
                <h3 className="text-base font-bold text-nexus-textPrimary">
                  Hybrid Dense Vector & Relational Search
                </h3>
                <p className="text-xs sm:text-sm text-nexus-textSecondary mt-2.5 leading-relaxed">
                  Execute natural language cross-modal queries against Qdrant dense vector embeddings, exact keyword queries against PostgreSQL metadata, and reverse similarity matching from reference files. Filter dynamically by modality, confidence threshold, and date range.
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-nexus-borderSubtle grid grid-cols-3 gap-2 font-mono text-[10px]">
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Dense Vector</span>
                  <span className="text-nexus-textPrimary font-semibold">Qdrant Index</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Relational</span>
                  <span className="text-nexus-textPrimary font-semibold">PostgreSQL</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Similarity</span>
                  <span className="text-nexus-textPrimary font-semibold">Cosine Distance</span>
                </div>
              </div>
            </div>

            {/* Capability 2 */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-6 flex flex-col justify-between">
              <div>
                <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-[#23426e] flex items-center justify-center text-nexus-brandText mb-4">
                  <HardDriveIcon className="w-4 h-4" />
                </div>
                <h3 className="text-base font-bold text-nexus-textPrimary">
                  Multi-Source Enterprise Ingestion Layer
                </h3>
                <p className="text-xs sm:text-sm text-nexus-textSecondary mt-2.5 leading-relaxed">
                  Configure direct connectors to generic S3-compatible vendor stores, AWS S3 buckets, and enterprise NAS shares via SMB or NFS. Supports SigV4 credentials, IAM role delegation, continuous event streams, or automated hourly polling with write-only HashiCorp Vault secrets.
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-nexus-borderSubtle grid grid-cols-3 gap-2 font-mono text-[10px]">
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Storage Types</span>
                  <span className="text-nexus-textPrimary font-semibold">S3, SMB, NFS</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Secrets</span>
                  <span className="text-nexus-textPrimary font-semibold">HashiCorp Vault</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Sync Modes</span>
                  <span className="text-nexus-textPrimary font-semibold">Event & Hourly</span>
                </div>
              </div>
            </div>

            {/* Capability 3 */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-6 flex flex-col justify-between">
              <div>
                <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-[#23426e] flex items-center justify-center text-nexus-brandText mb-4">
                  <CpuIcon className="w-4 h-4" />
                </div>
                <h3 className="text-base font-bold text-nexus-textPrimary">
                  Automated Multi-Stage AI Enrichment
                </h3>
                <p className="text-xs sm:text-sm text-nexus-textSecondary mt-2.5 leading-relaxed">
                  Raw files pass through automated four-stage enrichment pipelines upon arrival. Includes optical character recognition on scanned PDFs and TIFFs, speech-to-text acoustic transcription, frame anomaly embeddings on video capture, and contextual semantic tag generation.
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-nexus-borderSubtle grid grid-cols-3 gap-2 font-mono text-[10px]">
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">OCR Pipeline</span>
                  <span className="text-nexus-textPrimary font-semibold">Table & Text</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Acoustic</span>
                  <span className="text-nexus-textPrimary font-semibold">Spectral Match</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Vision</span>
                  <span className="text-nexus-textPrimary font-semibold">Frame Embedding</span>
                </div>
              </div>
            </div>

            {/* Capability 4 */}
            <div className="bg-nexus-surface border border-nexus-border rounded-sm p-6 flex flex-col justify-between">
              <div>
                <div className="w-8 h-8 rounded-sm bg-nexus-brandSubtle border border-[#23426e] flex items-center justify-center text-nexus-brandText mb-4">
                  <ShieldIcon className="w-4 h-4" />
                </div>
                <h3 className="text-base font-bold text-nexus-textPrimary">
                  Role-Based Security & Compliance Auditing
                </h3>
                <p className="text-xs sm:text-sm text-nexus-textSecondary mt-2.5 leading-relaxed">
                  Strict separation of privileges between administrators and data users via JWT Bearer authentication. Comprehensive audit logging records all search events, file previews, and batch download operations with timestamped compliance identifiers.
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-nexus-borderSubtle grid grid-cols-3 gap-2 font-mono text-[10px]">
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Auth Standard</span>
                  <span className="text-nexus-textPrimary font-semibold">JWT Bearer (HS256)</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Access Control</span>
                  <span className="text-nexus-textPrimary font-semibold">RBAC Middleware</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-nexus-textMuted uppercase">Audit Log</span>
                  <span className="text-nexus-textPrimary font-semibold">Full Event Trace</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 6. Technical Specifications & Architecture Grid ───────────────── */}
      <section id="infrastructure" className="py-16 px-6 lg:px-12 border-t border-nexus-border bg-nexus-bg">
        <div className="max-w-7xl mx-auto">
          
          <div className="flex flex-col items-center text-center mb-10">
            <span className="text-[10px] font-bold font-mono tracking-widest uppercase text-nexus-brandText">
              System Specifications
            </span>
            <h2 className="text-xl sm:text-2xl font-display font-medium text-nexus-textPrimary mt-1.5">
              Production Architecture Overview
            </h2>
          </div>

          <div className="bg-nexus-surface border border-nexus-border rounded-sm p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              
              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-bold text-nexus-textPrimary flex items-center gap-1.5">
                  <DatabaseIcon className="w-3.5 h-3.5 text-nexus-brandText" />
                  <span>Storage Connectors</span>
                </span>
                <p className="text-[11px] text-nexus-textSecondary leading-relaxed">
                  S3-compatible Object Storage (MinIO, Ceph, AWS S3) with SigV4/SigV2 path or virtual-hosted addressing, and SMB/NFS NAS mounts.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-bold text-nexus-textPrimary flex items-center gap-1.5">
                  <CpuIcon className="w-3.5 h-3.5 text-nexus-brandText" />
                  <span>Processing Engine</span>
                </span>
                <p className="text-[11px] text-nexus-textSecondary leading-relaxed">
                  Decoupled asynchronous worker nodes orchestrating feature extraction, document chunking, and embedding generation pipelines.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-bold text-nexus-textPrimary flex items-center gap-1.5">
                  <LayersIcon className="w-3.5 h-3.5 text-nexus-brandText" />
                  <span>Indexing Subsystem</span>
                </span>
                <p className="text-[11px] text-nexus-textSecondary leading-relaxed">
                  Qdrant vector collection for 1536-dimension cosine similarity matching paired with PostgreSQL for relational catalog queries.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-bold text-nexus-textPrimary flex items-center gap-1.5">
                  <ShieldIcon className="w-3.5 h-3.5 text-nexus-brandText" />
                  <span>Security & Auditing</span>
                </span>
                <p className="text-[11px] text-nexus-textSecondary leading-relaxed">
                  FastAPI RBAC middleware, bcrypt password hashing, JWT bearer verification, and persistent compliance event logging.
                </p>
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* ── 7. Call To Action Strip ───────────────────────────────────────── */}
      <section className="border-t border-nexus-border bg-nexus-surface py-12 px-6 lg:px-12 text-center">
        <div className="max-w-3xl mx-auto flex flex-col items-center gap-6">
          <h2 className="text-2xl font-display font-medium text-nexus-textPrimary">
            Ready to access multimodal search and data ingestion?
          </h2>
          <p className="text-xs text-nexus-textSecondary max-w-lg leading-relaxed">
            Select your access track to begin searching across enterprise datasets or configure source connectors.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 w-full max-w-md justify-center">
            <button
              onClick={() => navigate('/login/user')}
              className="h-10 px-6 bg-nexus-brand hover:bg-nexus-brandHover text-white text-xs font-semibold rounded-sm border border-[#284470] transition-colors"
            >
              Sign in as Standard User
            </button>
            <button
              onClick={() => navigate('/login/admin')}
              className="h-10 px-6 bg-nexus-elevated hover:bg-nexus-hover text-nexus-textPrimary text-xs font-semibold rounded-sm border border-nexus-borderStrong transition-colors"
            >
              Sign in as Administrator
            </button>
            <button
              onClick={() => navigate('/register')}
              className="h-10 px-6 bg-nexus-surface hover:bg-nexus-hover text-nexus-brandText text-xs font-semibold rounded-sm border border-nexus-borderStrong transition-colors"
            >
              Register
            </button>
          </div>
          <div className="flex items-center justify-center gap-3 text-[11px] text-nexus-textMuted font-mono">
            <span>Instant Demo:</span>
            <button
              disabled={demoLoading}
              onClick={() => handleQuickDemo('user')}
              className="text-nexus-brandText hover:underline"
            >
              User Demo
            </button>
            <span>·</span>
            <button
              disabled={demoLoading}
              onClick={() => handleQuickDemo('admin')}
              className="text-nexus-brandText hover:underline"
            >
              Admin Demo
            </button>
          </div>
        </div>
      </section>

      {/* ── 8. Minimal Clean Footer (No Placeholder Links) ────────────────── */}
      <footer className="border-t border-nexus-borderSubtle bg-[#0a0f15] px-6 lg:px-12 py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 bg-nexus-brand rounded-xs flex items-center justify-center text-white shrink-0">
            <NexusMark className="w-3 h-3" />
          </div>
          <span className="text-[11px] font-mono font-bold text-nexus-textPrimary">
            NEXUS MULTIMODAL PLATFORM
          </span>
          <span className="text-[10px] font-mono text-nexus-textMuted">
            v0.2.0
          </span>
        </div>

        <div className="flex items-center gap-6 text-[11px] text-nexus-textMuted font-mono">
          <span>SYSTEM OPERATIONAL</span>
          <span>RBAC ENFORCED</span>
          <span>INTERNAL ACCESS ONLY</span>
        </div>
      </footer>

    </div>
  );
};
