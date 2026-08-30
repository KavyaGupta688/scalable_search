/**
 * Icons — All icons sourced from lucide-react.
 * Each export maintains the original name used across the codebase.
 */
import {
  Triangle,
  LayoutDashboard,
  Database,
  CloudDownload,
  Cpu,
  ClipboardList,
  Search,
  SlidersHorizontal,
  LayoutGrid,
  List,
  X,
  Plus,
  RefreshCw,
  ChevronRight,
  ArrowUpRight,
  Eye,
  EyeOff,
  Image,
  Video,
  AudioLines,
  FileText,
  Table2,
  ShieldCheck,
  Bookmark,
  Copy,
  Download,
  Play,
  LogOut,
  Check,
  AlertCircle,
  HardDrive,
  TrendingUp,
  Layers,
  User,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  CheckSquare,
  Scan,
  ArrowUpLeft,
  Users,
} from 'lucide-react';

// Navigation icons
export const NexusIcon = ({ className = 'w-4 h-4' }) => <Triangle className={className} />;
export const OverviewIcon = ({ className = 'w-4 h-4' }) => <LayoutDashboard className={className} />;
export const S3Icon = ({ className = 'w-4 h-4' }) => <Database className={className} />;
export const DatabaseIcon = ({ className = 'w-4 h-4' }) => <Database className={className} />;
export const IngestionIcon = ({ className = 'w-4 h-4' }) => <CloudDownload className={className} />;
export const CpuIcon = ({ className = 'w-4 h-4' }) => <Cpu className={className} />;
export const AuditIcon = ({ className = 'w-4 h-4' }) => <ClipboardList className={className} />;
export const UsersNavIcon = ({ className = 'w-4 h-4' }) => <Users className={className} />;

// UI controls
export const SearchIcon = ({ className = 'w-4 h-4' }) => <Search className={className} />;
export const FilterIcon = ({ className = 'w-4 h-4' }) => <SlidersHorizontal className={className} />;
export const GridIcon = ({ className = 'w-4 h-4' }) => <LayoutGrid className={className} />;
export const ListIcon = ({ className = 'w-4 h-4' }) => <List className={className} />;
export const CloseIcon = ({ className = 'w-4 h-4' }) => <X className={className} />;
export const PlusIcon = ({ className = 'w-4 h-4' }) => <Plus className={className} />;
export const RefreshIcon = ({ className = 'w-4 h-4' }) => <RefreshCw className={className} />;
export const ChevronRightIcon = ({ className = 'w-4 h-4' }) => <ChevronRight className={className} />;
export const ArrowUpRightIcon = ({ className = 'w-4 h-4' }) => <ArrowUpRight className={className} />;
export const ArrowUpLeftIcon = ({ className = 'w-4 h-4' }) => <ArrowUpLeft className={className} />;
export const EyeIcon = ({ className = 'w-4 h-4' }) => <Eye className={className} />;
export const EyeOffIcon = ({ className = 'w-4 h-4' }) => <EyeOff className={className} />;
export const CheckIcon = ({ className = 'w-4 h-4' }) => <Check className={className} />;
export const AlertIcon = ({ className = 'w-4 h-4' }) => <AlertCircle className={className} />;
export const AlertCircleIcon = ({ className = 'w-4 h-4' }) => <AlertCircle className={className} />;

// Modality icons
export const ImageIcon = ({ className = 'w-4 h-4' }) => <Image className={className} />;
export const VideoIcon = ({ className = 'w-4 h-4' }) => <Video className={className} />;
export const AudioIcon = ({ className = 'w-4 h-4' }) => <AudioLines className={className} />;
export const DocumentIcon = ({ className = 'w-4 h-4' }) => <FileText className={className} />;
export const TabularIcon = ({ className = 'w-4 h-4' }) => <Table2 className={className} />;

// Action icons
export const ShieldIcon = ({ className = 'w-4 h-4' }) => <ShieldCheck className={className} />;
export const BookmarkIcon = ({ className = 'w-4 h-4' }) => <Bookmark className={className} />;
export const CopyIcon = ({ className = 'w-4 h-4' }) => <Copy className={className} />;
export const DownloadIcon = ({ className = 'w-4 h-4' }) => <Download className={className} />;
export const PlayIcon = ({ className = 'w-4 h-4' }) => <Play className={className} />;
export const LogoutIcon = ({ className = 'w-4 h-4' }) => <LogOut className={className} />;

// New icons for new features
export const NASIcon = ({ className = 'w-4 h-4' }) => <HardDrive className={className} />;
export const TrendingIcon = ({ className = 'w-4 h-4' }) => <TrendingUp className={className} />;
export const DatasetsIcon = ({ className = 'w-4 h-4' }) => <Layers className={className} />;
export const UserIcon = ({ className = 'w-4 h-4' }) => <User className={className} />;
export const SpinnerIcon = ({ className = 'w-4 h-4' }) => <Loader2 className={className} />;
export const CheckCircleIcon = ({ className = 'w-4 h-4' }) => <CheckCircle2 className={className} />;
export const XCircleIcon = ({ className = 'w-4 h-4' }) => <XCircle className={className} />;
export const ClockIcon = ({ className = 'w-4 h-4' }) => <Clock className={className} />;
export const CheckSquareIcon = ({ className = 'w-4 h-4' }) => <CheckSquare className={className} />;
export const ScanIcon = ({ className = 'w-4 h-4' }) => <Scan className={className} />;
