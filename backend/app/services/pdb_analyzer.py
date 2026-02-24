"""
BioPython-based PDB structure analysis.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List

from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import three_to_one


def analyze_pdb(filepath: Path) -> Dict[str, Any]:
    """
    Parse a PDB file and return structural metadata.

    Args:
        filepath: Path to a .pdb file.

    Returns:
        dict with keys:
            num_chains, chains, total_residues, total_atoms
    """
    # Suppress PDBParser warnings (e.g., discontinuous chains, missing atoms)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("input", str(filepath))

    # Use the first model (NMR structures may have multiple)
    model = structure[0]

    chains_info: List[Dict[str, Any]] = []
    total_residues = 0
    total_atoms = 0

    for chain in model:
        # Only count standard residues (skip HETATMs / water)
        residues = [
            res for res in chain.get_residues()
            if res.get_id()[0] == " "  # blank hetflag = standard residue
        ]
        num_residues = len(residues)
        total_residues += num_residues

        # Count all atoms in the chain (including HETATM)
        chain_atoms = sum(1 for _ in chain.get_atoms())
        total_atoms += chain_atoms

        # Build a short sequence preview (first 50 residues)
        seq_chars: list[str] = []
        for res in residues[:50]:
            try:
                seq_chars.append(three_to_one(res.get_resname()))
            except KeyError:
                seq_chars.append("X")
        sequence_preview = "".join(seq_chars)
        if num_residues > 50:
            sequence_preview += "..."

        chains_info.append(
            {
                "chain_id": chain.get_id(),
                "num_residues": num_residues,
                "sequence_preview": sequence_preview,
            }
        )

    return {
        "num_chains": len(chains_info),
        "chains": chains_info,
        "total_residues": total_residues,
        "total_atoms": total_atoms,
    }
