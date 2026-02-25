import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage as ChatMessageType } from '@/types';
import { MolStarViewer } from '@/components/MolViewer/MolStarViewer';

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-white border border-gray-200 shadow-sm'
        }`}
      >
        {/* Main text content */}
        {message.content && (
          <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.toolCalls.map((tc, i) => (
              <ToolCallBlock key={i} name={tc.name} input={tc.input} result={tc.result} />
            ))}
          </div>
        )}

        {/* Visualizations */}
        {message.visualizations && message.visualizations.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.visualizations.map((viz, i) => (
              <div key={i} className="rounded-lg overflow-hidden border border-gray-200">
                <MolStarViewer
                  pdbContents={viz.pdb_contents}
                  style={viz.style}
                  colorBy={viz.color_by}
                />
              </div>
            ))}
          </div>
        )}

        {/* Model info */}
        {message.modelUsed && !isUser && (
          <div className="mt-2 text-xs text-gray-400">
            {message.modelUsed}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCallBlock({
  name,
  input,
  result,
}: {
  name: string;
  input: Record<string, unknown>;
  result?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 text-sm">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-100 rounded-lg"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="font-mono text-primary-700 font-medium">
          {name}
        </span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          <div>
            <span className="text-xs text-gray-500 font-medium">Input:</span>
            <pre className="mt-1 text-xs bg-white p-2 rounded border overflow-x-auto">
              {JSON.stringify(input, null, 2)}
            </pre>
          </div>
          {result && (
            <div>
              <span className="text-xs text-gray-500 font-medium">Result:</span>
              <pre className="mt-1 text-xs bg-white p-2 rounded border overflow-x-auto max-h-40 overflow-y-auto">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(result), null, 2);
                  } catch {
                    return result;
                  }
                })()}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
