#!/usr/bin/env bash
# ComfyUI initial setup: creates data directories and builds the image.
# Run once before first start.

set -euo pipefail

COMFYUI_DATA="$HOME/babs-data/comfyui"

echo "==> Creating ComfyUI data directories..."
mkdir -p \
    "$COMFYUI_DATA/models/checkpoints" \
    "$COMFYUI_DATA/models/clip" \
    "$COMFYUI_DATA/models/clip_vision" \
    "$COMFYUI_DATA/models/controlnet" \
    "$COMFYUI_DATA/models/diffusion_models" \
    "$COMFYUI_DATA/models/embeddings" \
    "$COMFYUI_DATA/models/hypernetworks" \
    "$COMFYUI_DATA/models/ipadapter" \
    "$COMFYUI_DATA/models/loras" \
    "$COMFYUI_DATA/models/upscale_models" \
    "$COMFYUI_DATA/models/vae" \
    "$COMFYUI_DATA/models/vae_approx" \
    "$COMFYUI_DATA/output" \
    "$COMFYUI_DATA/input" \
    "$COMFYUI_DATA/user" \
    "$COMFYUI_DATA/custom_nodes_data"

echo "==> Building ComfyUI Docker image (this will take 10-20 min first time)..."
cd "$HOME/babs"
docker compose -f docker/docker-compose.comfyui.yml build --no-cache

echo ""
echo "==> Done. Start with:"
echo "    cd ~/babs && docker compose -f docker/docker-compose.comfyui.yml up -d"
echo ""
echo "==> ComfyUI will be at: http://$(hostname -I | awk '{print $1}'):8188"
echo ""
echo "==> For CivitAI integration, set your API key:"
echo "    export CIVITAI_API_KEY=your_key_here"
echo "    Then restart the container."
