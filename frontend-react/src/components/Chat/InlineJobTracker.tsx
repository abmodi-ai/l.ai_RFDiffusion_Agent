/**
 * InlineJobTracker — embedded progress bar for RFdiffusion jobs in chat messages.
 *
 * Shows real-time status: queued → running (with progress bar) → completed/failed.
 */

import { useJobStatus } from '@/hooks/useJobStatus';

interface Props {
  jobId: string;
}

export function InlineJobTracker({ jobId }: Props) {
  const { progress, status, message } = useJobStatus(jobId);

  if (!status) {
    return (
      <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-300 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-gray-400" />
        </span>
        Connecting to job...
      </div>
    );
  }

  if (status === 'completed') {
    return (
      <div className="mt-2 flex items-center gap-2 text-sm text-primary-700">
        <span className="inline-flex rounded-full h-2.5 w-2.5 bg-primary-500" />
        <span className="font-medium">Completed</span>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="mt-2 flex items-center gap-2 text-sm text-red-600">
        <span className="inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
        <span className="font-medium">Failed</span>
        {message && <span className="text-red-400">— {message}</span>}
      </div>
    );
  }

  // Running / queued / pending
  const pct = progress != null ? Math.round(progress * 100) : null;

  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary-500" />
        </span>
        <span className="font-medium capitalize">{status}</span>
        {message && <span className="text-gray-400 truncate max-w-xs">— {message}</span>}
      </div>
      {pct != null && (
        <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-primary-500 h-1.5 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
