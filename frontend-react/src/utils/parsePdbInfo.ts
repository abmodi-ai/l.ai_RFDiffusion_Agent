export interface ChainInfo {
  chainId: string;
  residueCount: number;
  residueStart: number;
  residueEnd: number;
}

export interface PdbInfo {
  chains: ChainInfo[];
  totalAtoms: number;
  hasBfactorData: boolean;
}

/**
 * Parse PDB file contents to extract chain, residue, and B-factor info.
 * Uses PDB fixed-width column format:
 * - Chain ID: column 22 (char index 21)
 * - Residue seq: columns 23-26 (indices 22-25)
 * - B-factor: columns 61-66 (indices 60-65)
 */
export function parsePdbInfo(pdbContents: Record<string, string>): PdbInfo {
  const chainResidues = new Map<string, Set<number>>();
  let totalAtoms = 0;
  let hasBfactorData = false;

  for (const pdbText of Object.values(pdbContents)) {
    const lines = pdbText.split('\n');

    for (const line of lines) {
      if (!line.startsWith('ATOM') && !line.startsWith('HETATM')) continue;
      if (line.length < 54) continue;

      totalAtoms++;

      const chainId = line[21]?.trim() || '_';
      const resSeqStr = line.substring(22, 26).trim();
      const resSeq = parseInt(resSeqStr, 10);

      if (!chainResidues.has(chainId)) {
        chainResidues.set(chainId, new Set());
      }
      if (!isNaN(resSeq)) {
        chainResidues.get(chainId)!.add(resSeq);
      }

      if (!hasBfactorData && line.length >= 66) {
        const bfactor = parseFloat(line.substring(60, 66).trim());
        if (!isNaN(bfactor) && bfactor !== 0.0) {
          hasBfactorData = true;
        }
      }
    }
  }

  const chains: ChainInfo[] = Array.from(chainResidues.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([chainId, residues]) => {
      const resArray = Array.from(residues);
      return {
        chainId,
        residueCount: resArray.length,
        residueStart: Math.min(...resArray),
        residueEnd: Math.max(...resArray),
      };
    });

  return { chains, totalAtoms, hasBfactorData };
}
