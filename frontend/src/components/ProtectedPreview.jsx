import React, {useState, useEffect} from 'react';
import {protectedBlob} from '../services/http';
import {ImageIcon, VideoIcon, AudioIcon, DocumentIcon} from './Icons';

export function ProtectedPreview({documentId, modality, name, text}) {
  const [state,setState] = useState({url:null,error:'',loading:false});
  useEffect(() => {
    const controller = new AbortController(); let url;
    setState({url:null,error:'',loading:['image','video','audio'].includes(modality)});
    if (!documentId || !['image','video','audio'].includes(modality)) return () => controller.abort();
    protectedBlob(`/documents/${encodeURIComponent(documentId)}/content`, {signal:controller.signal,maximum:32*1024**2})
      .then(blob => {
        if (!controller.signal.aborted) {url=URL.createObjectURL(blob);setState({url,error:'',loading:false});}
      }).catch(error => {if (!controller.signal.aborted) setState({url:null,error:error.message,loading:false});});
    return () => {controller.abort(); if (url) URL.revokeObjectURL(url);};
  }, [documentId,modality]);
  const unreadable = () => setState({url:null,loading:false,error:'Preview cannot be decoded by this browser.'});
  const Icon = {image:ImageIcon,video:VideoIcon,audio:AudioIcon}[modality] || DocumentIcon;
  return <div className={`${modality === 'image' ? 'h-56' : modality === 'video' ? 'h-48' : 'min-h-28'} bg-nexus-elevated rounded-sm border border-nexus-borderSubtle flex flex-col justify-center overflow-hidden p-3`}>
    {state.url && modality === 'image' ? <img src={state.url} alt={name} onError={unreadable} className="w-full h-full object-contain"/> :
      state.url && modality === 'video' ? <video src={state.url} aria-label={name} onError={unreadable} controls className="w-full h-full"/> :
      state.url && modality === 'audio' ? <audio src={state.url} aria-label={name} onError={unreadable} controls className="w-full"/> :
      <div className="text-sm text-nexus-textMuted flex flex-col items-center gap-2"><Icon className="w-8 h-8 text-nexus-brandText"/><span role={state.error ? 'alert' : 'status'}>{state.loading ? 'Loading protected preview…' : state.error || 'Preview unavailable'}</span>{text && <p className="font-mono whitespace-pre-wrap max-h-40 overflow-auto self-stretch">{text}</p>}</div>}
  </div>;
}
