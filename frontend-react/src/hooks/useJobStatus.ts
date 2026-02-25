/**
 * useJobStatus hook — SSE connection for real-time job progress.
 *
 * Returns the current progress (0-1) or null if not connected.
 * Auto-reconnects on connection drop with exponential backoff.
 */

import { useEffect, useRef, useState } from 'react';

export function useJobStatus(jobId: string | null): number | null {
  const [progress, setProgress] = useState<number | null>(null);
  const retryCount = useRef(0);
  const maxRetries = 5;

  useEffect(() => {
    if (!jobId) {
      setProgress(null);
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

      eventSource.addEventListener('progress', (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.progress !== null && data.progress !== undefined) {
            setProgress(data.progress);
          }
        } catch {
          // Ignore
        }
      });

      eventSource.addEventListener('completed', () => {
        setProgress(1);
        eventSource?.close();
      });

      eventSource.addEventListener('failed', () => {
        setProgress(null);
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

  return progress;
}
