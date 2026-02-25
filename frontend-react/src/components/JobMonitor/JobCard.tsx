import type { JobInfo } from '@/types';
import { ProgressBar } from '@/components/JobMonitor/ProgressBar';
import { useJobStatus } from '@/hooks/useJobStatus';

interface Props {
  job: JobInfo;
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  running: 'bg-yellow-100 text-yellow-700',
  queued: 'bg-blue-100 text-blue-700',
  pending: 'bg-gray-100 text-gray-600',
};

export function JobCard({ job }: Props) {
  const isActive = ['running', 'queued', 'pending'].includes(job.status);
  const progress = useJobStatus(isActive ? job.job_id : null);

  const statusClass = STATUS_COLORS[job.status] || STATUS_COLORS.pending;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-sm text-gray-600">
          {job.job_id.slice(0, 8)}...
        </span>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${statusClass}`}>
          {job.status}
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

      {isActive && progress !== null && (
        <div className="mt-3">
          <ProgressBar progress={progress} />
        </div>
      )}

      {job.error_message && (
        <div className="mt-2 text-xs text-red-600 bg-red-50 rounded p-2">
          {job.error_message}
        </div>
      )}
    </div>
  );
}
