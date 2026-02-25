import { useState, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import { useChatStore } from '@/store/chatStore';

export interface ChatInputHandle {
  focusInput: () => void;
}

export const ChatInput = forwardRef<ChatInputHandle>(function ChatInput(_props, ref) {
  const { sendMessage, isStreaming } = useChatStore();
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focusInput: () => {
      textareaRef.current?.focus();
    },
  }));

  const handleSubmit = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    setText('');
    await sendMessage(trimmed);
  }, [text, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t bg-white px-4 py-3">
      <div className="max-w-4xl mx-auto flex items-end gap-3">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about protein design, paste a PDB ID, or describe what you need..."
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 focus:ring-2 focus:ring-primary-500 focus:border-transparent max-h-40 min-h-[48px]"
          rows={1}
          disabled={isStreaming}
        />
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || isStreaming}
          className="p-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        </button>
      </div>
    </div>
  );
});
