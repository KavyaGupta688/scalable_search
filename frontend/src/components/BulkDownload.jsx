import React, { useState } from 'react';
import { DownloadDialog } from './DownloadDialog';
import { DownloadIcon } from './Icons';

export const BulkDownload = ({ catalog }) => {
  const [open, setOpen] = useState(false);
  if (!catalog.hasSearch || !catalog.totalCount) return null;
  return <>
    <div className="flex justify-end"><button type="button" className="nx-button flex items-center gap-2" onClick={() => setOpen(true)}><DownloadIcon className="w-4 h-4" />Download results</button></div>
    {open && <DownloadDialog searchParams={catalog.searchParams} onClose={() => setOpen(false)} />}
  </>;
};
