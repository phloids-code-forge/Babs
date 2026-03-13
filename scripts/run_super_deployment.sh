#!/bin/bash
# One-command Nemotron 3 Super deployment with automatic progress display

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║      NVIDIA Nemotron 3 Super 120B NVFP4 Deployment      ║"
echo "║            DGX Spark | 128GB Unified Memory             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📋 This script will:"
echo "   1. ✅ Check system requirements"
echo "   2. 🔧 Build vLLM for CUDA 13.1 compatibility"
echo "   3. 🚀 Deploy Nemotron 3 Super container"
echo "   4. 🧪 Run test inference"
echo "   5. 🔄 Fall back to Nano if needed"
echo ""
echo "⏰ Estimated time: 15-20 minutes"
echo ""

# Ask for confirmation
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "🔄 Starting deployment process..."
echo ""

# Make scripts executable
chmod +x scripts/diagnose_nemotron.sh 2>/dev/null || true
chmod +x scripts/deploy_nemotron_super.sh 2>/dev/null || true

# Run diagnostics first
echo "🔍 Running system diagnostics..."
echo "--------------------------------"
if ./scripts/diagnose_nemotron.sh; then
    echo ""
    echo "✅ Diagnostics passed"
else
    echo ""
    echo "❌ Diagnostics failed - check output above"
    exit 1
fi

echo ""
echo "🔄 Proceeding with deployment..."
echo ""

# Run the main deployment script
if ./scripts/deploy_nemotron_super.sh; then
    echo ""
    echo "🎉 Deployment successful!"
    echo ""
    echo "Quick test command:"
    echo 'curl -s http://localhost:8000/v1/completions \'
    echo '  -H "Content-Type: application/json" \'
    echo '  -d '\''{"model": "nemotron3-super", "prompt": "Hello", "max_tokens": 20}'\'' | jq .'
else
    echo ""
    echo "❌ Deployment failed"
    echo ""
    echo "🔄 Attempting fallback to Nemotron 3 Nano..."
    echo ""
    
    # Check if Nano exists
    NANO_PATH="$HOME/babs-data/models/nemotron3-nano-nvfp4"
    if [ -d "$NANO_PATH" ]; then
        echo "📦 Nemotron 3 Nano found, deploying..."
        
        # Stop any existing containers
        docker stop vllm-babs 2>/dev/null || true
        docker rm vllm-babs 2>/dev/null || true
        
        # Start Nano container
        echo "🚀 Starting Nemotron 3 Nano..."
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
        
        echo ""
        echo "⏳ Waiting for Nano to start..."
        sleep 30
        
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ Nemotron 3 Nano deployed successfully!"
            echo "   Model: nemotron3-nano"
            echo "   Speed: ~65+ tokens/sec"
            echo "   Memory: ~30GB weights"
        else
            echo "❌ Nano deployment also failed"
            echo "   Check logs: docker logs vllm-babs"
        fi
    else
        echo "❌ Nemotron 3 Nano not found at $NANO_PATH"
        echo "   Download with: hf download nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
    fi
fi

echo ""
echo "📝 Deployment complete. Next steps:"
echo "   1. Update Supervisor MODEL_NAME in docker-compose.supervisor.yml"
echo "   2. Test with actual Babs workflows"
echo "   3. Monitor memory usage: watch -n 1 'free -h && nvidia-smi | grep -A1 Memory'"
echo ""