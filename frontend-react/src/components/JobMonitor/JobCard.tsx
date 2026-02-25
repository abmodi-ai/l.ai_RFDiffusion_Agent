import type { JobInfo } from '@/types';
import { ProgressBar } from '@/components/JobMonitor/ProgressBar';
import { useJobStatus } from '@/hooks/useJobStatus';

interface Props {
  job: JobInfo;
  onClickJob?: (job: JobInfo) => void;
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  running: 'bg-yellow-100 text-yellow-700',
  queued: 'bg-blue-100 text-blue-700',
  pending: 'bg-gray-100 text-gray-600',
};

export function JobCard({ job, onClickJob }: Props) {
  const isInitiallyActive = ['running', 'queued', 'pending'].includes(job.status);
  const liveStatus = useJobStatus(isInitiallyActive ? job.job_id : null);

  // Use live status from SSE if available, otherwise fall back to initial DB status
  const effectiveStatus = liveStatus.status ?? job.status;
  const isActive = ['running', 'queued', 'pending'].includes(effectiveStatus);
  const statusClass = STATUS_COLORS[effectiveStatus] || STATUS_COLORS.pending;
  const isClickable = effectiveStatus === 'completed' && !!onClickJob;

  return (
    <div
      className={`bg-white rounded-lg border border-gray-200 p-4 transition-colors ${
        isClickable
          ? 'cursor-pointer hover:border-primary-400 hover:bg-primary-50/30'
          : ''
      }`}
      onClick={isClickable ? () => onClickJob({ ...job, status: effectiveStatus }) : undefined}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={isClickable ? (e) => { if (e.key === 'Enter') onClickJob({ ...job, status: effectiveStatus }); } : undefined}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-sm text-gray-600">
          {job.job_id.slice(0, 8)}...
        </span>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${statusClass}`}>
          {effectiveStatus}
        </span>
      </div>

      {job.contigs && (
        <div className="text-xs text-gray-500 mb-2">
          <span className="font-medium">Contigs:</span>{' '}
          <code className="bg-gray-100 px-1 rounded">{job.contigs}</code>
        </div>
      )}

      <div className="text-xs text-gray-500">
        <span className="font-medium">Designs:</span> {job.num_designs}
        {job.duration_secs && (
          <>
            {' | '}
            <span className="font-medium">Duration:</span>{' '}
            {job.duration_secs < 60
              ? `${Math.round(job.duration_secs)}s`
              : `${Math.round(job.duration_secs / 60)}m`}
          </>
        )}
      </div>

      {/* Progress bar for active jobs */}
      {isActive && liveStatus.progress !== null && (
        <div className="mt-3">
          <ProgressBar progress={liveStatus.progress} />
        </div>
      )}

      {/* Show message from SSE for running/queued jobs */}
      {isActive && liveStatus.message && (
        <div className="mt-1 text-xs text-gray-400 truncate">
          {liveStatus.message}
        </div>
      )}

      {/* Error message for failed jobs */}
      {(job.error_message || effectiveStatus === 'failed') && (
        <div className="mt-2 text-xs text-red-600 bg-red-50 rounded p-2">
          {liveStatus.message || job.error_message || 'Job failed'}
        </div>
      )}

      {/* Clickable hint for completed jobs */}
      {isClickable && (
        <div className="mt-2 text-xs text-primary-600 font-medium">
          Click to view results
        </div>
      )}
    </div>
  );
}
