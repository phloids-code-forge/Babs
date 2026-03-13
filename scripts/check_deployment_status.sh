#!/bin/bash
# Check deployment status with visual indicators

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Deployment Status Dashboard      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check container status
echo "📦 Container Status:"
echo "-------------------"
if docker ps --filter name=vllm-babs --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep -q vllm-babs; then
    echo -e "${GREEN}✅ vLLM container is running${NC}"
    docker ps --filter name=vllm-babs --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
else
    echo -e "${RED}❌ vLLM container is not running${NC}"
fi
echo ""

# Check health endpoint
echo "🔌 API Health Check:"
echo "-------------------"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Health endpoint responding${NC}"
    
    # Try to get model info
    echo ""
    echo "🤖 Model Information:"
    echo "-------------------"
    MODEL_INFO=$(curl -s http://localhost:8000/v1/models 2>/dev/null | jq -r '.data[0].id // "Unknown"' 2>/dev/null || echo "Unknown")
    echo "Model: $MODEL_INFO"
    
    # Quick test
    echo ""
    echo "⚡ Quick Test:"
    echo "------------"
    RESPONSE=$(curl -s http://localhost:8000/v1/completions \
      -H "Content-Type: application/json" \
      -d '{"model": "'"$MODEL_INFO"'", "prompt": "Status check", "max_tokens": 5}' 2>/dev/null \
      | jq -r '.choices[0].text // "ERROR"' 2>/dev/null || echo "ERROR")
    
    if [ "$RESPONSE" != "ERROR" ] && [ ! -z "$RESPONSE" ]; then
        echo -e "${GREEN}✅ Inference working: \"$RESPONSE\"${NC}"
    else
        echo -e "${YELLOW}⚠️  Inference test failed${NC}"
    fi
else
    echo -e "${RED}❌ Health endpoint not responding${NC}"
fi
echo ""

# Check memory usage
echo "💾 Memory Usage:"
echo "---------------"
echo -n "System memory: "
free -h | grep Mem | awk '{print $3 "/" $2 " (" $7 " available)"}'

# Check GPU memory if available
if command -v nvidia-smi &> /dev/null; then
    echo ""
    echo "🎮 GPU Status:"
    echo "-------------"
    nvidia-smi | grep -E "(Memory|CUDA|Driver)" | head -3
fi
echo ""

# Check logs for errors
echo "📋 Recent Logs (last 5 lines):"
echo "------------------------------"
if docker ps --filter name=vllm-babs --quiet 2>/dev/null | grep -q .; then
    docker logs vllm-babs --tail 5 2>/dev/null | while read line; do
        if echo "$line" | grep -q -i "error\|fail\|crash\|exception"; then
            echo -e "${RED}⚠ $line${NC}"
        elif echo "$line" | grep -q -i "ready\|success\|loaded\|started"; then
            echo -e "${GREEN}✓ $line${NC}"
        else
            echo "  $line"
        fi
    done
else
    echo "No container logs available"
fi
echo ""

echo "🔄 Quick Actions:"
echo "----------------"
echo "1. View full logs:    docker logs vllm-babs"
echo "2. Restart container: docker restart vllm-babs"
echo "3. Stop container:    docker stop vllm-babs"
echo "4. Deploy Super:      ./scripts/run_super_deployment.sh"
echo "5. Deploy Nano:       Use avarok/vllm-dgx-spark:v11 with nano model"
echo ""