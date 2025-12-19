#!/bin/bash
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

# This script is for container monitoring
# Run inside the Docker container

INTERFACE="${1:-$(ip route | grep default | awk '{print $5}' | head -n1)}"

if [ -z "$INTERFACE" ]; then
    echo "Warning: Could not detect network interface, using 'eth0'"
    INTERFACE="eth0"
fi

echo "Starting container monitoring services on interface: $INTERFACE"

# Start Snort3 in daemon mode (if installed)
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
SCAN_DIR="/app"
LOG_FILE="/var/log/clamav/daily-scan.log"
mkdir -p /var/log/clamav
clamscan -r "$SCAN_DIR" \
    --exclude-dir="^/sys" \
    --exclude-dir="^/proc" \
    --exclude-dir="^/dev" \
    --log="$LOG_FILE"
EOF

chmod +x "$CLAM_SCRIPT"

# Setup cron job for daily scan at 2 AM
CRON_JOB="0 2 * * * $CLAM_SCRIPT"
if crontab -l 2>/dev/null | grep -qF "$CLAM_SCRIPT"; then
    echo "ClamAV cron job already exists."
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "ClamAV cron job added successfully."
fi

# Start auditd if available
echo "Starting auditd..."
service auditd start 2>/dev/null || echo "Note: auditd not available in container"

echo "Container monitoring started successfully."
