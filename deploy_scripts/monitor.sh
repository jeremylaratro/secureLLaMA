#!/bin/bash

/usr/local/snort/bin/snort -D -i $(ifconfig | awk '{print $1}' | grep : | tr -d : | tr -d lo) -c /usr/local/snort/etc/snort/snort.lua --rule-path /usr/local/snort/etc/snort/rules --daq-dir /usr/local/lib/daq/ -l /var/log/snort

cat <<EOF > /etc/cron.d/clam.sh
#!/bin/bash
# Directory to scan
SCAN_DIR="/"

# Log file for clamscan
LOG_FILE="/var/log/clamav/daily-scan.log"

# Run clamscan
clamscan -r $SCAN_DIR --exclude-dir="^/sys" --exclude-dir="^/proc" --exclude-dir="^/dev" --log=$LOG_FILE
EOF

chmod +x /usr/local/bin/clam.sh
# Define the cron job
CRON_JOB="0 2 * * * /etc/cron.d/clam.sh"

# Check if the cron job already exists
(crontab -l 2>/dev/null | grep -F "$CRON_JOB") && echo "Cron job already exists." && exit 0
# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
echo "Cron job added successfully."
