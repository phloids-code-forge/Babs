#!/bin/bash
# Test Nemotron 3 Super 120B NVFP4 with vLLM
# Run this AFTER upgrading to driver 590

set -e

echo "=== Nemotron 3 Super Test Script ==="
echo ""

# Check driver version
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader)
echo "Current driver: $DRIVER_VERSION"

if [[ "$DRIVER_VERSION" < "590" ]]; then
    echo "ERROR: Driver version must be 590 or higher!"
    echo "Run upgrade_driver_590.sh first"
    exit 1
fi

echo "✓ Driver version OK"
echo ""

# Check if Super weights exist
SUPER_MODEL_PATH="$HOME/babs-data/models/nemotron3-super-nvfp4"
if [ ! -d "$SUPER_MODEL_PATH" ]; then
    echo "Super model not found at $SUPER_MODEL_PATH"
    echo "Checking if download is needed..."

    read -p "Download Nemotron 3 Super 120B NVFP4 (~75GB)? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Downloading Nemotron 3 Super 120B NVFP4 (~75GB)..."
        echo "This will take several minutes depending on your connection."
        echo ""
        mkdir -p "$SUPER_MODEL_PATH"

        # Download with progress bar
        hf download nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \
            --local-dir "$SUPER_MODEL_PATH" \
            --local-dir-use-symlinks False

        echo ""
        echo "✓ Download complete!"
        echo ""
    else
        echo "Cannot test without model weights"
        exit 1
    fi
fi

echo "✓ Model weights found"
echo ""

# Build custom vLLM image if not exists
echo "Building custom vLLM image for CUDA 13.1 compatibility..."
if ! docker images | grep -q "vllm-cuda13-super"; then
    cd ~/babs/docker
    docker build -f Dockerfile.vllm-super -t vllm-cuda13-super .
    echo "✓ Custom vLLM image built"
else
    echo "✓ Custom vLLM image already exists"
fi

# Stop current vLLM
echo "Stopping current vLLM container..."
docker stop vllm-babs || true
docker rm vllm-babs || true

# Start vLLM with Super model using custom image
echo "Starting vLLM with Nemotron 3 Super 120B NVFP4..."
echo "Using custom vLLM image built for CUDA 13.1"
echo ""

docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -e VLLM_FLASHINFER_MOE_BACKEND=throughput \
  -v ~/babs-data/models/nemotron3-super-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  -v ~/babs/scripts/super_v3_reasoning_parser.py:/opt/super_v3_reasoning_parser.py \
  vllm-cuda13-super \
  vllm serve /model \
  --served-model-name nemotron3-super \
  --dtype auto \
  --kv-cache-dtype fp8 \
  --tensor-parallel-size 1 \
  --trust-remote-code \
  --gpu-memory-utilization 0.85 \
  --max-num-seqs 4 \
  --max-model-len 32768 \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser-plugin /opt/super_v3_reasoning_parser.py \
  --reasoning-parser super_v3

echo ""
echo "Container started. Waiting for model to load..."
echo "This will take 1-2 minutes for a 120B model."
echo ""

# Wait for vLLM to be ready with progress
for i in {1..180}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ vLLM ready!"
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo "Still loading... ($i seconds elapsed)"
    fi
    sleep 1
done

echo ""
echo "Checking container status and startup logs..."
docker logs vllm-babs --tail 30

echo ""
echo "Testing inference..."
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron3-super",
    "prompt": "Hello! Please respond with a brief greeting.",
    "max_tokens": 50,
    "temperature": 0.7
  }' | jq -r '.choices[0].text'

echo ""
echo "✓ Test complete!"
