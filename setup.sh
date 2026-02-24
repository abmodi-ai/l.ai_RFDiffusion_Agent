#!/usr/bin/env bash
# =============================================================================
# Ligant.ai — DGX Spark Setup Script
# Installs RFdiffusion + dependencies on aarch64 (ARM64) with CUDA 13.0
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
MODEL_DIR="$SCRIPT_DIR/models"
RFDIFF_DIR="$SCRIPT_DIR/RFdiffusion"

echo "=== Ligant.ai DGX Spark Setup ==="
echo "Script directory: $SCRIPT_DIR"
echo ""

# ---- Step 1: Create virtual environment ----
echo "[1/10] Creating virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip wheel setuptools

# ---- Step 2: Install PyTorch for aarch64 + CUDA 13.0 ----
echo "[2/10] Installing PyTorch (aarch64 + CUDA)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# Verify CUDA
python3 -c "
import torch
print(f'PyTorch {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
"

# ---- Step 3: Build DGL from source (no aarch64 wheel available) ----
echo "[3/10] Building DGL from source (this will take 30-60 minutes)..."
if [ ! -d "$SCRIPT_DIR/dgl" ]; then
    git clone --recurse-submodules https://github.com/dmlc/dgl.git "$SCRIPT_DIR/dgl"
fi

cd "$SCRIPT_DIR/dgl"
mkdir -p build && cd build
cmake .. \
    -DUSE_CUDA=ON \
    -DTORCH_CUDA_ARCH_LIST="12.1" \
    -DBUILD_TORCH=ON \
    -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
cd "$SCRIPT_DIR/dgl/python"
pip install .
cd "$SCRIPT_DIR"

# Verify DGL
python3 -c "
import dgl
print(f'DGL {dgl.__version__}')
print(f'DGL CUDA: {dgl.backend.backend_name}')
"

# ---- Step 4: Clone RFdiffusion ----
echo "[4/10] Cloning RFdiffusion..."
if [ ! -d "$RFDIFF_DIR" ]; then
    git clone https://github.com/RosettaCommons/RFdiffusion.git "$RFDIFF_DIR"
fi

# ---- Step 5: Install SE3-Transformer ----
echo "[5/10] Installing SE3-Transformer..."
cd "$RFDIFF_DIR/env/SE3Transformer"
# Relax version pins for compatibility
sed -i 's/torch>=.*/torch/' requirements.txt 2>/dev/null || true
sed -i 's/numpy>=.*/numpy/' requirements.txt 2>/dev/null || true
pip install .
cd "$SCRIPT_DIR"

# ---- Step 6: Patch e3nn for PyTorch 2.6+ ----
echo "[6/10] Patching e3nn torch.load() for PyTorch 2.6+..."
pip install e3nn
E3NN_PATH=$(python3 -c "import e3nn; import os; print(os.path.dirname(e3nn.__file__))")
find "$E3NN_PATH" -name "*.py" -exec grep -l "torch.load(" {} \; | while read f; do
    sed -i 's/torch\.load(\([^)]*\))/torch.load(\1, weights_only=False)/g' "$f"
    echo "  Patched: $f"
done

# ---- Step 7: Install RFdiffusion ----
echo "[7/10] Installing RFdiffusion..."
cd "$RFDIFF_DIR"
pip install -e .
cd "$SCRIPT_DIR"

# ---- Step 8: Download model weights ----
echo "[8/10] Downloading RFdiffusion model weights..."
mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_DIR/Complex_base_ckpt.pt" ]; then
    wget -O "$MODEL_DIR/Complex_base_ckpt.pt" \
        "http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt"
    echo "  Downloaded Complex_base_ckpt.pt (484 MB)"
else
    echo "  Complex_base_ckpt.pt already exists, skipping."
fi

# ---- Step 9: Install backend dependencies ----
echo "[9/10] Installing backend dependencies..."
pip install -r "$SCRIPT_DIR/backend/requirements.txt"

# ---- Step 10: Verification ----
echo "[10/10] Running verification..."
python3 -c "
import torch
import dgl
import fastapi
import uvicorn
import pydantic
from Bio import PDB

print('=== Verification Passed ===')
print(f'  torch:    {torch.__version__} (CUDA: {torch.cuda.is_available()})')
print(f'  dgl:      {dgl.__version__}')
print(f'  fastapi:  {fastapi.__version__}')
print(f'  uvicorn:  {uvicorn.__version__}')
print(f'  pydantic: {pydantic.__version__}')
print(f'  BioPython PDB: OK')

try:
    import rfdiffusion
    print(f'  rfdiffusion: OK')
except ImportError:
    print(f'  rfdiffusion: import failed (may need PYTHONPATH)')
print('=== Setup Complete ===')
"

echo ""
echo "Setup complete! To start the backend:"
echo "  source .venv/bin/activate"
echo "  cd backend && bash start_server.sh"
echo ""
echo "To start the ngrok tunnel:"
echo "  bash backend/start_tunnel.sh"
