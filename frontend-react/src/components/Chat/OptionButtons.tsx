import type { ParsedOption } from '../../utils/parseMessageOptions';

interface OptionButtonsProps {
  options: ParsedOption[];
  disabled: boolean;
  onSelectOption: (option: ParsedOption) => void;
  /** Label of the option the user already selected (for history highlighting) */
  selectedLabel?: string | null;
}

export function OptionButtons({ options, disabled, onSelectOption, selectedLabel }: OptionButtonsProps) {
  const hasSelection = selectedLabel != null;

  return (
    <div className="mt-4 flex flex-col gap-2">
      {options.map((opt) => {
        const isSelected = hasSelection && opt.label === selectedLabel;
        const isUnselected = hasSelection && !isSelected;

        return (
          <button
            key={opt.number}
            disabled={disabled || hasSelection}
            onClick={() => onSelectOption(opt)}
            className={`
              w-full text-left rounded-lg px-4 py-2.5 text-sm transition-colors
              ${isSelected
                ? 'border-2 border-primary-500 bg-primary-100 text-primary-900 font-medium'
                : isUnselected
                  ? 'border border-gray-200 bg-gray-50 text-gray-400 cursor-default'
                  : opt.isFreeform
                    ? 'border border-dashed border-gray-300 text-gray-600 hover:border-primary-400 hover:text-primary-700 hover:bg-primary-50 cursor-pointer'
                    : 'border border-primary-200 text-primary-800 bg-primary-50/50 hover:bg-primary-100 hover:border-primary-400 cursor-pointer'
              }
              ${!hasSelection && !disabled ? '' : ''}
              disabled:cursor-default
            `}
          >
            <span className={isSelected ? 'font-medium' : ''}>
              {opt.number}. {opt.label}
            </span>
            {opt.description && (
              <span className={`ml-1.5 ${isUnselected ? 'text-gray-300' : 'text-gray-500'}`}>
                — {opt.description}
              </span>
            )}
            {opt.isFreeform && !hasSelection && (
              <svg
                className="inline-block w-3.5 h-3.5 ml-1.5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                />
              </svg>
            )}
            {isSelected && (
              <svg
                className="inline-block w-4 h-4 ml-2 text-primary-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            )}
          </button>
        );
      })}
    </div>
  );
}
