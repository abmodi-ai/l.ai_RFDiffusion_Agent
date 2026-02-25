import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useChatStore } from '@/store/chatStore';
import * as api from '@/api/client';
import type { JobInfo } from '@/types';
import { JobCard } from '@/components/JobMonitor/JobCard';
import { SidebarSkeleton, JobCardSkeleton } from '@/components/Layout/Skeleton';

export function Sidebar() {
  const { user } = useAuthStore();
  const { conversations, loadConversations, selectConversation, newConversation } = useChatStore();
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [activeTab, setActiveTab] = useState<'chats' | 'jobs'>('chats');
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingJobs, setLoadingJobs] = useState(true);

  useEffect(() => {
    loadConversations().finally(() => setLoadingChats(false));
    api.listJobs().then(setJobs).catch(() => {}).finally(() => setLoadingJobs(false));
  }, [loadConversations]);

  return (
    <div className="w-72 bg-gray-900 text-white flex flex-col h-full">
      {/* User info */}
      <div className="p-4 border-b border-gray-700">
        <div className="text-sm font-medium">{user?.display_name || 'User'}</div>
        <div className="text-xs text-gray-400">{user?.email}</div>
      </div>

      {/* New conversation button */}
      <div className="p-3">
        <button
          onClick={newConversation}
          className="w-full flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Conversation
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-700">
        <button
          className={`flex-1 py-2 text-xs font-medium ${
            activeTab === 'chats'
              ? 'text-white border-b-2 border-primary-500'
              : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('chats')}
        >
          Conversations
        </button>
        <button
          className={`flex-1 py-2 text-xs font-medium ${
            activeTab === 'jobs'
              ? 'text-white border-b-2 border-primary-500'
              : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('jobs')}
        >
          Jobs ({jobs.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'chats' ? (
          loadingChats ? (
            <SidebarSkeleton />
          ) : (
            <div className="p-2 space-y-1">
              {conversations.length === 0 && (
                <p className="text-xs text-gray-500 p-3 text-center">
                  No conversations yet
                </p>
              )}
              {conversations.map((conv) => (
                <button
                  key={conv.conversation_id}
                  onClick={() => selectConversation(conv.conversation_id)}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-700 text-sm transition-colors"
                >
                  <div className="text-gray-200 truncate">
                    {conv.title || conv.preview || 'Empty conversation'}
                  </div>
                  {conv.title && conv.preview && (
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {conv.preview}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )
        ) : (
          loadingJobs ? (
            <div className="p-2 space-y-2">
              {[...Array(3)].map((_, i) => <JobCardSkeleton key={i} />)}
            </div>
          ) : (
            <div className="p-2 space-y-2">
              {jobs.length === 0 && (
                <p className="text-xs text-gray-500 p-3 text-center">
                  No jobs yet
                </p>
              )}
              {jobs.map((job) => (
                <JobCard key={job.job_id} job={job} />
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}
