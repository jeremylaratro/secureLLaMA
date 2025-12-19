#!/bin/bash
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

# Detect default network interface
INTERFACE="${1:-$(ip route | grep default | awk '{print $5}' | head -n1)}"

if [ -z "$INTERFACE" ]; then
    echo "Warning: Could not detect network interface, using 'eth0'"
    INTERFACE="eth0"
fi

echo "Starting monitoring services on interface: $INTERFACE"

# Start Snort3 in daemon mode
if command -v /usr/local/snort/bin/snort &> /dev/null; then
    echo "Starting Snort3 IDS..."
    /usr/local/snort/bin/snort -D -i "$INTERFACE" \
        -c /usr/local/snort/etc/snort/snort.lua \
        --rule-path /usr/local/snort/etc/snort/rules \
        --daq-dir /usr/local/lib/daq/ \
        -l /var/log/snort
else
    echo "Warning: Snort3 not found, skipping IDS setup"
fi

# Create ClamAV scan script
CLAM_SCRIPT="/usr/local/bin/clam_scan.sh"
cat <<'EOF' > "$CLAM_SCRIPT"
#!/bin/bash
# Directory to scan
SCAN_DIR="/"

# Log file for clamscan
LOG_FILE="/var/log/clamav/daily-scan.log"

# Ensure log directory exists
mkdir -p /var/log/clamav

# Run clamscan
clamscan -r "$SCAN_DIR" \
    --exclude-dir="^/sys" \
    --exclude-dir="^/proc" \
    --exclude-dir="^/dev" \
    --log="$LOG_FILE"
EOF

chmod +x "$CLAM_SCRIPT"

# Define the cron job (daily at 2 AM)
CRON_JOB="0 2 * * * $CLAM_SCRIPT"

# Check if the cron job already exists
if crontab -l 2>/dev/null | grep -qF "$CLAM_SCRIPT"; then
    echo "ClamAV cron job already exists."
else
    # Add the new cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "ClamAV cron job added successfully."
fi

# Start services
echo "Starting auditd..."
service auditd start || systemctl start auditd || echo "Warning: Could not start auditd"

echo "Starting UFW..."
service ufw start || systemctl start ufw || ufw enable || echo "Warning: Could not start UFW"

echo "Starting collectd..."
service collectd start || systemctl start collectd || echo "Warning: Could not start collectd"

# Enable audit rules for network connections
echo "Configuring audit rules..."
auditctl -a always,exit -F arch=b64 -S connect -S accept -k network_connections 2>/dev/null || \
    echo "Warning: Could not set audit rules (may already exist)"

# Start tcpdump to monitor Gradio web requests
echo "Starting network capture for Gradio traffic..."
mkdir -p /var/log
nohup tcpdump -i "$INTERFACE" port 7860 -w /var/log/gradio_requests.pcap &>/dev/null &

echo "Monitoring services started successfully."
