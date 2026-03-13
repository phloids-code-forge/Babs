#!/bin/bash
# Diagnostic script for Nemotron 3 Super deployment issues

set -e

# Color codes for progress display
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Nemotron 3 Super Diagnostics     ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "🔄 Starting comprehensive system check..."
echo ""

# Check system info
echo "📋 1. System Information:"
echo "---------------------"
echo -n "Checking NVIDIA driver... "
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo "UNKNOWN")
if [[ "$DRIVER_VERSION" < "590" ]]; then
    echo -e "${RED}❌ $DRIVER_VERSION (needs 590+)${NC}"
else
    echo -e "${GREEN}✅ $DRIVER_VERSION${NC}"
fi

echo -n "Checking CUDA... "
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep release | awk '{print $6}' | tr -d ',' || echo "UNKNOWN")
    echo -e "${GREEN}✅ $CUDA_VERSION${NC}"
else
    echo -e "${YELLOW}⚠️  nvcc not found${NC}"
    CUDA_VERSION=$(nvidia-smi | grep CUDA | awk '{print $9}' || echo "UNKNOWN")
    echo "   CUDA from nvidia-smi: $CUDA_VERSION"
fi
echo ""

echo "🔍 2. CUDA Version Check:"
echo "----------------"
echo -n "Checking CUDA installation... "
if command -v nvcc &> /dev/null; then
    echo "✓ Found"
    nvcc --version | grep release
else
    echo "⚠ Not found via nvcc"
    echo "Checking via nvidia-smi..."
    nvidia-smi | grep CUDA || echo "No CUDA info in nvidia-smi"
fi
echo ""

echo "🐳 3. Docker Containers Status:"
echo "---------------------"
docker ps -a --filter name=vllm --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker check failed"
echo ""

# Check model directory
echo "📁 4. Model Directory Analysis:"
echo "-------------------------"
MODEL_PATH="$HOME/babs-data/models/nemotron3-super-nvfp4"
echo -n "Checking model path '$MODEL_PATH'... "
if [ -d "$MODEL_PATH" ]; then
    echo "✓ Exists"
    echo -n "Counting files... "
    FILE_COUNT=$(find "$MODEL_PATH" -type f 2>/dev/null | wc -l)
    echo "$FILE_COUNT files found"

    # Check for key files with progress
    echo "🔍 Checking key files:"
    key_files=("config.json" "hf_quant_config.json" "model.safetensors.index.json")
    for file in "${key_files[@]}"; do
        echo -n "  - $file... "
        if [ -f "$MODEL_PATH/$file" ]; then
            echo "✓"
        else
            echo "✗"
        fi
    done
    # Check quantization config
    if [ -f "$MODEL_PATH/hf_quant_config.json" ]; then
echo ""
        echo "📊 Quantization config:"
        QUANT_ALGO=$(grep -o '"quant_algo":[[:space:]]*"[^"]*"' "$MODEL_PATH/hf_quant_config.json" | cut -d'"' -f4 || echo "Unknown")
        echo "  Algorithm: $QUANT_ALGO"
    fi
else
    echo "✗ Not found"
    echo "❌ Model weights missing - cannot proceed"
    exit 1
fi
echo ""

# Library Dependencies Check
echo "📚 5. Library Dependencies Check:"
echo "-------------------------------"
echo -n "Checking for CUDA libraries... "
if ldconfig -p 2>/dev/null | grep -q libcudart; then
    echo "✓ Found CUDA libraries"
    echo "Available CUDA library versions:"
    ldconfig -p 2>/dev/null | grep libcudart | head -5
else
    echo "⚠ No CUDA libraries found via ldconfig"
fi
echo ""

echo "🐍 6. Python Environment Check:"
echo "--------------------------------"
echo -n "Testing Python imports... "
cat << 'EOF' > /tmp/test_imports.py
import sys
print(f"Python {sys.version}")
try:
    import torch
    print(f"✓ PyTorch {torch.__version__}")
    if torch.cuda.is_available():
        print(f"✓ CUDA available: {torch.version.cuda}")
        print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("✗ CUDA not available in PyTorch")
except ImportError:
    print("✗ PyTorch not installed")

try:
    import vllm
    print(f"✓ vLLM {vllm.__version__}")
except ImportError:
    print("✗ vLLM not installed")
EOF

python3 /tmp/test_imports.py
rm -f /tmp/test_imports.py
echo ""

echo "💾 7. Memory Availability Check:"
echo "--------------------------------"
echo -n "Total system memory: "
free -h | grep Mem | awk '{print $2}'
echo -n "Available memory: "
free -h | grep Mem | awk '{print $7}'
echo ""

echo "✅ Diagnostic Complete"
echo ""
echo "📋 Summary:"
echo "-----------"
echo "1. Run ./scripts/test_nemotron_super.sh for vLLM 0.17.1 build"
echo "2. If that fails, we'll fall back to Nemotron 3 Nano"
echo "3. Monitor progress in terminal - each step will show ✅ or ❌"
echo ""
