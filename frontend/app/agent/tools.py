"""
Ligant.ai Claude Tool Definitions

Defines the six tools available to Claude for orchestrating RFdiffusion
protein binder design workflows.  Each tool follows the Anthropic tool-use
schema (name, description, input_schema in JSON Schema format).
"""

TOOLS = [
    {
        "name": "upload_pdb",
        "description": (
            "Upload a PDB file to the backend server for analysis or as input "
            "to RFdiffusion. Use this when the user provides a PDB file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": (
                        "Name of the PDB file to upload "
                        "(from the uploaded files in the session)"
                    ),
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "fetch_pdb",
        "description": (
            "Fetch a PDB structure from the RCSB Protein Data Bank by its "
            "4-character PDB ID. Use when the user references a PDB ID "
            "(e.g., '6AL5', '1BRS') instead of uploading a file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdb_id": {
                    "type": "string",
                    "description": "4-character RCSB PDB ID (e.g., '6AL5', '1BRS')",
                }
            },
            "required": ["pdb_id"],
        },
    },
    {
        "name": "run_rfdiffusion",
        "description": (
            "Run RFdiffusion to design protein binders. Requires a PDB file that "
            "has been fetched or uploaded first. IMPORTANT: input_pdb_id must be the "
            "file_id string returned by fetch_pdb or upload_pdb (e.g. "
            "'09ec9f46fbe643a5b68cf006f990917f'), NOT the 4-character PDB ID. "
            "The contigs string defines which residues to keep fixed "
            "and how many residues to generate for the binder. Example contig: "
            "'A1-100/0 100-100' means keep chain A residues 1-100 fixed and "
            "generate a 100-residue binder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "input_pdb_id": {
                    "type": "string",
                    "description": (
                        "The file_id returned from fetch_pdb or upload_pdb "
                        "(a hex string like '09ec9f46fbe643a5b68cf006f990917f'). "
                        "This is NOT the 4-character PDB ID."
                    ),
                },
                "contigs": {
                    "type": "string",
                    "description": (
                        "Contig string defining fixed and generated regions. "
                        "E.g. 'A1-100/0 100-100'"
                    ),
                },
                "num_designs": {
                    "type": "integer",
                    "description": (
                        "Number of binder designs to generate (1-10)"
                    ),
                    "default": 1,
                },
                "diffuser_T": {
                    "type": "integer",
                    "description": (
                        "Number of diffusion timesteps "
                        "(higher=more diverse, 25-200)"
                    ),
                    "default": 50,
                },
                "hotspot_res": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional list of hotspot residues on the target to "
                        "bias binding, e.g. ['A30', 'A33', 'A34']"
                    ),
                },
            },
            "required": ["input_pdb_id", "contigs"],
        },
    },
    {
        "name": "check_job_status",
        "description": (
            "Check the current status and progress of an RFdiffusion job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": (
                        "The job ID returned from run_rfdiffusion"
                    ),
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "get_results",
        "description": (
            "Get the output PDB files from a completed RFdiffusion job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID of a completed job",
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "visualize_structure",
        "description": (
            "Render a 3D visualization of one or more PDB structures in the "
            "browser using py3Dmol. Can show individual structures or overlay "
            "multiple designs on a target."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of PDB file IDs to visualize",
                },
                "style": {
                    "type": "string",
                    "enum": [
                        "cartoon",
                        "surface",
                        "stick",
                        "cartoon+surface",
                    ],
                    "description": "Visualization style",
                    "default": "cartoon",
                },
                "color_by": {
                    "type": "string",
                    "enum": ["chain", "spectrum", "secondary_structure"],
                    "description": "Coloring scheme",
                    "default": "chain",
                },
                "label": {
                    "type": "string",
                    "description": "Optional label for the visualization",
                },
            },
            "required": ["file_ids"],
        },
    },
    {
        "name": "get_pdb_info",
        "description": (
            "Get structural information about a PDB file including chain "
            "count, residue count, and chain details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The file ID of the PDB to analyze",
                }
            },
            "required": ["file_id"],
        },
    },
]
