import React from 'react';
import { ImageIcon, VideoIcon, AudioIcon, DocumentIcon, TabularIcon } from './Icons';

const MODALITY_CONFIG = {
  image:    { label: 'Image',    colorClass: 'text-modality-image    bg-[#0c2a3c] border-[#0e3a54]', Icon: ImageIcon },
  video:    { label: 'Video',    colorClass: 'text-modality-video    bg-[#1d1435] border-[#2b1d4d]', Icon: VideoIcon },
  audio:    { label: 'Audio',    colorClass: 'text-modality-audio    bg-[#0c2c18] border-[#0e3e22]', Icon: AudioIcon },
  document: { label: 'Document', colorClass: 'text-modality-document bg-[#2c1a0a] border-[#3e2510]', Icon: DocumentIcon },
  tabular:  { label: 'Tabular',  colorClass: 'text-modality-tabular  bg-[#2c2304] border-[#3e3106]', Icon: TabularIcon },
};

/**
 * ModalityBadge — small colored badge indicating content modality.
 * @param {string} type — one of image | video | audio | document | tabular
 */
export const ModalityBadge = ({ type }) => {
  const config = MODALITY_CONFIG[type?.toLowerCase()] || {
    label: type || 'Unknown',
    colorClass: 'text-nexus-textMuted bg-nexus-elevated border-nexus-borderSubtle',
    Icon: DocumentIcon,
  };
  const { label, colorClass, Icon } = config;
  return (
    <span
      className={`inline-flex w-fit self-start items-center gap-1 whitespace-nowrap text-sm font-mono font-semibold px-1.5 py-0.5 rounded-xs border ${colorClass} shrink-0`}
    >
      <Icon className="w-3 h-3 shrink-0" />
      {label}
    </span>
  );
};
