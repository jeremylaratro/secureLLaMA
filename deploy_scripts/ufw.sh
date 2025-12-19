#!/bin/bash
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

# Detect default network interface if not provided
INTERFACE="${1:-$(ip route | grep default | awk '{print $5}' | head -n1)}"

if [ -z "$INTERFACE" ]; then
    echo "Error: Could not detect network interface. Please provide as argument."
    echo "Usage: $0 [interface]"
    exit 1
fi

echo "Configuring UFW firewall on interface: $INTERFACE"

# Set default policies
sudo ufw default deny incoming
sudo ufw default deny outgoing

# Allow HTTPS (port 443) from VLAN 192.168.100.0/24
sudo ufw allow in on "$INTERFACE" from 192.168.100.0/24 to any port 443 proto tcp
sudo ufw allow out on "$INTERFACE" to 192.168.100.0/24 port 443 proto tcp

# Allow Gradio web UI (port 7860) from VLAN 192.168.100.0/24
sudo ufw allow in on "$INTERFACE" from 192.168.100.0/24 to any port 7860 proto tcp
sudo ufw allow out on "$INTERFACE" to 192.168.100.0/24 port 7860 proto tcp

# Allow SSH (port 22) from management VLAN 192.168.105.0/24
sudo ufw allow in on "$INTERFACE" from 192.168.105.0/24 to any port 22 proto tcp
sudo ufw allow out on "$INTERFACE" to 192.168.105.0/24 port 22 proto tcp

# Enable UFW
sudo ufw --force enable

echo "UFW firewall configured successfully."
sudo ufw status verbose
