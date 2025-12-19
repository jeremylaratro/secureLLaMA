#!/bin/bash
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

echo "Installing host dependencies for SecureLLaMA..."

# Install core packages
sudo dnf install -y docker virt-manager qemu nvidia-container-toolkit bubblewrap

# Install Bearer security scanner
echo "Installing Bearer security scanner..."
curl -sfL https://raw.githubusercontent.com/Bearer/bearer/main/contrib/install.sh | sh

# Enable and start Docker
echo "Enabling Docker service..."
sudo systemctl enable docker
sudo systemctl start docker

# Configure NVIDIA container toolkit
echo "Configuring NVIDIA container toolkit..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "Host setup complete."
echo ""
echo "For VM setup, run the following commands:"
echo "  sudo systemctl enable auditd"
echo "  sudo dnf install xtables-addons xtables-addons-kmod"
