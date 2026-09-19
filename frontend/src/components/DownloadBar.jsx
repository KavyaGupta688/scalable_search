import React,{useState,useEffect} from 'react';
import { FeedbackMotion } from './Motion';
import { createBatchDownload,getDownloadStatus } from '../services/downloadApi';
import { saveArchive } from '../services/http';
export function DownloadBar({selectedFileIds=[],onClear,onShowToast}) {
 const [job,setJob]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{if(job?.status!=='building')return;let stopped=false;let timer;
  const poll=async()=>{try{const next=await getDownloadStatus(job.download_id);if(!stopped){setJob(next);setError('');if(next.status==='building')timer=setTimeout(poll,2000);}}catch(e){if(!stopped){setError(e.message);timer=setTimeout(poll,5000);}}};
  timer=setTimeout(poll,2000);return()=>{stopped=true;clearTimeout(timer);};
 },[job?.download_id,job?.status]);
 if(!selectedFileIds.length&&!job)return null;
 const start=async()=>{setBusy(true);setError('');try{setJob(await createBatchDownload(selectedFileIds));}catch(e){setError(e.message);}finally{setBusy(false);}};
 return <div className="download-float"><FeedbackMotion className="download-surface flex gap-4 items-center flex-wrap"><div role="status">{job?`${job.progress||0}/${job.file_count} packaged · ${job.status}`:`${selectedFileIds.length} files selected`}{(error||job?.error)&&<p role="alert">{error||job.error}</p>}</div>
 {!job&&<button className="nx-button nx-button--primary" disabled={busy} onClick={start}>Download selected</button>}
 {job?.status==='ready'&&<button className="nx-button nx-button--primary" disabled={busy} onClick={async()=>{setBusy(true);try{await saveArchive(job.download_id);}catch(e){setError(e.message);}finally{setBusy(false);}}}>Save archive</button>}
 <button className="nx-button" onClick={()=>{setJob(null);onClear?.();}}>Close</button></FeedbackMotion></div>;
}
