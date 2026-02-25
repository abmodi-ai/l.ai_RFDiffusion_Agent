import { useState, useMemo } from 'react';
import { MolStarViewer } from './MolStarViewer';
import { StructureInfoPanel } from './StructureInfoPanel';
import { parsePdbInfo } from '@/utils/parsePdbInfo';

type ColorMode = 'chain' | 'residue' | 'element' | 'uniform' | 'bfactor';

interface Props {
  pdbContents: Record<string, string>;
  style?: 'cartoon' | 'ball-and-stick' | 'surface' | 'spacefill';
  colorBy?: ColorMode;
  height?: number;
}

export function StructureViewer({
  pdbContents,
  style = 'cartoon',
  colorBy = 'chain',
  height = 400,
}: Props) {
  const [activeColorBy, setActiveColorBy] = useState<ColorMode>(colorBy);

  const pdbInfo = useMemo(() => parsePdbInfo(pdbContents), [pdbContents]);

  const structureCount = Object.keys(pdbContents).length;

  return (
    <div className="relative" style={{ height: `${height}px` }}>
      <MolStarViewer
        pdbContents={pdbContents}
        style={style}
        colorBy={activeColorBy}
        height={height}
      />
      <StructureInfoPanel
        pdbInfo={pdbInfo}
        structureCount={structureCount}
        activeColorBy={activeColorBy}
        onColorByChange={setActiveColorBy}
      />
    </div>
  );
}
