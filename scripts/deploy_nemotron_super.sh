#!/bin/bash
# Comprehensive Nemotron 3 Super deployment with progress tracking

set -e

# Color codes for progress display
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_step() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}STEP $1: $2${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Function to show spinner during long operations
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

print_status "🚀 Starting Nemotron 3 Super deployment process"
print_status "Hardware: DGX Spark with 128GB unified memory"
print_status "Model: Nemotron 3 Super 120B NVFP4 (MIXED_PRECISION)"
echo ""

# ========================================
# STEP 1: Pre-flight checks
# ========================================
print_step "1" "Pre-flight System Checks"

print_status "Checking NVIDIA driver version..."
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo "UNKNOWN")
print_status "Current driver: $DRIVER_VERSION"

if [[ "$DRIVER_VERSION" < "590" ]]; then
    print_error "Driver must be 590.48.01 or higher for SM121 compatibility"
    print_warning "Run: ./scripts/upgrade_driver_590.sh"
    exit 1
else
    print_success "Driver version OK ($DRIVER_VERSION)"
fi

print_status "Checking CUDA availability..."
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep release | awk '{print $6}' | tr -d ',')
    print_success "CUDA $CUDA_VERSION detected"
else
    print_warning "nvcc not found, checking via nvidia-smi"
    CUDA_VERSION=$(nvidia-smi | grep CUDA | awk '{print $9}' || echo "UNKNOWN")
    print_status "CUDA version from nvidia-smi: $CUDA_VERSION"
fi

print_status "Checking Docker..."
if command -v docker &> /dev/null; then
    print_success "Docker is available"
else
    print_error "Docker not found"
    exit 1
fi

print_status "Checking model weights..."
MODEL_PATH="$HOME/babs-data/models/nemotron3-super-nvfp4"
if [ ! -d "$MODEL_PATH" ]; then
    print_error "Model weights not found at $MODEL_PATH"
    print_warning "Run: ./scripts/download_nemotron_super.sh"
    exit 1
fi

WEIGHT_FILES=$(find "$MODEL_PATH" -name "*.safetensors" | wc -l)
if [ "$WEIGHT_FILES" -lt 10 ]; then
    print_error "Incomplete model weights: only $WEIGHT_FILES safetensors files"
    exit 1
fi
print_success "Model weights found ($WEIGHT_FILES safetensors files)"

# ========================================
# STEP 2: Build custom vLLM image
# ========================================
print_step "2" "Building vLLM for CUDA 13.1 Compatibility"

print_status "Checking for existing vLLM image..."
if docker images | grep -q "vllm-cuda13-super"; then
    print_warning "Custom vLLM image already exists"
    read -p "Rebuild image? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Removing old image..."
        docker rmi vllm-cuda13-super 2>/dev/null || true
        REBUILD=true
    else
        REBUILD=false
    fi
else
    REBUILD=true
fi

if [ "$REBUILD" = true ]; then
    print_status "Building custom vLLM image from source..."
    print_status "This will take 10-15 minutes..."
    
    # Start build in background and show spinner
    (cd ~/babs/docker && docker build -f Dockerfile.vllm-super -t vllm-cuda13-super .) &
    BUILD_PID=$!
    
    # Show spinner while building
    spinner $BUILD_PID &
    SPINNER_PID=$!
    
    # Wait for build to complete
    wait $BUILD_PID
    BUILD_RESULT=$?
    
    # Kill spinner
    kill $SPINNER_PID 2>/dev/null
    wait $SPINNER_PID 2>/dev/null
    
    if [ $BUILD_RESULT -eq 0 ]; then
        print_success "vLLM image built successfully"
    else
        print_error "Failed to build vLLM image"
        print_warning "Falling back to patched vLLM 0.14.0 approach..."
        
        print_status "Building patched vLLM 0.14.0 image..."
        (cd ~/babs/docker && docker build -f Dockerfile.vllm-modelopt-patch -t vllm-patched .) &
        PATCH_PID=$!
        spinner $PATCH_PID &
        SPINNER2_PID=$!
        wait $PATCH_PID
        kill $SPINNER2_PID 2>/dev/null
        wait $SPINNER2_PID 2>/dev/null
        
        if [ $? -eq 0 ]; then
            print_success "Patched vLLM 0.14.0 image built"
            USE_PATCHED=true
        else
            print_error "All build attempts failed"
            exit 1
        fi
    fi
else
    print_success "Using existing vLLM image"
fi

# ========================================
# STEP 3: Deploy vLLM container
# ========================================
print_step "3" "Deploying vLLM Container"

print_status "Stopping any existing vLLM containers..."
docker stop vllm-babs 2>/dev/null || true
docker rm vllm-babs 2>/dev/null || true
print_success "Cleaned up old containers"

print_status "Starting Nemotron 3 Super container..."

if [ "$USE_PATCHED" = true ]; then
    print_warning "Using patched vLLM 0.14.0 (MIXED_PRECISION support)"
    IMAGE_NAME="vllm-patched"
    QUANT_ARG=""  # Patched version handles MIXED_PRECISION automatically
else
    print_status "Using vLLM built from source"
    IMAGE_NAME="vllm-cuda13-super"
    QUANT_ARG="--quantization modelopt_fp4"
fi

docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -e VLLM_FLASHINFER_MOE_BACKEND=throughput \
  -v ~/babs-data/models/nemotron3-super-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  -v ~/babs/scripts/super_v3_reasoning_parser.py:/opt/super_v3_reasoning_parser.py \
  "$IMAGE_NAME" \
  vllm serve /model \
  --served-model-name nemotron3-super \
  --dtype auto \
  --kv-cache-dtype fp8 \
  $QUANT_ARG \
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

if [ $? -eq 0 ]; then
    print_success "Container started successfully"
else
    print_error "Failed to start container"
    exit 1
fi

# ========================================
# STEP 4: Monitor startup
# ========================================
print_step "4" "Monitoring Model Loading"

print_status "Waiting for vLLM to initialize..."
print_status "Model loading will take 1-3 minutes for 120B parameters"

LOAD_START=$(date +%s)
MAX_WAIT=300  # 5 minutes max
CHECK_INTERVAL=5

for ((i=0; i<=MAX_WAIT; i+=CHECK_INTERVAL)); do
    # Show progress bar
    PERCENT=$(( (i * 100) / MAX_WAIT ))
    BAR_LENGTH=$(( PERCENT / 2 ))
    BAR=$(printf "▓%.0s" $(seq 1 $BAR_LENGTH))
    SPACES=$(printf " %.0s" $(seq 1 $((50 - BAR_LENGTH))))
    echo -ne "\r🔄 Loading: |${BAR}${SPACES}| ${PERCENT}% (${i}s/${MAX_WAIT}s)"
    
    # Check health endpoint
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n"
        print_success "vLLM is ready and responding!"
        LOAD_END=$(date +%s)
        LOAD_TIME=$((LOAD_END - LOAD_START))
        print_status "Model loaded in ${LOAD_TIME} seconds"
        break
    fi
    
    # Check if container crashed
    if ! docker ps --format "{{.Names}}" | grep -q "vllm-babs"; then
        echo -e "\n"
        print_error "Container crashed during startup"
        print_status "Checking logs..."
        docker logs vllm-babs --tail 20
        exit 1
    fi
    
    sleep $CHECK_INTERVAL
    
    if [ $i -ge $MAX_WAIT ]; then
        echo -e "\n"
        print_error "Timeout waiting for vLLM to start"
        print_status "Container logs:"
        docker logs vllm-babs --tail 30
        exit 1
    fi
done

# ========================================
# STEP 5: Run test inference
# ========================================
print_step "5" "Running Test Inference"

print_status "Testing with simple prompt..."
TEST_RESPONSE=$(curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron3-super",
    "prompt": "Hello! I am testing the Nemotron 3 Super deployment. Please respond with a brief greeting.",
    "max_tokens": 50,
    "temperature": 0.7
  }' 2>/dev/null | jq -r '.choices[0].text 2>/dev/null // "ERROR"')

if [ "$TEST_RESPONSE" != "ERROR" ] && [ ! -z "$TEST_RESPONSE" ]; then
    print_success "Inference test successful!"
    echo ""
    echo "🤖 Model response:"
    echo "-----------------"
    echo "$TEST_RESPONSE"
    echo "-----------------"
else
    print_error "Inference test failed"
    print_status "Checking container status..."
    docker logs vllm-babs --tail 20
    exit 1
fi

# ========================================
# STEP 6: Fallback to Nano if needed
# ========================================
print_step "6" "Fallback Readiness Check"

print_status "Checking Nemotron 3 Nano availability..."
NANO_PATH="$HOME/babs-data/models/nemotron3-nano-nvfp4"
if [ -d "$NANO_PATH" ]; then
    NANO_FILES=$(find "$NANO_PATH" -name "*.safetensors" | wc -l)
    if [ "$NANO_FILES" -ge 5 ]; then
        print_success "Nemotron 3 Nano available as fallback ($NANO_FILES files)"
        print_status "To switch to Nano:"
        echo "  docker stop vllm-babs && docker rm vllm-babs"
        echo "  docker run ... (use nano model path and name)"
    else
        print_warning "Nano model incomplete - consider redownloading"
    fi
else
    print_warning "Nano model not found - no automatic fallback"
    print_status "Download with: ./scripts/download_nemotron_super.sh (edit for nano)"
fi

# ========================================
# Final Status
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🚀 DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📊 Deployment Status:"
echo "  ✅ Driver: $DRIVER_VERSION"
echo "  ✅ CUDA: $CUDA_VERSION"
echo "  ✅ Model: Nemotron 3 Super 120B NVFP4"
echo "  ✅ Container: $(docker ps --filter name=vllm-babs --format '{{.Status}}')"
echo "  ✅ Endpoint: http://localhost:8000"
echo "  ✅ Health check: curl http://localhost:8000/health"
echo ""
echo "🔧 Quick commands:"
echo "  Check logs:    docker logs vllm-babs --tail 20"
echo "  Stop:          docker stop vllm-babs"
echo "  Restart:       docker restart vllm-babs"
echo "  Test:          curl http://localhost:8000/v1/completions [json]"
echo ""
echo "⚠️  Next steps:"
echo "  1. Update Supervisor config to use 'nemotron3-super'"
echo "  2. Monitor memory usage during extended generation"
echo "  3. Test with actual Babs workflows"
echo ""
print_status "Deployment completed at $(date '+%H:%M:%S')"