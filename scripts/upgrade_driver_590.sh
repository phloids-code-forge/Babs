#!/bin/bash
# Upgrade NVIDIA Driver to 590 for SM121 NVFP4 Support
# This fixes CUDA illegal instruction errors with Nemotron models on DGX Spark

set -e

echo "=== NVIDIA Driver 590 Upgrade Script ==="
echo ""
echo "Current driver version:"
nvidia-smi --query-gpu=driver_version --format=csv,noheader

echo ""
echo "Updating package lists..."
sudo apt update

echo ""
echo "Available driver versions:"
apt-cache madison nvidia-driver | head -5

echo ""
echo "Installing NVIDIA driver 590..."
echo "WARNING: This will require a reboot!"
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled."
    exit 1
fi

# Install driver 590
sudo apt install -y nvidia-driver-590

echo ""
echo "Driver installation complete!"
echo ""
echo "You MUST reboot for the new driver to take effect."
echo "After reboot, verify with: nvidia-smi"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Rebooting..."
    sudo reboot
else
    echo "Remember to reboot manually before testing vLLM!"
fi
