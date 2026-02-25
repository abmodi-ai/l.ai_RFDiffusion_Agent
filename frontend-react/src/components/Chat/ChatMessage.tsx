import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage as ChatMessageType } from '@/types';
import { StructureViewer } from '@/components/MolViewer/StructureViewer';
import { OptionButtons } from './OptionButtons';
import { InlineJobTracker } from './InlineJobTracker';
import { parseMessageOptions, type ParsedOption } from '@/utils/parseMessageOptions';

interface Props {
  message: ChatMessageType;
  /** Whether this message's options are interactive (latest unanswered) */
  isInteractive?: boolean;
  isStreaming?: boolean;
  onSendMessage?: (text: string) => void;
  onFocusInput?: () => void;
  /** The label the user selected (for historical highlighting) */
  selectedLabel?: string | null;
}

export function ChatMessage({
  message,
  isInteractive,
  isStreaming,
  onSendMessage,
  onFocusInput,
  selectedLabel,
}: Props) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // Parse options for ALL assistant messages (not just the last one)
  const { bodyMarkdown, options } = useMemo(() => {
    if (isUser || isSystem || !message.content) {
      return { bodyMarkdown: message.content, options: [] as ParsedOption[] };
    }
    // Don't parse while streaming the latest message (content is incomplete)
    if (isInteractive && isStreaming) {
      return { bodyMarkdown: message.content, options: [] as ParsedOption[] };
    }
    return parseMessageOptions(message.content);
  }, [message.content, isUser, isSystem, isInteractive, isStreaming]);

  // Extract job_id from run_rfdiffusion tool call results for inline tracker
  const rfdiffJobId = useMemo(() => {
    if (!message.toolCalls) return null;
    for (const tc of message.toolCalls) {
      if (tc.name === 'run_rfdiffusion' && tc.result) {
        try {
          const result = JSON.parse(tc.result);
          return result.job_id ?? null;
        } catch {
          return null;
        }
      }
    }
    return null;
  }, [message.toolCalls]);

  const handleOptionClick = (option: ParsedOption) => {
    if (option.isFreeform) {
      onFocusInput?.();
    } else {
      // Send the full label text so it reads naturally in chat history
      onSendMessage?.(option.label);
    }
  };

  // System messages (auto-viz) get a distinct centered style
  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="max-w-[85%] w-full rounded-2xl px-4 py-3 bg-primary-50 border border-primary-200 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex rounded-full h-2.5 w-2.5 bg-primary-500" />
            <span className="text-sm font-medium text-primary-700">Auto-visualization</span>
          </div>
          {message.content && (
            <div className="prose prose-sm max-w-none text-primary-900">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
          {message.visualizations && message.visualizations.length > 0 && (
            <div className="mt-3 space-y-3">
              {message.visualizations.map((viz, i) => (
                <div key={i} className="rounded-lg overflow-hidden border border-primary-200">
                  <StructureViewer
                    pdbContents={viz.pdb_contents}
                    style={viz.style as 'cartoon' | 'ball-and-stick' | 'surface' | 'spacefill'}
                    colorBy={viz.color_by as 'chain' | 'residue' | 'element' | 'uniform'}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

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
        {(bodyMarkdown || message.content) && (
          <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
            <ReactMarkdown>{options.length > 0 ? bodyMarkdown : message.content}</ReactMarkdown>
          </div>
        )}

        {/* Option buttons — shown on ALL assistant messages that have options */}
        {options.length > 0 && (
          <OptionButtons
            options={options}
            disabled={!!isStreaming || (!isInteractive && selectedLabel == null)}
            onSelectOption={handleOptionClick}
            selectedLabel={selectedLabel}
          />
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.toolCalls.map((tc, i) => (
              <ToolCallBlock key={i} name={tc.name} input={tc.input} result={tc.result} />
            ))}
          </div>
        )}

        {/* Inline job tracker for RFdiffusion jobs */}
        {rfdiffJobId && <InlineJobTracker jobId={rfdiffJobId} />}

        {/* Visualizations */}
        {message.visualizations && message.visualizations.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.visualizations.map((viz, i) => (
              <div key={i} className="rounded-lg overflow-hidden border border-gray-200">
                <StructureViewer
                  pdbContents={viz.pdb_contents}
                  style={viz.style as 'cartoon' | 'ball-and-stick' | 'surface' | 'spacefill'}
                  colorBy={viz.color_by as 'chain' | 'residue' | 'element' | 'uniform'}
                />
              </div>
            ))}
          </div>
        )}

        {/* Model info — hidden from users */}
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
