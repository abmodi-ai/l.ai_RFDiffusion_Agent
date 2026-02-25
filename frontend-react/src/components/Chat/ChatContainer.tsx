import { useRef, useEffect, useMemo, useCallback } from 'react';
import { useChatStore } from '@/store/chatStore';
import { ChatMessage } from '@/components/Chat/ChatMessage';
import { ChatInput, type ChatInputHandle } from '@/components/Chat/ChatInput';
import { ChatSkeleton } from '@/components/Layout/Skeleton';
import { parseMessageOptions } from '@/utils/parseMessageOptions';

export function ChatContainer() {
  const { messages, isStreaming, isLoadingHistory, sendMessage } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // For each assistant message with options, determine:
  //  - isInteractive: true only for the last assistant message that has no user reply yet
  //  - selectedLabel: the option label the user chose (matched from next user message)
  const messageProps = useMemo(() => {
    const props: Record<string, { isInteractive: boolean; selectedLabel: string | null }> = {};

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      if (msg.role !== 'assistant' || !msg.content) continue;

      const { options } = parseMessageOptions(msg.content);
      if (options.length === 0) continue;

      // Look for the next user message after this assistant message
      let nextUserContent: string | null = null;
      for (let j = i + 1; j < messages.length; j++) {
        if (messages[j].role === 'user') {
          nextUserContent = messages[j].content;
          break;
        }
      }

      if (nextUserContent == null) {
        // No user reply yet — this is the interactive one
        props[msg.id] = { isInteractive: true, selectedLabel: null };
      } else {
        // Try to match user's reply to one of the options
        const trimmed = nextUserContent.trim();
        let matched: string | null = null;

        for (const opt of options) {
          // Match by exact label (case-insensitive)
          if (trimmed.toLowerCase() === opt.label.toLowerCase()) {
            matched = opt.label;
            break;
          }
          // Match by option number (e.g., user typed "1" or "2")
          if (trimmed === String(opt.number)) {
            matched = opt.label;
            break;
          }
        }

        props[msg.id] = { isInteractive: false, selectedLabel: matched };
      }
    }
    return props;
  }, [messages]);

  const handleFocusInput = useCallback(() => {
    chatInputRef.current?.focusInput();
  }, []);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {isLoadingHistory && <ChatSkeleton />}

        {!isLoadingHistory && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <svg
              className="w-16 h-16 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p className="text-lg font-medium">Start a conversation</p>
            <p className="text-sm mt-1">
              Ask about protein binder design, upload PDB files, or fetch structures from RCSB.
            </p>
          </div>
        )}

        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((msg) => {
            const extra = messageProps[msg.id];
            return (
              <ChatMessage
                key={msg.id}
                message={msg}
                isInteractive={extra?.isInteractive}
                isStreaming={isStreaming}
                onSendMessage={sendMessage}
                onFocusInput={handleFocusInput}
                selectedLabel={extra?.selectedLabel}
              />
            );
          })}

          {isStreaming && (
            <div className="flex items-center gap-2 text-gray-400 text-sm pl-4">
              <div className="animate-pulse flex gap-1">
                <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
              <span>Processing...</span>
            </div>
          )}
        </div>

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <ChatInput ref={chatInputRef} />
    </div>
  );
}
