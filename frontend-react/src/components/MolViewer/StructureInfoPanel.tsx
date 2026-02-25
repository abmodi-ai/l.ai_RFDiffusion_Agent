import { useState } from 'react';
import type { PdbInfo } from '@/utils/parsePdbInfo';

type ColorMode = 'chain' | 'residue' | 'element' | 'uniform' | 'bfactor';

interface Props {
  pdbInfo: PdbInfo;
  structureCount: number;
  activeColorBy: ColorMode;
  onColorByChange: (mode: ColorMode) => void;
}

const COLOR_MODES: { value: ColorMode; label: string }[] = [
  { value: 'chain', label: 'Chain' },
  { value: 'bfactor', label: 'B-factor' },
  { value: 'residue', label: 'Residue' },
  { value: 'element', label: 'Element' },
];

export function StructureInfoPanel({
  pdbInfo,
  structureCount,
  activeColorBy,
  onColorByChange,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <div className="absolute bottom-3 left-3 z-10">
        <button
          onClick={() => setCollapsed(false)}
          className="flex items-center gap-1.5 bg-gray-900/80 backdrop-blur-sm text-white text-xs rounded-lg px-3 py-1.5 hover:bg-gray-900/90 transition-colors"
        >
          <span>ℹ Info</span>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="absolute bottom-3 left-3 z-10 bg-gray-900/80 backdrop-blur-sm text-white text-xs rounded-lg p-3 max-w-xs">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium">ℹ Structure Info</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
      </div>

      {/* Chain list */}
      {pdbInfo.chains.length > 0 ? (
        <div className="space-y-0.5 max-h-24 overflow-y-auto mb-2">
          {pdbInfo.chains.map((chain) => (
            <div key={chain.chainId} className="text-gray-300">
              Chain {chain.chainId} · {chain.residueCount} res ({chain.residueStart}–{chain.residueEnd})
            </div>
          ))}
        </div>
      ) : (
        <div className="text-gray-400 mb-2">No structures loaded</div>
      )}

      {structureCount > 0 && (
        <div className="text-gray-400 mb-2">
          {structureCount} structure{structureCount !== 1 ? 's' : ''} loaded
        </div>
      )}

      {/* Color mode buttons */}
      <div className="flex flex-wrap gap-1">
        {COLOR_MODES.map(({ value, label }) => {
          const isActive = activeColorBy === value;
          const isDimmed = value === 'bfactor' && !pdbInfo.hasBfactorData;

          return (
            <button
              key={value}
              onClick={() => onColorByChange(value)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              } ${isDimmed ? 'opacity-50' : ''}`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
