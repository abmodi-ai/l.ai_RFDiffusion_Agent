/**
 * useJobAutoVisualize — monitors pending RFdiffusion jobs and automatically
 * fetches PDB contents + injects a visualization message when a job completes.
 *
 * No LLM call needed — entire flow is deterministic frontend logic.
 */

import { useEffect, useRef } from 'react';
import { useChatStore } from '@/store/chatStore';
import * as api from '@/api/client';
import type { VisualizationData } from '@/types';

export function useJobAutoVisualize() {
  const pendingJobs = useChatStore((s) => s.pendingJobs);
  const conversationId = useChatStore((s) => s.conversationId);
  const removePendingJob = useChatStore((s) => s.removePendingJob);
  const appendVisualizationMessage = useChatStore((s) => s.appendVisualizationMessage);

  // Track active EventSources so we can clean them up
  const activeStreams = useRef<Map<string, EventSource>>(new Map());
  // Track jobs we've already started monitoring to avoid duplicate connections
  const monitoredJobs = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Filter to jobs in the current conversation
    const currentJobs = pendingJobs.filter(
      (j) => j.conversationId === conversationId,
    );

    for (const job of currentJobs) {
      // Skip if already monitoring this job
      if (monitoredJobs.current.has(job.jobId)) continue;
      monitoredJobs.current.add(job.jobId);

      const es = api.streamJobProgress(job.jobId);
      activeStreams.current.set(job.jobId, es);

      es.addEventListener('completed', async (e) => {
        es.close();
        activeStreams.current.delete(job.jobId);
        monitoredJobs.current.delete(job.jobId);

        try {
          const data = JSON.parse(e.data);
          const pdbIds: string[] = data.output_pdb_ids ?? [];
          if (pdbIds.length === 0) {
            removePendingJob(job.jobId);
            return;
          }

          // Fetch PDB file contents
          const pdbMap = await api.getPdbContents(pdbIds);
          if (Object.keys(pdbMap).length === 0) {
            removePendingJob(job.jobId);
            return;
          }

          // Build visualization data
          const vizData: VisualizationData[] = [
            {
              pdb_contents: pdbMap,
              style: 'cartoon',
              color_by: 'chain',
            },
          ];

          // Inject visualization message into chat
          appendVisualizationMessage(job.jobId, vizData);

          // Persist to backend DB
          api.saveAutoVisualizationMessage(
            job.conversationId,
            job.jobId,
            pdbIds,
          ).catch(() => {
            // Non-critical — viz is already displayed
          });
        } catch {
          // Ignore errors
        }

        removePendingJob(job.jobId);
      });

      es.addEventListener('failed', (e) => {
        es.close();
        activeStreams.current.delete(job.jobId);
        monitoredJobs.current.delete(job.jobId);

        // Extract error message from event
        let errorMessage = 'Unknown error';
        try {
          const data = JSON.parse((e as MessageEvent).data);
          errorMessage = data.message ?? 'Unknown error';
        } catch { /* ignore */ }

        // Auto-send error recovery message to the agent
        const { sendErrorRecovery, isStreaming, conversationId: currentConvId } = useChatStore.getState();
        if (!isStreaming && currentConvId === job.conversationId) {
          sendErrorRecovery(job.jobId, errorMessage);
        }

        removePendingJob(job.jobId);
      });

      es.onerror = () => {
        // Connection error — don't remove the pending job so it can be retried
        es.close();
        activeStreams.current.delete(job.jobId);
        monitoredJobs.current.delete(job.jobId);
      };
    }

    // Cleanup: close streams for jobs that were removed from pendingJobs
    const pendingJobIds = new Set(pendingJobs.map((j) => j.jobId));
    for (const [jobId, es] of activeStreams.current) {
      if (!pendingJobIds.has(jobId)) {
        es.close();
        activeStreams.current.delete(jobId);
        monitoredJobs.current.delete(jobId);
      }
    }
  }, [pendingJobs, conversationId, removePendingJob, appendVisualizationMessage]);

  // Cleanup all streams on unmount
  useEffect(() => {
    return () => {
      for (const es of activeStreams.current.values()) {
        es.close();
      }
      activeStreams.current.clear();
      monitoredJobs.current.clear();
    };
  }, []);
}
