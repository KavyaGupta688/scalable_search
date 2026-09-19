import React, {useState, useEffect, useCallback} from 'react';
import {request} from '../services/http';

export function useResource(path, {poll = 0} = {}) {
  const [state, setState] = useState({data: null, error: '', loading: Boolean(path)});
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(r => r + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    setState({data: null, error: '', loading: Boolean(path)});
    if (!path) return () => controller.abort();
    const read = async () => {
      try {
        const data = await request(path, {signal: controller.signal});
        if (!controller.signal.aborted) setState({data, error: '', loading: false});
      } catch (error) {
        if (!controller.signal.aborted) setState({data: null, error: error.message, loading: false});
      }
      if (poll && !controller.signal.aborted) timer = setTimeout(read, poll);
    };
    read();
    return () => {controller.abort(); clearTimeout(timer);};
  }, [path, revision, poll]);
  return {...state, reload};
}

export function ResourceState({error, loading, empty, children}) {
  if (error) return <p role="alert" className="px-3.5 py-2.5 rounded-sm border border-red-800/40 bg-red-950/20 text-sm text-nexus-danger">{error}</p>;
  if (loading) return <p role="status" className="text-sm text-nexus-textMuted">Loading…</p>;
  if (empty) return <p className="text-sm text-nexus-textMuted">{children || 'No records yet.'}</p>;
  return null;
}
