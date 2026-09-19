import React, { useEffect, useState } from 'react';
import { DialogBackdrop } from './DialogBackdrop';
import { getFile, postSearchEvent } from '../services/searchApi';
import { protectedBlob } from '../services/http';
import { createBatchDownload } from '../services/downloadApi';
export function ModalDetail({docId,onClose,onSimilar,showToast}) {
 const [doc,setDoc]=useState(null), [error,setError]=useState(''), [url,setUrl]=useState(null), [previewError,setPreviewError]=useState('');
 useEffect(()=>{const c=new AbortController();let objectUrl;
  getFile(docId,c.signal).then(async d=>{setDoc(d);
   const type=d.technical?.mime_type||'';
   if(d.technical?.file_size>32*1024**2 || !/^(image\/(png|jpeg|gif|webp)|video\/mp4|audio\/|application\/pdf)/.test(type)){setPreviewError('Preview unavailable for this format or size. You can request a download.');return;}
   try {const blob=await protectedBlob(`/documents/${docId}/content`,{signal:c.signal,maximum:32*1024**2});if(c.signal.aborted)return;objectUrl=URL.createObjectURL(blob);setUrl(objectUrl);}catch(e){if(e.name!=='AbortError')setPreviewError(e.message);}
  }).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>{c.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[docId]);
 return <DialogBackdrop onClose={onClose}><section role="dialog" aria-modal="true" aria-label="File details" className="nx-panel p-6 w-full max-w-3xl max-h-[90vh] overflow-auto"><button className="nx-button float-right" onClick={onClose}>Close</button>
 {error?<p role="alert">{error}</p>:!doc?<p role="status">Loading details…</p>:<><h2 className="page-title">{doc.title||doc.file_name}</h2><p>{doc.dataset_name} · {doc.file_type}</p>
 {url&&(doc.file_type==='image'?<img src={url} alt={doc.caption||doc.title} className="max-h-96 mx-auto"/>:doc.file_type==='video'?<video controls src={url} className="w-full max-h-96"/>:doc.file_type==='audio'?<audio controls src={url}/>:<iframe title="PDF preview" src={url} className="w-full h-96"/>)}
 {previewError&&<p role="status" className="p-4">{previewError}</p>}<p className="my-4">{doc.description}</p><p>{doc.tags.join(', ')}</p><details className="my-4"><summary>Technical and AI metadata</summary><pre className="text-sm whitespace-pre-wrap">{JSON.stringify({technical:doc.technical,ai:doc.ai_enrichment,summary:doc.content_summary,ocr:doc.ocr_text,transcript:doc.transcript},null,2)}</pre></details>
 <div className="flex gap-3"><button className="nx-button nx-button--primary" onClick={()=>createBatchDownload([docId]).then(()=>showToast?.('Download queued. Follow its progress in Downloads.','success')).catch(e=>setError(e.message))}>Request download</button>{onSimilar&&<button className="nx-button" onClick={()=>onSimilar(docId,doc.title||doc.file_name)}>Find similar files</button>}</div></>}
 </section></DialogBackdrop>;
}
