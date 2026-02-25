/**
 * useJobStatus hook — SSE connection for real-time job progress.
 *
 * Returns the current progress (0-1), live status, and optional message.
 * Auto-reconnects on connection drop with exponential backoff.
 */

import { useEffect, useRef, useState } from 'react';

export interface JobStatusState {
  progress: number | null;
  status: string | null;
  message: string | null;
}

const INITIAL: JobStatusState = { progress: null, status: null, message: null };

export function useJobStatus(jobId: string | null): JobStatusState {
  const [state, setState] = useState<JobStatusState>(INITIAL);
  const retryCount = useRef(0);
  const maxRetries = 5;

  useEffect(() => {
    if (!jobId) {
      setState(INITIAL);
      return;
    }

    let eventSource: EventSource | null = null;
    let retryTimeout: ReturnType<typeof setTimeout>;
    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const token = localStorage.getItem('ligant_token');
      eventSource = new EventSource(
        `/api/job/${jobId}/stream${token ? `?token=${token}` : ''}`,
      );

      // Reset retry count on successful connection
      eventSource.onopen = () => {
        retryCount.current = 0;
      };

      eventSource.addEventListener('progress', (e) => {
        try {
          const data = JSON.parse(e.data);
          setState({
            progress: data.progress ?? null,
            status: data.status ?? 'running',
            message: data.message ?? null,
          });
        } catch {
          // Ignore
        }
      });

      eventSource.addEventListener('completed', (e) => {
        try {
          const data = JSON.parse(e.data);
          setState({
            progress: 1,
            status: 'completed',
            message: data.message ?? 'Job completed',
          });
        } catch {
          setState({ progress: 1, status: 'completed', message: 'Job completed' });
        }
        eventSource?.close();
      });

      eventSource.addEventListener('failed', (e) => {
        try {
          const data = JSON.parse(e.data);
          setState({
            progress: null,
            status: 'failed',
            message: data.message ?? 'Job failed',
          });
        } catch {
          setState({ progress: null, status: 'failed', message: 'Job failed' });
        }
        eventSource?.close();
      });

      eventSource.addEventListener('error', (e) => {
        // SSE "error" event from backend (job not found, etc.)
        try {
          const me = e as MessageEvent;
          if (me.data) {
            const data = JSON.parse(me.data);
            setState({
              progress: null,
              status: 'failed',
              message: data.error ?? 'Unknown error',
            });
          }
        } catch {
          // Ignore
        }
        eventSource?.close();
      });

      eventSource.onerror = () => {
        eventSource?.close();
        if (!cancelled && retryCount.current < maxRetries) {
          const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
          retryCount.current++;
          retryTimeout = setTimeout(connect, delay);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      eventSource?.close();
      clearTimeout(retryTimeout);
      retryCount.current = 0;
    };
  }, [jobId]);

  return state;
}
