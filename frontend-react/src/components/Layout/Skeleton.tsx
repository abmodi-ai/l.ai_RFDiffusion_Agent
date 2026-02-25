/**
 * Reusable skeleton / shimmer loading placeholders.
 */

export function ChatSkeleton() {
  return (
    <div className="space-y-4 animate-pulse px-4 py-6 max-w-4xl mx-auto">
      {/* User message skeleton */}
      <div className="flex justify-end">
        <div className="w-2/3 h-12 bg-gray-200 rounded-2xl" />
      </div>
      {/* Assistant message skeleton */}
      <div className="flex justify-start">
        <div className="w-3/4 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-full" />
          <div className="h-4 bg-gray-200 rounded w-5/6" />
          <div className="h-4 bg-gray-200 rounded w-4/6" />
        </div>
      </div>
      {/* Another user message */}
      <div className="flex justify-end">
        <div className="w-1/2 h-10 bg-gray-200 rounded-2xl" />
      </div>
      {/* Another assistant message */}
      <div className="flex justify-start">
        <div className="w-3/4 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-full" />
          <div className="h-4 bg-gray-200 rounded w-3/4" />
        </div>
      </div>
    </div>
  );
}

export function SidebarSkeleton() {
  return (
    <div className="p-2 space-y-2 animate-pulse">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="h-10 bg-gray-700 rounded-lg" />
      ))}
    </div>
  );
}

export function JobCardSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 bg-gray-200 rounded w-24" />
        <div className="h-5 bg-gray-200 rounded-full w-16" />
      </div>
      <div className="h-3 bg-gray-200 rounded w-3/4 mb-2" />
      <div className="h-3 bg-gray-200 rounded w-1/2" />
    </div>
  );
}
