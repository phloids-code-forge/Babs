#!/bin/bash
# Fix Nemotron 3 Nano deployment issues

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "🛠️  Fixing Nemotron 3 Nano Deployment"
echo "====================================="
echo ""

# Check current container status
echo "📊 Current Status:"
echo "-----------------"
if docker ps --filter name=vllm-babs --format "table {{.Names}}\t{{.Status}}" | grep -q vllm-babs; then
    echo -e "${YELLOW}⚠️  vLLM container exists but may not be healthy${NC}"
    docker ps --filter name=vllm-babs
else
    echo -e "${GREEN}✅ No vLLM container running${NC}"
fi

echo ""
echo "🔍 Checking Nano model availability..."
NANO_PATH="$HOME/babs-data/models/nemotron3-nano-nvfp4"
if [ -d "$NANO_PATH" ]; then
    echo -e "${GREEN}✅ Nemotron 3 Nano found at $NANO_PATH${NC}"
    FILE_COUNT=$(find "$NANO_PATH" -name "*.safetensors" | wc -l)
    echo "   Safetensors files: $FILE_COUNT"
else
    echo -e "${RED}❌ Nemotron 3 Nano not found${NC}"
    echo "   Download with:"
    echo "   hf download nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4 --local-dir ~/babs-data/models/nemotron3-nano-nvfp4"
    exit 1
fi

echo ""
read -p "Stop existing container and deploy fresh Nano? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "🔄 Stopping existing container..."
docker stop vllm-babs 2>/dev/null || true
docker rm vllm-babs 2>/dev/null || true
echo -e "${GREEN}✅ Container cleaned up${NC}"

echo ""
echo "🚀 Deploying Nemotron 3 Nano with proven configuration..."
echo "Using community image: avarok/vllm-dgx-spark:v11"
echo ""

# Deploy Nano with the working configuration
docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -e VLLM_FLASHINFER_MOE_BACKEND=latency \
  -v ~/babs-data/models/nemotron3-nano-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  avarok/vllm-dgx-spark:v11 \
  serve /model \
  --served-model-name nemotron3-nano \
  --quantization modelopt_fp4 \
  --kv-cache-dtype fp8 \
  --trust-remote-code \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.85 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser deepseek_r1 \
  --host 0.0.0.0 --port 8000

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Container started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start container${NC}"
    exit 1
fi

echo ""
echo "⏳ Waiting for Nano to initialize (30 seconds)..."
echo "This model loads faster (~30 seconds for 30B parameters)"
echo ""

# Wait for health endpoint
for i in {1..30}; do
    echo -n "."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n${GREEN}✅ vLLM is ready!${NC}"
        break
    fi
    sleep 1
    
    if [ $i -eq 30 ]; then
        echo -e "\n${YELLOW}⚠️  Health endpoint not responding, checking logs...${NC}"
        docker logs vllm-babs --tail 10
        echo ""
        echo "${YELLOW}Model may still be loading. Wait another minute or check logs.${NC}"
    fi
done

echo ""
echo "🧪 Testing inference..."
TEST_RESPONSE=$(curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron3-nano",
    "prompt": "Hello! Quick test of Nemotron 3 Nano.",
    "max_tokens": 20,
    "temperature": 0.7
  }' 2>/dev/null | jq -r '.choices[0].text // "ERROR"' 2>/dev/null || echo "ERROR")

if [ "$TEST_RESPONSE" != "ERROR" ] && [ ! -z "$TEST_RESPONSE" ]; then
    echo -e "${GREEN}✅ Inference successful!${NC}"
    echo "Response: $TEST_RESPONSE"
else
    echo -e "${YELLOW}⚠️  Inference test failed - checking container status...${NC}"
    docker logs vllm-babs --tail 20
fi

echo ""
echo "📊 Final Status:"
echo "---------------"
echo "Container: $(docker ps --filter name=vllm-babs --format '{{.Status}}')"
echo "Model: nemotron3-nano"
echo "Endpoint: http://localhost:8000"
echo "Health: $(if curl -s http://localhost:8000/health > /dev/null 2>&1; then echo "✅ OK"; else echo "❌ Not responding"; fi)"
echo ""
echo "🎉 Nemotron 3 Nano deployment complete!"
echo "Use: ./scripts/check_deployment_status.sh to monitor"